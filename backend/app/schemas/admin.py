import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.rbac.catalog import REGIONS, RoleCode
from app.schemas.auth import UserOut, normalize_name

RegionLiteral = Literal["NORTH", "SOUTH", "EAST", "WEST", "ALL"]


class AdminUserOut(UserOut):
    locked_until: datetime | None
    failed_login_count: int
    invitation_pending: bool


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(max_length=200)
    role: RoleCode
    region: RegionLiteral | None = None
    clearance_level: int = Field(default=1, ge=1, le=3)

    _name = field_validator("full_name")(normalize_name)


class UpdateUserRequest(BaseModel):
    role: RoleCode | None = None
    is_active: bool | None = None
    region: RegionLiteral | None = None
    clearance_level: int | None = Field(default=None, ge=1, le=3)
    clear_region: bool = False


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    category: str
    description: str


class RoleDetailOut(BaseModel):
    code: str
    name: str
    description: str
    is_staff: bool
    user_count: int
    permissions: list[str]


class RolesMatrixOut(BaseModel):
    roles: list[RoleDetailOut]
    permissions: list[PermissionOut]
    regions: list[str] = REGIONS


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    occurred_at: datetime
    actor_user_id: uuid.UUID | None
    actor_email: str | None
    actor_role: str | None
    action: str
    outcome: str
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    request_id: str | None
    details: dict[str, Any]


class IntegrationStatus(BaseModel):
    key: str
    name: str
    status: Literal["CONFIGURED", "NOT_CONFIGURED", "DEGRADED"]
    mode: Literal["LIVE", "LOCAL_DEVELOPMENT", "SANDBOX", "NONE"]
    detail: str


class SystemHealthOut(BaseModel):
    status: str
    app_env: str
    version: str
    database: dict[str, Any]
    integrations: list[IntegrationStatus]
    email_deliveries_last_24h: dict[str, int]


class AdminStatsOut(BaseModel):
    users_by_role: dict[str, int]
    active_users: int
    inactive_users: int
    unverified_users: int
    pending_invitations: int
    active_sessions: int
    registrations_last_7_days: int
    failed_logins_last_24h: int
    recent_audit: list[AuditLogOut]


class AdminDashboardOut(BaseModel):
    stats: AdminStatsOut
    total_applications: int
    applications_by_status: dict[str, int]
    escalated_applications: int
    training_certified_count: int
    training_sync_failed_count: int
    integrations: list[IntegrationStatus]
    reviewer_count: int
    senior_reviewer_count: int


class ReviewerWorkloadOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: RoleCode
    region: str | None
    clearance_level: int
    is_active: bool
    email_verified: bool
    active_assigned_count: int
    escalated_assigned_count: int
    decisions_made_count: int
    overrides_count: int
    corrections_requested_count: int
    last_login_at: datetime | None


class ReassignWorkloadRequest(BaseModel):
    target_reviewer_id: uuid.UUID | None = None
    reason: str = Field(min_length=5, max_length=500)


class ReassignWorkloadOut(BaseModel):
    source_reviewer_id: uuid.UUID
    target_reviewer_id: uuid.UUID | None
    reassigned_count: int


class AdminApplicationItemOut(BaseModel):
    id: uuid.UUID
    reference_code: str
    applicant_id: uuid.UUID
    applicant_name: str
    applicant_email: str
    status: str
    region: str | None
    assigned_reviewer_id: uuid.UUID | None
    assigned_reviewer_name: str | None
    assigned_reviewer_email: str | None
    is_escalated: bool
    fraud_flag: bool
    training_status: str | None
    submitted_at: datetime | None
    updated_at: datetime


class AdminApplicationPageOut(BaseModel):
    items: list[AdminApplicationItemOut]
    total: int
    page: int
    page_size: int
    counts_by_status: dict[str, int]


class AdminAssignReviewerRequest(BaseModel):
    reviewer_id: uuid.UUID | None = None
    reason: str = Field(min_length=5, max_length=500)


