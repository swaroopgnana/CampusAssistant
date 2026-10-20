from collections.abc import Generator
from datetime import datetime
from io import BytesIO
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-long-enough-for-validation"
os.environ["OPENAI_API_KEY"] = ""

from PIL import Image

from app.database import Base, get_db
from app.main import app
from app.models import (
    AcademicSection, CampusLocation, CampusPath, Department, Event, Subject, TimetableEntry, User,
)
from app.config import settings
from app.security import create_access_token, hash_password


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def register(client: TestClient, email: str = "student@example.edu") -> str:
    response = client.post("/api/v1/auth/register", json={
        "email": email,
        "full_name": "Test Student",
        "password": "a-strong-password",
    })
    assert response.status_code == 201
    return response.json()["access_token"]


def test_authentication_and_profile(client: TestClient) -> None:
    token = register(client)
    login_response = client.post("/api/v1/auth/login", data={
        "username": "student@example.edu",
        "password": "a-strong-password",
    })
    assert login_response.status_code == 200
    assert login_response.json()["token_type"] == "bearer"
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "student@example.edu"
    assert "password_hash" not in response.json()
    assert client.get("/api/v1/auth/me").status_code == 401
    student_headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/admin/overview", headers=student_headers).status_code == 403


def test_timetable_clarification_uses_conversation_context(client: TestClient) -> None:
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    from app.database import get_db

    override = app.dependency_overrides[get_db]
    generator = override()
    db: Session = next(generator)
    department = Department(name="Computer Science and Engineering")
    subject = Subject(code="CS101", name="Algorithms")
    db.add_all([department, subject])
    db.flush()
    db.add(TimetableEntry(
        department_id=department.id, semester=5, section="A",
        subject_id=subject.id, weekday=0, starts_at="09:00", ends_at="10:00",
    ))
    db.commit()
    db.close()
    generator.close()

    conversation_id = None
    prompts = [
        ("Show my timetable", "department"),
        ("Computer Science and Engineering", "semester"),
        ("5th semester", "section"),
        ("section A", "Algorithms"),
    ]
    for message, expected in prompts:
        response = client.post("/api/v1/chat/message", headers=headers, json={
            "message": message,
            "conversation_id": conversation_id,
        })
        assert response.status_code == 200
        body = response.json()
        conversation_id = body["conversation_id"]
        assert expected.casefold() in body["reply"].casefold()


def test_navigation_requires_an_entered_path(client: TestClient) -> None:
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    from app.database import get_db

    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    first = CampusLocation(name="Library", latitude=10.0, longitude=20.0)
    second = CampusLocation(name="Hall", latitude=10.1, longitude=20.1)
    third = CampusLocation(name="Auditorium", latitude=10.2, longitude=20.2)
    admin = User(
        email="routes-admin@example.edu",
        full_name="Routes Admin",
        password_hash=hash_password("an-admin-password"),
        role="admin",
    )
    db.add_all([first, second, third, admin])
    db.commit()
    first_id, second_id, third_id, admin_id = first.id, second.id, third.id, admin.id
    db.close()
    generator.close()
    response = client.post(
        "/api/v1/navigation/route",
        params={"origin_id": first_id, "destination_id": third_id},
        headers=headers,
    )
    assert response.status_code == 404
    assert "No mapped campus pathway" in response.json()["detail"]
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    db.add_all([
        CampusPath(from_location_id=first_id, to_location_id=second_id, distance_meters=350),
        CampusPath(from_location_id=first_id, to_location_id=third_id, distance_meters=500),
        CampusPath(from_location_id=third_id, to_location_id=second_id, distance_meters=100),
    ])
    db.commit()
    db.close()
    generator.close()
    response = client.post(
        "/api/v1/navigation/route",
        params={"origin_id": first_id, "destination_id": third_id},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["distance_meters"] == 450
    assert response.json()["locations"][0]["name"] == "Library"
    assert response.json()["locations"][1]["name"] == "Hall"
    assert response.json()["locations"][-1]["name"] == "Auditorium"
    assert response.json()["estimated_walking_minutes"] == 6
    admin_headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}
    paths = client.get("/api/v1/admin/campus/paths", headers=admin_headers)
    assert paths.status_code == 200
    assert any(path["from_location"] == "Library" and path["to_location"] == "Hall"
               for path in paths.json())


