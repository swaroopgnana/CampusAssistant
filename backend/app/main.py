from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
from pathlib import Path
import re
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import asyncio
from math import ceil
import warnings

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from PIL import Image, UnidentifiedImageError
from jose import JWTError, jwt
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.config import settings
from app.database import SessionLocal, get_db
from app.ai import AIServiceError, classify_intent
from app.models import (
    AcademicSection, AuditLog, CampusBuilding, CampusLocation, CampusPath, ChatConversation, ChatMessage,
    CollegeNews, Department, Event, Faculty, KnowledgeDocument, LostFoundReport,
    Notification, ReportImage, Subject, TimetableEntry, User,
)
from app.schemas import (
    AcademicSectionCreate, BuildingCreate, ChatRequest, ChatResponse, DepartmentCreate,
    EventCreate, EventUpdate, FacultyCreate, LocationCreate, KnowledgeDocumentCreate,
    NewsCreate, NewsUpdate, PathCreate, ProfileUpdate, RegisterRequest,
    ReportCreate, ReportStatusUpdate, RoleUpdate, SubjectCreate, TimetableCreate,
    TokenResponse, UserResponse,
)
from app.security import ALGORITHM, admin_user, create_access_token, current_user, hash_password, verify_password


app = FastAPI(title="Campus Pilot API", version="1.0.0")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
API = "/api/v1"
REPORT_STATUSES = {"SUBMITTED", "UNDER_REVIEW", "MATCHED", "READY_FOR_COLLECTION", "RESOLVED"}


def _utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        try:
            value = value.replace(tzinfo=ZoneInfo(settings.college_timezone))
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(500, "COLLEGE_TIMEZONE is not a valid timezone") from exc
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _college_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    try:
        return value.astimezone(ZoneInfo(settings.college_timezone)).isoformat()
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(500, "COLLEGE_TIMEZONE is not a valid timezone") from exc


def _event_payload(event: Event, location_name: str | None) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "starts_at": _college_iso(event.starts_at),
        "ends_at": _college_iso(event.ends_at),
        "timezone": settings.college_timezone,
        "location_id": event.location_id,
        "location": location_name,
        "organizer": event.organizer,
        "registration_url": event.registration_url,
        "registration_required": event.registration_required,
        "department_id": event.department_id,
        "published": event.published,
        "cancelled": event.cancelled,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(f"{API}/auth/register", response_model=TokenResponse, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, full_name=payload.full_name, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists") from exc
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id), user=user)


@app.post(f"{API}/auth/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password", headers={"WWW-Authenticate": "Bearer"})
    return TokenResponse(access_token=create_access_token(user.id), user=user)


@app.get(f"{API}/auth/me", response_model=UserResponse)
def me(user: User = Depends(current_user)):
    return user


@app.patch(f"{API}/auth/me/profile", response_model=UserResponse)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    values = payload.model_dump(exclude_unset=True)
    profile_fields = {"department_id", "semester", "section"}
    if values:
        profile = {field: values.get(field, getattr(user, field)) for field in profile_fields}
        if any(value is not None for value in profile.values()) and any(
            value is None for value in profile.values()
        ):
            raise HTTPException(422, "Set department, semester, and section together, or clear all three")
        if profile["department_id"] is not None and db.get(Department, profile["department_id"]) is None:
            raise HTTPException(404, "Department not found")
        if all(profile[field] is not None for field in profile_fields):
            section = db.scalar(select(AcademicSection).where(
                AcademicSection.department_id == profile["department_id"],
                AcademicSection.semester == profile["semester"],
                AcademicSection.section == str(profile["section"]).strip().upper(),
            ))
            if section is None:
                raise HTTPException(404, "That academic section has not been configured")
        for field, value in values.items():
            if field == "section" and value is not None:
                value = value.strip().upper()
            setattr(user, field, value)
        db.commit()
        db.refresh(user)
    return user


@app.get(f"{API}/campus/departments")
def list_departments(db: Session = Depends(get_db)):
    return db.scalars(select(Department).order_by(Department.name)).all()


@app.get(f"{API}/campus/config")
def campus_config():
    return {"timezone": settings.college_timezone}


@app.get(f"{API}/campus/subjects")
def list_subjects(db: Session = Depends(get_db)):
    return db.scalars(select(Subject).order_by(Subject.name)).all()