class UpdateRolePermissionsRequest(BaseModel):
    permission_codes: list[str]
    reason: str = Field(min_length=5, max_length=500)


class LmsConfigOut(BaseModel):
    lms_provider: str
    lms_api_base_url: str | None
    lms_course_code: str
    lms_required_hours: float
    lms_passing_score_pct: float
    lms_timeout_seconds: int
    lms_exam_cooldown_hours: int
    lms_certificate_validity_years: int
    lms_sync_retry_base_seconds: int
    lms_sync_max_attempts: int
    has_api_key: bool
    api_key_hint: str | None
    has_webhook_secret: bool
    webhook_secret_hint: str | None
    source: str
    updated_at: datetime | None


class UpdateLmsConfigRequest(BaseModel):
    lms_provider: Literal["not_configured", "sandbox", "http_api"]
    lms_api_base_url: str | None = Field(default=None, max_length=500)
    lms_course_code: str = Field(min_length=2, max_length=120)
    lms_required_hours: float = Field(ge=1.0, le=100.0)
    lms_passing_score_pct: float = Field(ge=1.0, le=100.0)
    lms_timeout_seconds: int = Field(ge=2, le=120)
    lms_exam_cooldown_hours: int = Field(ge=0, le=168)
    lms_certificate_validity_years: int = Field(ge=1, le=20)
    lms_sync_retry_base_seconds: int = Field(ge=10, le=3600)
    lms_sync_max_attempts: int = Field(ge=1, le=10)
    lms_api_key: str | None = Field(default=None, max_length=500)
    clear_api_key: bool = False
    lms_webhook_secret: str | None = Field(default=None, max_length=500)
    clear_webhook_secret: bool = False


class IntegrationsConfigOut(BaseModel):
    ocr_provider: str
    ocr_api_base_url: str | None
    has_ocr_api_key: bool
    ocr_api_key_hint: str | None
    ai_provider: str
    gemini_model: str
    has_gemini_api_key: bool
    gemini_api_key_hint: str | None
    ifsc_lookup_enabled: bool
    pan_verification_provider: str
    pan_api_base_url: str | None
    has_pan_api_key: bool
    pan_api_key_hint: str | None
    bank_verification_provider: str
    bank_api_base_url: str | None
    has_bank_api_key: bool
    bank_api_key_hint: str | None
    digilocker_provider: str
    digilocker_base_url: str | None
    digilocker_client_id: str | None
    has_digilocker_client_secret: bool
    digilocker_client_secret_hint: str | None
    face_match_provider: str
    face_api_base_url: str | None
    has_face_api_key: bool
    face_api_key_hint: str | None
    sms_provider: str
    sms_api_base_url: str | None
    sms_sender_id: str | None
    sms_timeout_seconds: int
    sms_max_attempts: int
    has_sms_api_key: bool
    sms_api_key_hint: str | None
    has_webhook_shared_secret: bool
    webhook_shared_secret_hint: str | None
    integration_http_timeout_seconds: int
    integration_http_max_retries: int
    source: str
    updated_at: datetime | None


