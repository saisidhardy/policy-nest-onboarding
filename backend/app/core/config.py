from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PolicyNest"
    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"

    database_url: str
    secret_key: str = Field(min_length=32)

    public_app_url: str = "http://localhost:3000"
    allowed_origins: str = "http://localhost:3000"
    trust_proxy_headers: bool = False

    session_cookie_name: str = "pn_session"
    csrf_cookie_name: str = "pn_csrf"
    session_idle_minutes: int = 120
    session_absolute_hours: int = 12
    cookie_secure: bool | None = None

    require_email_verification: bool = True
    login_max_failures: int = 5
    login_lockout_minutes: int = 15
    email_verify_ttl_hours: int = 24
    password_reset_ttl_minutes: int = 30
    invite_ttl_hours: int = 72
    email_resend_cooldown_seconds: int = 60
    exam_max_attempts: int = Field(default=3, ge=1, le=10)
    exam_retake_cooldown_hours: int = Field(default=24, ge=0, le=168)

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_seconds: int = 10
    email_from: str | None = None

    @property
    def origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def secure_cookies(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.app_env == "production"

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.email_from)

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.app_env == "production":
            if "change" in self.secret_key.lower() or len(set(self.secret_key)) < 10:
                raise ValueError("SECRET_KEY must be a strong random value in production")
            if self.cookie_secure is False:
                raise ValueError("COOKIE_SECURE cannot be disabled in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