@app.get(f"{API}/events")
def list_events(
    date_filter: date | None = None,
    db: Session = Depends(get_db),
):
    query = select(Event, CampusLocation.name).outerjoin(
        CampusLocation, Event.location_id == CampusLocation.id
    ).where(Event.published.is_(True), Event.cancelled.is_(False))
    if date_filter:
        try:
            tz = ZoneInfo(settings.college_timezone)
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(500, "COLLEGE_TIMEZONE is not a valid timezone") from exc
        start = _utc_naive(datetime.combine(date_filter, time.min, tzinfo=tz))
        end = _utc_naive(datetime.combine(date_filter + timedelta(days=1), time.min, tzinfo=tz))
        query = query.where(Event.starts_at >= start, Event.starts_at < end)
    query = query.order_by(Event.starts_at)
    return [_event_payload(event, location) for event, location in db.execute(query).all()]


@app.get(f"{API}/events/today")
def events_today(db: Session = Depends(get_db)):
    try:
        local_today = datetime.now(ZoneInfo(settings.college_timezone)).date()
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(500, "COLLEGE_TIMEZONE is not a valid timezone") from exc
    return list_events(date_filter=local_today, db=db)


@app.get(f"{API}/events/{{event_id}}")
def get_event(event_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        select(Event, CampusLocation.name)
        .outerjoin(CampusLocation, Event.location_id == CampusLocation.id)
        .where(Event.id == event_id, Event.published.is_(True), Event.cancelled.is_(False))
    ).first()
    if row is None:
        raise HTTPException(404, "Event not found")
    return _event_payload(*row)