class UpdateIntegrationsConfigRequest(BaseModel):
    ocr_provider: Literal["local_tesseract", "http_ocr", "none"]
    ocr_api_base_url: str | None = Field(default=None, max_length=500)
    ocr_api_key: str | None = Field(default=None, max_length=500)
    clear_ocr_api_key: bool = False
    ai_provider: Literal["local_heuristic", "gemini"]
    gemini_model: str = Field(default="gemini-3.8-flash", min_length=2, max_length=120)
    gemini_api_key: str | None = Field(default=None, max_length=500)
    clear_gemini_api_key: bool = False
    ifsc_lookup_enabled: bool = True
    pan_verification_provider: Literal["not_configured", "sandbox", "protean", "cashfree"]
    pan_api_base_url: str | None = Field(default=None, max_length=500)
    pan_api_key: str | None = Field(default=None, max_length=500)
    clear_pan_api_key: bool = False
    bank_verification_provider: Literal["not_configured", "sandbox", "razorpayx", "cashfree"]
    bank_api_base_url: str | None = Field(default=None, max_length=500)
    bank_api_key: str | None = Field(default=None, max_length=500)
    clear_bank_api_key: bool = False
    digilocker_provider: Literal["not_configured", "sandbox", "negd_oauth"]
    digilocker_base_url: str | None = Field(default=None, max_length=500)
    digilocker_client_id: str | None = Field(default=None, max_length=200)
    digilocker_client_secret: str | None = Field(default=None, max_length=500)
    clear_digilocker_client_secret: bool = False
    face_match_provider: Literal["not_configured", "sandbox", "aws_rekognition"]
    face_api_base_url: str | None = Field(default=None, max_length=500)
    face_api_key: str | None = Field(default=None, max_length=500)
    clear_face_api_key: bool = False
    sms_provider: Literal["not_configured", "sandbox", "twilio", "msg91", "webhook_http"] = "not_configured"
    sms_api_base_url: str | None = Field(default=None, max_length=500)
    sms_sender_id: str | None = Field(default=None, max_length=32)
    sms_timeout_seconds: int = Field(default=8, ge=2, le=60)
    sms_max_attempts: int = Field(default=3, ge=1, le=5)
    sms_api_key: str | None = Field(default=None, max_length=500)
    clear_sms_api_key: bool = False
    webhook_shared_secret: str | None = Field(default=None, max_length=500)
    clear_webhook_shared_secret: bool = False
    integration_http_timeout_seconds: int = Field(default=8, ge=2, le=60)
    integration_http_max_retries: int = Field(default=2, ge=0, le=5)


class PlatformConfigOut(BaseModel):
    public_app_url: str
    require_email_verification: bool
    session_idle_minutes: int
    login_max_failures: int
    login_lockout_minutes: int
    max_upload_size_mb: int
    source: str
    updated_at: datetime | None


class UpdatePlatformConfigRequest(BaseModel):
    public_app_url: str = Field(min_length=4, max_length=300)
    require_email_verification: bool
    session_idle_minutes: int = Field(ge=5, le=1440)
    login_max_failures: int = Field(ge=3, le=20)
    login_lockout_minutes: int = Field(ge=1, le=240)
    max_upload_size_mb: int = Field(ge=1, le=50)


class AdminConfigBundleOut(BaseModel):
    lms: LmsConfigOut
    integrations: IntegrationsConfigOut
    platform: PlatformConfigOut
    integrations_health: list[IntegrationStatus]


class IntegrationProbeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    adapter_key: str
    status: str
    mode: str
    latency_ms: int | None
    http_status: int | None
    detail: str
    checked_at: datetime


class EmailDeliveryMonitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    recipient: str
    template: str
    subject: str
    status: str
    provider: str
    attempts: int
    error: str | None
    created_at: datetime
    sent_at: datetime | None


class SmsDeliveryMonitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    application_id: uuid.UUID | None
    recipient_mobile: str
    event_type: str
    provider: str
    status: str
    is_simulated: bool
    provider_message_id: str | None
    attempts: int
    error: str | None
    created_at: datetime
    sent_at: datetime | None


class WebhookDeliveryMonitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source: str
    external_event_id: str | None
    signature_valid: bool
    processing_status: str
    application_id: uuid.UUID | None
    error_message: str | None
    received_at: datetime
    processed_at: datetime | None


class IntegrationsMonitorOut(BaseModel):
    probes: list[IntegrationProbeOut]
    email_deliveries: list[EmailDeliveryMonitorOut]
    sms_deliveries: list[SmsDeliveryMonitorOut]
    webhook_deliveries: list[WebhookDeliveryMonitorOut]


class SmsRetryOut(BaseModel):
    attempted: int
    succeeded: int
    failed: int