def test_profile_and_timetable_use_configured_section(client: TestClient) -> None:
    token = register(client)
    generator = app.dependency_overrides[get_db]()
    db: Session = next(generator)
    department = Department(name="Computer Science")
    subject = Subject(code="CS101", name="Algorithms")
    db.add_all([department, subject])
    db.flush()
    db.add(AcademicSection(department_id=department.id, semester=5, section="A"))
    db.add(TimetableEntry(
        department_id=department.id, semester=5, section="A",
        subject_id=subject.id, weekday=0, starts_at="09:00", ends_at="10:00",
    ))
    department_id = department.id
    db.commit()
    db.close()
    generator.close()
    headers = {"Authorization": f"Bearer {token}"}
    response = client.patch("/api/v1/auth/me/profile", headers=headers, json={
        "department_id": department_id,
        "semester": 5,
        "section": "a",
    })
    assert response.status_code == 200
    assert response.json()["section"] == "A"
    schedule = client.get("/api/v1/timetable", headers=headers)
    assert schedule.status_code == 200
    assert schedule.json()[0]["subject"] == "Algorithms"


def test_only_verified_and_published_events_are_visible(client: TestClient) -> None:
    generator = app.dependency_overrides[get_db]()
    db: Session = next(generator)
    admin = User(
        email="admin@example.edu",
        full_name="Campus Admin",
        password_hash=hash_password("an-admin-password"),
        role="admin",
    )
    location = CampusLocation(name="Main Hall")
    db.add_all([admin, location])
    db.flush()
    db.add(Event(
        title="Published seminar",
        starts_at=datetime(2030, 2, 1, 2, 30),
        location_id=location.id,
        published=True,
    ))
    db.add(Event(
        title="Draft seminar",
        starts_at=datetime(2030, 2, 1, 3, 30),
        location_id=location.id,
        published=False,
    ))
    admin_id = admin.id
    db.commit()
    db.close()
    generator.close()
    response = client.get("/api/v1/events", params={"date_filter": "2030-02-01"})
    assert response.status_code == 200, response.text
    assert [event["title"] for event in response.json()] == ["Published seminar"]
    assert response.json()[0]["location"] == "Main Hall"
    assert response.json()[0]["timezone"] == "Asia/Kolkata"
    headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}
    assert client.get("/api/v1/admin/overview", headers=headers).status_code == 200


def test_image_upload_validation_and_private_storage(client: TestClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    report = client.post("/api/v1/lost-found/reports", headers=headers, json={
        "report_type": "FOUND",
        "description": "A blue notebook",
        "location": "Library",
    })
    assert report.status_code == 201
    response = client.post(
        f"/api/v1/lost-found/reports/{report.json()['id']}/images",
        headers=headers,
        files={"file": ("photo.png", b"not an image", "image/png")},
    )
    assert response.status_code == 415
    image_data = BytesIO()
    Image.new("RGB", (16, 16), color="teal").save(image_data, format="PNG")
    response = client.post(
        f"/api/v1/lost-found/reports/{report.json()['id']}/images",
        headers=headers,
        files={"file": ("photo.png", image_data.getvalue(), "image/png")},
    )
    assert response.status_code == 201
    saved_files = list(tmp_path.iterdir())
    assert len(saved_files) == 1
    assert saved_files[0].suffix == ".png"


def test_report_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/lost-found/reports", json={
        "report_type": "FOUND",
        "description": "A blue notebook",
        "location": "Library",
    })
    assert response.status_code == 401
