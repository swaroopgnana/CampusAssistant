from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./campus_pilot.db"
    jwt_secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    frontend_origin: str = "http://localhost:5173"
    upload_dir: str = "./private_uploads"
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1, le=25 * 1024 * 1024)
    college_timezone: str = "Asia/Kolkata"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def empty_ai_key_is_unset(cls, value: str | None) -> str | None:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("college_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("COLLEGE_TIMEZONE must be a valid IANA timezone") from exc
        return value


settings = Settings()
