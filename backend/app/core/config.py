from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PolicyNest"
    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.3.0"

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

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_seconds: int = 10
    email_from: str | None = None
    resend_api_key: str | None = None

    storage_provider: Literal["local", "s3"] = "local"
    storage_local_dir: str = "./storage"
    max_upload_size_mb: int = 10
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "ap-south-1"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    redis_url: str | None = None

    # Enterprise Observability & Reviewer Queue SLA Alerting
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1
    sla_review_unassigned_threshold_minutes: int = 30
    sla_alert_webhook_url: str | None = None

    # Phase 8: Outbound transport, SMS & webhook hardening
    email_max_attempts: int = 3
    integration_http_timeout_seconds: int = 8
    integration_http_max_retries: int = 2
    webhook_shared_secret: str | None = None

    sms_provider: Literal["not_configured", "sandbox", "twilio", "msg91", "webhook_http"] = "not_configured"
    sms_api_base_url: str | None = None
    sms_api_key: str | None = None
    sms_sender_id: str | None = None
    sms_timeout_seconds: int = 8
    sms_max_attempts: int = 3

    # Phase 3 & 8: Document intelligence, AI assistance, and external verification adapters
    ocr_provider: Literal["local_tesseract", "http_ocr", "none"] = "local_tesseract"
    ocr_api_base_url: str | None = None
    ocr_api_key: str | None = None
    tesseract_cmd: str | None = None
    ai_provider: Literal["local_heuristic", "gemini"] = "local_heuristic"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"

    ifsc_lookup_enabled: bool = True
    pan_verification_provider: Literal["not_configured", "sandbox", "protean", "cashfree"] = "not_configured"
    pan_api_base_url: str | None = None
    pan_api_key: str | None = None
    bank_verification_provider: Literal["not_configured", "sandbox", "razorpayx", "cashfree"] = "not_configured"
    bank_api_base_url: str | None = None
    bank_api_key: str | None = None
    digilocker_provider: Literal["not_configured", "sandbox", "negd_oauth"] = "not_configured"
    digilocker_base_url: str | None = None
    digilocker_client_id: str | None = None
    digilocker_client_secret: str | None = None
    face_match_provider: Literal["not_configured", "sandbox", "aws_rekognition"] = "not_configured"
    face_api_base_url: str | None = None
    face_api_key: str | None = None

    # Phase 6: External LMS training & POSP certification integration adapter
    lms_provider: Literal["not_configured", "sandbox", "http_api"] = "not_configured"
    lms_api_base_url: str | None = None
    lms_api_key: str | None = None
    lms_webhook_secret: str | None = None
    lms_timeout_seconds: int = 8
    lms_course_code: str = "IRDAI-POSP-15H"
    lms_required_hours: float = 15.0
    lms_passing_score_pct: float = 50.0
    lms_exam_cooldown_hours: int = 24
    lms_certificate_validity_years: int = 3
    lms_sync_retry_base_seconds: int = 300
    lms_sync_max_attempts: int = 5

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

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
        return bool(self.email_from and (self.smtp_host or self.resend_api_key))

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def s3_configured(self) -> bool:
        return bool(self.s3_bucket and (self.s3_access_key_id and self.s3_secret_access_key))

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.app_env == "production":
            if "change" in self.secret_key.lower() or len(set(self.secret_key)) < 10:
                raise ValueError("SECRET_KEY must be a strong random value in production")
            if self.cookie_secure is False:
                raise ValueError("COOKIE_SECURE cannot be disabled in production")
            if self.storage_provider == "s3" and not self.s3_bucket:
                raise ValueError("S3_BUCKET must be configured when STORAGE_PROVIDER=s3 in production")
            for field_name in (
                "pan_verification_provider",
                "bank_verification_provider",
                "digilocker_provider",
                "face_match_provider",
                "lms_provider",
                "sms_provider",
            ):
                if getattr(self, field_name) == "sandbox":
                    raise ValueError(f"{field_name.upper()}=sandbox is forbidden in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
