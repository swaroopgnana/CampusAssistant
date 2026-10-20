from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=10, max_length=72)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Full name cannot be empty")
        return name


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    department_id: int | None
    semester: int | None
    section: str | None

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    department_id: int | None = None
    semester: int | None = Field(default=None, ge=1, le=12)
    section: str | None = Field(default=None, min_length=1, max_length=24)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str
    requires_clarification: bool = False


class ReportCreate(BaseModel):
    report_type: Literal["LOST", "FOUND"]
    description: str = Field(min_length=3, max_length=4000)
    location: str = Field(min_length=2, max_length=200)
    occurred_at: datetime | None = None


class ReportStatusUpdate(BaseModel):
    status: Literal["SUBMITTED", "UNDER_REVIEW", "MATCHED", "READY_FOR_COLLECTION", "RESOLVED"]


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    starts_at: datetime
    ends_at: datetime | None = None
    location_id: int | None = None
    organizer: str | None = None
    registration_url: str | None = None
    registration_required: bool = False
    department_id: int | None = None
    published: bool = False

    @field_validator("registration_url")
    @classmethod
    def validate_registration_url(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Registration links must use HTTP or HTTPS")
        return value


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location_id: int | None = None
    organizer: str | None = None
    registration_url: str | None = None
    registration_required: bool | None = None
    department_id: int | None = None
    published: bool | None = None
    cancelled: bool | None = None

    @field_validator("registration_url")
    @classmethod
    def validate_registration_url(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Registration links must use HTTP or HTTPS")
        return value


class NewsCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=48)
    description: str = Field(min_length=1)
    source: str = Field(min_length=1, max_length=200)
    published: bool = False


class NewsUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=48)
    description: str | None = Field(default=None, min_length=1)
    source: str | None = Field(default=None, min_length=1, max_length=200)
    published: bool | None = None


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class BuildingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None


class SubjectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=160)


class FacultyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr | None = None
    department_id: int | None = None


class AcademicSectionCreate(BaseModel):
    department_id: int
    semester: int = Field(ge=1, le=12)
    section: str = Field(min_length=1, max_length=24)


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    building_id: int | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    description: str | None = None


class PathCreate(BaseModel):
    from_location_id: int
    to_location_id: int
    distance_meters: int = Field(gt=0)
    accessible: bool = True


class TimetableCreate(BaseModel):
    department_id: int
    semester: int = Field(ge=1, le=12)
    section: str = Field(min_length=1, max_length=24)
    subject_id: int
    faculty_id: int | None = None
    weekday: int = Field(ge=0, le=6)
    starts_at: str = Field(pattern=r"^\d{2}:\d{2}$")
    ends_at: str = Field(pattern=r"^\d{2}:\d{2}$")
    location_id: int | None = None


class RoleUpdate(BaseModel):
    role: Literal["student", "faculty", "admin"]


class KnowledgeDocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1)