@app.post(f"{API}/admin/events", status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    values = payload.model_dump()
    values["starts_at"] = _utc_naive(values["starts_at"])
    values["ends_at"] = _utc_naive(values["ends_at"])
    if values["ends_at"] is not None and values["ends_at"] <= values["starts_at"]:
        raise HTTPException(422, "Event end time must be after its start time")
    if values["location_id"] is not None and db.get(CampusLocation, values["location_id"]) is None:
        raise HTTPException(404, "Campus location not found")
    if values["department_id"] is not None and db.get(Department, values["department_id"]) is None:
        raise HTTPException(404, "Department not found")
    event = Event(**values)
    db.add(event)
    db.flush()
    db.add(AuditLog(actor_id=admin.id, action="event.created", entity="event", entity_id=str(event.id)))
    db.commit()
    db.refresh(event)
    location = db.get(CampusLocation, event.location_id) if event.location_id else None
    return _event_payload(event, location.name if location else None)


@app.patch(f"{API}/admin/events/{{event_id}}")
def update_event(event_id: int, payload: EventUpdate, db: Session = Depends(get_db),
                 admin: User = Depends(admin_user)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    values = payload.model_dump(exclude_unset=True)
    for field in ("starts_at", "ends_at"):
        if field in values:
            values[field] = _utc_naive(values[field])
    next_start = values.get("starts_at", event.starts_at)
    next_end = values.get("ends_at", event.ends_at)
    if next_end is not None and next_end <= next_start:
        raise HTTPException(422, "Event end time must be after its start time")
    if values.get("location_id") is not None and db.get(CampusLocation, values["location_id"]) is None:
        raise HTTPException(404, "Campus location not found")
    if values.get("department_id") is not None and db.get(Department, values["department_id"]) is None:
        raise HTTPException(404, "Department not found")
    for field, value in values.items():
        setattr(event, field, value)
    db.add(AuditLog(actor_id=admin.id, action="event.updated", entity="event", entity_id=str(event.id)))
    db.commit()
    db.refresh(event)
    location = db.get(CampusLocation, event.location_id) if event.location_id else None
    return _event_payload(event, location.name if location else None)


@app.post(f"{API}/admin/news", status_code=201)
def create_news(payload: NewsCreate, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    item = CollegeNews(**payload.model_dump())
    db.add(item)
    db.flush()
    db.add(AuditLog(actor_id=admin.id, action="news.created", entity="college_news", entity_id=str(item.id)))
    db.commit()
    db.refresh(item)
    return item


@app.patch(f"{API}/admin/news/{{news_id}}")
def update_news(news_id: int, payload: NewsUpdate, db: Session = Depends(get_db),
                admin: User = Depends(admin_user)):
    item = db.get(CollegeNews, news_id)
    if item is None:
        raise HTTPException(404, "News item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.add(AuditLog(actor_id=admin.id, action="news.updated", entity="college_news", entity_id=str(item.id)))
    db.commit()
    db.refresh(item)
    return item


@app.post(f"{API}/admin/knowledge-documents", status_code=201)
def create_knowledge_document(payload: KnowledgeDocumentCreate, db: Session = Depends(get_db),
                              admin: User = Depends(admin_user)):
    document = KnowledgeDocument(**payload.model_dump(), approved=False)
    db.add(document)
    db.flush()
    db.add(AuditLog(actor_id=admin.id, action="knowledge_document.created",
                    entity="knowledge_document", entity_id=str(document.id)))
    db.commit()
    db.refresh(document)
    return document


@app.get(f"{API}/admin/knowledge-documents")
def list_knowledge_documents(db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    return db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())).all()


@app.patch(f"{API}/admin/knowledge-documents/{{document_id}}/approve")
def approve_knowledge_document(document_id: int, db: Session = Depends(get_db),
                               admin: User = Depends(admin_user)):
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(404, "Knowledge document not found")
    document.approved = True
    db.add(AuditLog(actor_id=admin.id, action="knowledge_document.approved",
                    entity="knowledge_document", entity_id=str(document.id)))
    db.commit()
    return {"id": document.id, "approved": document.approved}


@app.post(f"{API}/admin/departments", status_code=201)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db),
                      admin: User = Depends(admin_user)):
    department = Department(name=payload.name.strip())
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


@app.post(f"{API}/admin/campus/buildings", status_code=201)
def create_building(payload: BuildingCreate, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    building = CampusBuilding(**payload.model_dump())
    db.add(building)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A building with this name already exists") from exc
    db.refresh(building)
    return building


@app.post(f"{API}/admin/subjects", status_code=201)
def create_subject(payload: SubjectCreate, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    subject = Subject(**payload.model_dump())
    db.add(subject)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A subject with this code already exists") from exc
    db.refresh(subject)
    return subject


@app.post(f"{API}/admin/faculty", status_code=201)
def create_faculty(payload: FacultyCreate, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    if payload.department_id is not None and db.get(Department, payload.department_id) is None:
        raise HTTPException(404, "Department not found")
    faculty = Faculty(**payload.model_dump())
    db.add(faculty)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A faculty record with this email already exists") from exc
    db.refresh(faculty)
    return faculty


@app.post(f"{API}/admin/academic-sections", status_code=201)
def create_academic_section(payload: AcademicSectionCreate, db: Session = Depends(get_db),
                            admin: User = Depends(admin_user)):
    if db.get(Department, payload.department_id) is None:
        raise HTTPException(404, "Department not found")
    values = payload.model_dump()
    values["section"] = values["section"].strip().upper()
    section = AcademicSection(**values)
    db.add(section)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This academic section already exists") from exc
    db.refresh(section)
    return section


@app.post(f"{API}/admin/campus/locations", status_code=201)
def create_location(payload: LocationCreate, db: Session = Depends(get_db),
                    admin: User = Depends(admin_user)):
    if payload.building_id is not None and db.get(CampusBuilding, payload.building_id) is None:
        raise HTTPException(404, "Campus building not found")
    location = CampusLocation(**payload.model_dump())
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@app.get(f"{API}/admin/academic-sections")
def list_academic_sections(db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    rows = db.execute(
        select(AcademicSection, Department.name)
        .join(Department, AcademicSection.department_id == Department.id)
        .order_by(Department.name, AcademicSection.semester, AcademicSection.section)
    ).all()
    return [
        {"id": item.id, "department_id": item.department_id, "department": department,
         "semester": item.semester, "section": item.section}
        for item, department in rows
    ]


@app.get(f"{API}/admin/campus/paths")
def list_campus_paths(db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    origin_location = aliased(CampusLocation)
    destination_location = aliased(CampusLocation)
    return [
        {"id": path.id, "from_location": origin, "to_location": destination,
         "distance_meters": path.distance_meters, "accessible": path.accessible}
        for path, origin, destination in db.execute(
            select(CampusPath, origin_location.name, destination_location.name)
            .join(origin_location, CampusPath.from_location_id == origin_location.id)
            .join(destination_location, CampusPath.to_location_id == destination_location.id)
        ).all()
    ]


@app.get(f"{API}/admin/timetable")
def list_admin_timetable(db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    rows = db.execute(
        select(TimetableEntry, Department.name, Subject.name)
        .join(Department, TimetableEntry.department_id == Department.id)
        .join(Subject, TimetableEntry.subject_id == Subject.id)
        .order_by(TimetableEntry.weekday, TimetableEntry.starts_at)
    ).all()
    return [
        {"id": entry.id, "department": department, "semester": entry.semester,
         "section": entry.section, "subject": subject, "weekday": entry.weekday,
         "starts_at": entry.starts_at, "ends_at": entry.ends_at}
        for entry, department, subject in rows
    ]


@app.post(f"{API}/admin/campus/paths", status_code=201)
def create_path(payload: PathCreate, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    if payload.from_location_id == payload.to_location_id:
        raise HTTPException(422, "A pathway must connect two different locations")
    for location_id in (payload.from_location_id, payload.to_location_id):
        if db.get(CampusLocation, location_id) is None:
            raise HTTPException(404, f"Campus location {location_id} was not found")
    path = CampusPath(**payload.model_dump())
    db.add(path)
    db.commit()
    db.refresh(path)
    return path


@app.post(f"{API}/admin/timetable", status_code=201)
def create_timetable_entry(payload: TimetableCreate, db: Session = Depends(get_db),
                           admin: User = Depends(admin_user)):
    if db.get(Department, payload.department_id) is None:
        raise HTTPException(404, "Department not found")
    academic_section = db.scalar(select(AcademicSection).where(
        AcademicSection.department_id == payload.department_id,
        AcademicSection.semester == payload.semester,
        AcademicSection.section == payload.section.strip().upper(),
    ))
    if academic_section is None:
        raise HTTPException(404, "Academic section not found")
    if db.get(Subject, payload.subject_id) is None:
        raise HTTPException(404, "Subject not found")
    if payload.faculty_id is not None and db.get(Faculty, payload.faculty_id) is None:
        raise HTTPException(404, "Faculty member not found")
    if payload.location_id is not None and db.get(CampusLocation, payload.location_id) is None:
        raise HTTPException(404, "Campus location not found")
    try:
        if time.fromisoformat(payload.ends_at) <= time.fromisoformat(payload.starts_at):
            raise HTTPException(422, "Class end time must be after its start time")
    except ValueError as exc:
        raise HTTPException(422, "Class times must be valid 24-hour HH:MM values") from exc
    values = payload.model_dump()
    values["section"] = values["section"].strip().upper()
    entry = TimetableEntry(**values)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@app.get(f"{API}/admin/users")
def list_users(db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    return [
        {"id": user.id, "email": user.email, "full_name": user.full_name,
         "role": user.role, "is_active": user.is_active, "created_at": user.created_at}
        for user in db.scalars(select(User).order_by(User.id)).all()
    ]


@app.patch(f"{API}/admin/users/{{user_id}}/role")
def update_user_role(user_id: int, payload: RoleUpdate, db: Session = Depends(get_db),
                     admin: User = Depends(admin_user)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id and payload.role != "admin":
        raise HTTPException(422, "You cannot remove your own administrator role")
    user.role = payload.role
    db.add(AuditLog(actor_id=admin.id, action="user.role_changed", entity="user", entity_id=str(user.id)))
    db.commit()
    return {"id": user.id, "role": user.role}


@app.get(f"{API}/news")
def list_news(db: Session = Depends(get_db)):
    return db.scalars(
        select(CollegeNews).where(CollegeNews.published.is_(True)).order_by(CollegeNews.published_at.desc())
    ).all()


@app.get(f"{API}/admin/events")
def list_admin_events(db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    rows = db.execute(
        select(Event, CampusLocation.name)
        .outerjoin(CampusLocation, Event.location_id == CampusLocation.id)
        .order_by(Event.starts_at.desc())
    ).all()
    return [_event_payload(event, location) for event, location in rows]


@app.get(f"{API}/admin/news")
def list_admin_news(db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    return db.scalars(select(CollegeNews).order_by(CollegeNews.published_at.desc())).all()


@app.get(f"{API}/admin/departments")
def list_admin_departments(db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    return db.scalars(select(Department).order_by(Department.name)).all()


@app.get(f"{API}/admin/overview")
def admin_overview(db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    return {
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "events": db.scalar(select(func.count()).select_from(Event)) or 0,
        "news": db.scalar(select(func.count()).select_from(CollegeNews)) or 0,
        "open_reports": db.scalar(select(func.count()).select_from(LostFoundReport).where(
            LostFoundReport.status != "RESOLVED"
        )) or 0,
    }


@app.get(f"{API}/admin/audit-logs")
def admin_audit_logs(limit: int = 100, offset: int = 0, db: Session = Depends(get_db),
                     admin: User = Depends(admin_user)):
    if limit < 1 or limit > 200 or offset < 0:
        raise HTTPException(422, "Limit must be 1-200 and offset must be non-negative")
    return db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc())
                      .offset(offset).limit(limit)).all()


@app.get(f"{API}/campus/locations")
def locations(db: Session = Depends(get_db)):
    return db.scalars(select(CampusLocation).order_by(CampusLocation.name)).all()


@app.get(f"{API}/campus/search")
def search_campus(q: str, db: Session = Depends(get_db)):
    query = q.strip()
    if len(query) < 2 or len(query) > 120:
        raise HTTPException(422, "Search text must be 2-120 characters")
    matches = db.scalars(select(CampusLocation).where(
        CampusLocation.name.ilike(f"%{query}%")
    ).order_by(CampusLocation.name).limit(20)).all()
    return matches


@app.post(f"{API}/navigation/route")
def navigation_route(origin_id: int, destination_id: int, accessible_only: bool = False,
                     db: Session = Depends(get_db)):
    if origin_id == destination_id:
        raise HTTPException(422, "Origin and destination must be different")
    locations_by_id = {row.id: row for row in db.scalars(select(CampusLocation)).all()}
    if origin_id not in locations_by_id or destination_id not in locations_by_id:
        raise HTTPException(404, "Origin or destination was not found")
    edges: dict[int, list[tuple[int, int]]] = {}
    path_query = select(CampusPath)
    if accessible_only:
        path_query = path_query.where(CampusPath.accessible.is_(True))
    for path in db.scalars(path_query).all():
        edges.setdefault(path.from_location_id, []).append((path.to_location_id, path.distance_meters))
        edges.setdefault(path.to_location_id, []).append((path.from_location_id, path.distance_meters))
    # Dijkstra over administrator-maintained pathways; no route is inferred when data is absent.
    pending = [(0, origin_id, [origin_id])]
    distances: dict[int, int] = {}
    while pending:
        pending.sort(key=lambda item: item[0], reverse=True)
        distance, node, path = pending.pop()
        if node in distances:
            continue
        distances[node] = distance
        if node == destination_id:
            return {
                "locations": [
                    {"id": item, "name": locations_by_id[item].name,
                     "latitude": locations_by_id[item].latitude,
                     "longitude": locations_by_id[item].longitude}
                    for item in path
                ],
                "distance_meters": distance,
                "estimated_walking_minutes": max(1, ceil(distance / 80)),
            }
        for neighbor, weight in edges.get(node, []):
            if neighbor not in distances:
                pending.append((distance + weight, neighbor, path + [neighbor]))
    raise HTTPException(404, "No mapped campus pathway connects these locations")


@app.get(f"{API}/timetable")
def timetable(department_id: int | None = None, semester: int | None = None, section: str | None = None,
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    department_id = user.department_id if department_id is None else department_id
    semester = user.semester if semester is None else semester
    section = user.section if section is None else section
    if not department_id or not semester or not section:
        raise HTTPException(422, "Provide department_id, semester, and section or complete your profile")
    rows = db.execute(
        select(TimetableEntry, Subject.name, Faculty.name, CampusLocation.name)
        .join(Subject, TimetableEntry.subject_id == Subject.id)
        .outerjoin(Faculty, TimetableEntry.faculty_id == Faculty.id)
        .outerjoin(CampusLocation, TimetableEntry.location_id == CampusLocation.id)
        .where(
            TimetableEntry.department_id == department_id,
            TimetableEntry.semester == semester,
            TimetableEntry.section == section,
        )
        .order_by(TimetableEntry.weekday, TimetableEntry.starts_at)
    ).all()
    return [
        {"id": entry.id, "weekday": entry.weekday, "starts_at": entry.starts_at,
         "ends_at": entry.ends_at, "subject": subject, "faculty": faculty, "location": location}
        for entry, subject, faculty, location in rows
    ]


@app.get(f"{API}/timetable/next-class")
def next_class(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.department_id is None or user.semester is None or not user.section:
        raise HTTPException(422, "Complete your department, semester, and section in your profile first")
    try:
        now = datetime.now(ZoneInfo(settings.college_timezone))
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(500, "COLLEGE_TIMEZONE is not a valid timezone") from exc
    rows = db.execute(
        select(TimetableEntry, Subject.name, Faculty.name, CampusLocation.name)
        .join(Subject, TimetableEntry.subject_id == Subject.id)
        .outerjoin(Faculty, TimetableEntry.faculty_id == Faculty.id)
        .outerjoin(CampusLocation, TimetableEntry.location_id == CampusLocation.id)
        .where(
            TimetableEntry.department_id == user.department_id,
            TimetableEntry.semester == user.semester,
            TimetableEntry.section == user.section,
        )
    ).all()
    upcoming = []
    for entry, subject, faculty, location in rows:
        days_ahead = (entry.weekday - now.weekday()) % 7
        starts = datetime.combine(
            now.date() + timedelta(days=days_ahead),
            time.fromisoformat(entry.starts_at),
            tzinfo=now.tzinfo,
        )
        if starts <= now:
            starts += timedelta(days=7)
        upcoming.append((starts, entry, subject, faculty, location))
    if not upcoming:
        return {"next_class": None, "message": "No timetable entries are available for your profile."}
    starts, entry, subject, faculty, location = min(upcoming, key=lambda row: row[0])
    return {"next_class": {
        "starts_at": starts.isoformat(), "ends_at": entry.ends_at, "subject": subject,
        "faculty": faculty, "location": location,
    }}


@app.post(f"{API}/chat/message", response_model=ChatResponse)
@limiter.limit("20/minute")
def chat(request: Request, payload: ChatRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    conversation = None
    if payload.conversation_id is not None:
        conversation = db.get(ChatConversation, payload.conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise HTTPException(404, "Conversation not found")
    else:
        conversation = ChatConversation(user_id=user.id)
        db.add(conversation)
        db.flush()
    history = db.scalars(select(ChatMessage).where(
        ChatMessage.conversation_id == conversation.id
    ).order_by(ChatMessage.created_at.desc()).limit(12)).all()
    history.reverse()
    db.add(ChatMessage(conversation_id=conversation.id, role="user", content=payload.message))

    text = payload.message.casefold()
    try:
        intent = classify_intent(
            payload.message,
            [(message.role, message.content) for message in history],
        )
    except AIServiceError as exc:
        raise HTTPException(502, str(exc)) from exc
    needs_clarification = False
    timetable_context = any(
        message.role == "assistant" and "timetable" in message.content.casefold()
        for message in history
    )
    is_timetable = intent == "timetable" if intent is not None else (
        any(term in text for term in ("timetable", "next class", "next lecture")) or timetable_context
    )
    is_event = intent == "events" if intent is not None else any(
        term in text for term in ("event", "happening", "seminar", "workshop", "registration")
    )
    is_lost_found = intent == "lost_found" if intent is not None else any(
        term in text for term in ("lost", "found", "wallet")
    )
    if is_timetable or timetable_context:
        context_text = " ".join([message.content.casefold() for message in history] + [text])
        user_context = " ".join(
            [message.content.casefold() for message in history if message.role == "user"] + [text]
        )
        department_id = user.department_id
        semester = user.semester
        section = user.section
        if department_id is None:
            for department in db.scalars(select(Department)).all():
                if department.name.casefold() in context_text:
                    department_id = department.id
                    break
        semester_words = {
            "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
            "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12,
        }
        semester_match = re.search(
            r"\b(?:semester\s*)?(1[0-2]|[1-9])(?:st|nd|rd|th)?(?:\s+semester)?\b", context_text
        )
        if semester is None and semester_match:
            semester = int(semester_match.group(1))
        if semester is None:
            for word, value in semester_words.items():
                if re.search(rf"\b{word}(?:\s+semester)?\b", user_context):
                    semester = value
                    break
        section_match = re.search(r"\bsection\s+([a-z0-9-]+)\b", user_context)
        if section is None and section_match:
            section = section_match.group(1).upper()
        if section is None and any(
            message.role == "assistant" and "section" in message.content.casefold() for message in history
        ):
            candidate = payload.message.strip()
            if re.fullmatch(r"[A-Za-z0-9-]{1,24}", candidate):
                section = candidate.upper()
        missing = [
            label for label, value in (
                ("department", department_id), ("semester", semester), ("section", section)
            ) if value is None
        ]
        if missing:
            reply = "Please tell me your " + ", ".join(missing) + " so I can look up the correct timetable."
            needs_clarification = True
        else:
            rows = db.execute(
                select(TimetableEntry, Subject.name, Faculty.name, CampusLocation.name)
                .join(Subject, TimetableEntry.subject_id == Subject.id)
                .outerjoin(Faculty, TimetableEntry.faculty_id == Faculty.id)
                .outerjoin(CampusLocation, TimetableEntry.location_id == CampusLocation.id)
                .where(
                    TimetableEntry.department_id == department_id,
                    TimetableEntry.semester == semester,
                    TimetableEntry.section == section,
                )
                .order_by(TimetableEntry.weekday, TimetableEntry.starts_at)
            ).all()
            if not rows:
                reply = "I couldn't find a timetable matching those details. Please check them with your department."
            else:
                day_names = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
                reply = "Your timetable:\n" + "\n".join(
                    f"- {day_names[entry.weekday]} {entry.starts_at}-{entry.ends_at}: {subject}"
                    + (f" in {location}" if location else "")
                    for entry, subject, _, location in rows
                )
    elif is_event:
        try:
            zone = ZoneInfo(settings.college_timezone)
            now = datetime.now(zone)
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(500, "COLLEGE_TIMEZONE is not a valid timezone") from exc
        event_query = select(Event, CampusLocation.name).outerjoin(
            CampusLocation, Event.location_id == CampusLocation.id
        ).where(Event.published.is_(True), Event.cancelled.is_(False))
        if "today" in text:
            start = _utc_naive(datetime.combine(now.date(), time.min, tzinfo=zone))
            end = _utc_naive(datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=zone))
            event_query = event_query.where(Event.starts_at >= start, Event.starts_at < end)
        else:
            event_query = event_query.where(Event.starts_at >= _utc_naive(now))
        records = db.execute(event_query.order_by(Event.starts_at).limit(10)).all()
        query_terms = {term for term in re.findall(r"[a-z0-9]{3,}", text)
                       if term not in {"where", "what", "when", "which", "event", "events", "happening", "today"}}
        matching = [
            pair for pair in records
            if query_terms & set(re.findall(r"[a-z0-9]{3,}", pair[0].title.casefold()))
        ]
        if matching:
            records = matching
        if not records:
            reply = "There are no matching published events today." if "today" in text else (
                "There are no matching upcoming published events."
            )
        elif "where" in text and len(records) > 1:
            reply = "Which event do you mean? Matching published events are: " + ", ".join(
                event.title for event, _ in records
            )
            needs_clarification = True
        else:
            reply = ("Today's events:\n" if "today" in text else "Upcoming events:\n") + "\n".join(
                f"- {event.title} ({_college_iso(event.starts_at)})"
                + (f" at {location}" if location else "")
                + (f"; hosted by {event.organizer}" if event.organizer else "")
                + ("; registration required" if event.registration_required else "")
                + (f"; register: {event.registration_url}" if event.registration_url else "")
                for event, location in records
            )
    elif is_lost_found:
        reply = "I can help file that. Open Lost & Found, choose LOST or FOUND, and add the item description and location."
    else:
        tokens = {word for word in re.findall(r"[a-z0-9]{3,}", text) if word not in {
            "where", "what", "when", "which", "does", "have", "with", "from", "about", "please"
        }}
        documents = db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.approved.is_(True))).all()
        matches = []
        for document in documents:
            doc_tokens = set(re.findall(r"[a-z0-9]{3,}", (document.title + " " + document.content).casefold()))
            overlap = tokens & doc_tokens
            if overlap:
                matches.append((len(overlap), document))
        if matches:
            _, document = max(matches, key=lambda match: match[0])
            reply = f"According to {document.title} ({document.source}):\n{document.content[:1200]}"
        else:
            reply = "I don't have enough verified information in the college knowledge base to answer that. Please check with the relevant campus office."
    db.add(ChatMessage(conversation_id=conversation.id, role="assistant", content=reply))
    db.commit()
    return ChatResponse(conversation_id=conversation.id, reply=reply, requires_clarification=needs_clarification)


@app.get(f"{API}/chat/conversations")
def conversations(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(ChatConversation).where(ChatConversation.user_id == user.id)
                      .order_by(ChatConversation.created_at.desc())).all()


@app.get(f"{API}/chat/conversations/{{conversation_id}}")
def conversation_detail(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    conversation = db.get(ChatConversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    return db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conversation_id)
                      .order_by(ChatMessage.created_at)).all()


def _validate_image(data: bytes) -> str:
    if not data or len(data) > settings.max_upload_bytes:
        raise HTTPException(413, "Image is empty or exceeds the upload size limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(data))
            if image.width * image.height > 40_000_000:
                raise HTTPException(413, "Image dimensions exceed the allowed limit")
            image.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError) as exc:
        raise HTTPException(415, "Uploaded file is not a valid image") from exc
    if image.format not in {"JPEG", "PNG", "WEBP"}:
        raise HTTPException(415, "Only JPEG, PNG, and WEBP images are accepted")
    return {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[image.format]


@app.post(f"{API}/lost-found/reports", status_code=201)
@limiter.limit("10/hour")
def create_report(request: Request, payload: ReportCreate, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    report = LostFoundReport(report_code=f"CP-{uuid4().hex[:10].upper()}", user_id=user.id, **payload.model_dump())
    db.add(report)
    db.flush()
    admins = db.scalars(select(User).where(User.role == "admin", User.is_active.is_(True))).all()
    db.add_all(Notification(user_id=admin.id, message=f"New Lost & Found report {report.report_code}")
                  for admin in admins)
    db.commit()
    db.refresh(report)
    return {"id": report.id, "report_code": report.report_code, "status": report.status}


@app.get(f"{API}/lost-found/reports")
def list_own_reports(db: Session = Depends(get_db), user: User = Depends(current_user)):
    reports = db.scalars(select(LostFoundReport).where(
        LostFoundReport.user_id == user.id
    ).order_by(LostFoundReport.created_at.desc())).all()
    return [
        {"id": report.id, "report_code": report.report_code, "report_type": report.report_type,
         "description": report.description, "location": report.location, "status": report.status,
         "created_at": report.created_at}
        for report in reports
    ]


@app.post(f"{API}/lost-found/reports/{{report_id}}/images", status_code=201)
@limiter.limit("10/minute")
async def upload_report_image(request: Request, report_id: int, file: UploadFile = File(...),
                              db: Session = Depends(get_db),
                              user: User = Depends(current_user)):
    report = db.get(LostFoundReport, report_id)
    if report is None or (report.user_id != user.id and user.role != "admin"):
        raise HTTPException(404, "Report not found")
    content = await file.read(settings.max_upload_bytes + 1)
    extension = _validate_image(content)
    storage_key = f"{uuid4().hex}{extension}"
    directory = Path(settings.upload_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / storage_key
    target.write_bytes(content)
    db.add(ReportImage(report_id=report.id, storage_key=storage_key))
    db.commit()
    return {"uploaded": True}


@app.get(f"{API}/lost-found/reports/{{report_id}}")
def get_report(report_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    report = db.get(LostFoundReport, report_id)
    if report is None or (report.user_id != user.id and user.role != "admin"):
        raise HTTPException(404, "Report not found")
    return report


@app.get(f"{API}/admin/lost-found/reports")
def admin_reports(status_filter: str | None = None, type_filter: str | None = None,
                  limit: int = 50, offset: int = 0, db: Session = Depends(get_db),
                  admin: User = Depends(admin_user)):
    query = select(LostFoundReport).order_by(LostFoundReport.created_at.desc())
    if status_filter:
        if status_filter not in REPORT_STATUSES:
            raise HTTPException(422, "Unknown report status")
        query = query.where(LostFoundReport.status == status_filter)
    if type_filter:
        if type_filter not in {"LOST", "FOUND"}:
            raise HTTPException(422, "Unknown report type")
        query = query.where(LostFoundReport.report_type == type_filter)
    if limit < 1 or limit > 200 or offset < 0:
        raise HTTPException(422, "Limit must be 1-200 and offset must be non-negative")
    return db.scalars(query.offset(offset).limit(limit)).all()


@app.patch(f"{API}/admin/lost-found/reports/{{report_id}}")
def update_report(report_id: int, payload: ReportStatusUpdate, db: Session = Depends(get_db),
                  admin: User = Depends(admin_user)):
    report = db.get(LostFoundReport, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    report.status = payload.status
    db.add(AuditLog(actor_id=admin.id, action="lost_found.status_changed",
                    entity="lost_found_report", entity_id=str(report.id)))
    db.commit()
    return {"id": report.id, "report_code": report.report_code, "status": report.status}


@app.get(f"{API}/admin/lost-found/reports/{{report_id}}/images/{{image_id}}")
def admin_report_image(report_id: int, image_id: int, db: Session = Depends(get_db),
                       admin: User = Depends(admin_user)):
    image = db.scalar(select(ReportImage).where(
        ReportImage.id == image_id, ReportImage.report_id == report_id
    ))
    if image is None:
        raise HTTPException(404, "Image not found")
    path = Path(settings.upload_dir).resolve() / Path(image.storage_key).name
    if not path.is_file():
        raise HTTPException(404, "Image file not found")
    return FileResponse(path)


@app.websocket(f"{API}/notifications/ws")
async def notifications_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        token = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        try:
            subject = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM]).get("sub")
            user_id = int(subject)
        except (JWTError, TypeError, ValueError):
            await websocket.close(code=1008, reason="Invalid access token")
            return
        while True:
            with SessionLocal() as db:
                user = db.get(User, user_id)
                if user is None or not user.is_active:
                    await websocket.close(code=1008, reason="Account unavailable")
                    return
                notifications = db.scalars(select(Notification).where(
                    Notification.user_id == user_id, Notification.read.is_(False)
                ).order_by(Notification.created_at)).all()
                for item in notifications:
                    await websocket.send_json({
                        "id": item.id, "message": item.message, "created_at": item.created_at.isoformat()
                    })
                    item.read = True
                if notifications:
                    db.commit()
            await asyncio.sleep(3)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        return
