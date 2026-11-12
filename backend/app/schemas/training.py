"""Phase 6 schemas for LMS training eligibility, progress sync, exam, certification, and retries."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _OrmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CurriculumModuleProgressOut(BaseModel):
    code: str
    title: str
    required_hours: float
    logged_hours: float = 0.0
    completed: bool = False


class LmsAdapterStatusOut(BaseModel):
    key: str = "lms"
    name: str = "LMS training & certification sync"
    provider: str
    status: str  # CONFIGURED | DEGRADED | NOT_CONFIGURED
    mode: str  # LIVE | SANDBOX | NONE
    webhook_configured: bool
    detail: str


class LmsSyncLogOut(_OrmOut):
    id: uuid.UUID
    operation: str
    provider_name: str
    adapter_origin: str
    is_simulated: bool
    attempt_number: int
    outcome: str
    http_status: int | None
    error_code: str | None
    error_message: str | None
    occurred_at: datetime


class TrainingRecordOut(_OrmOut):
    id: uuid.UUID
    application_id: uuid.UUID
    reference_code: str | None = None
    applicant_name: str | None = None
    application_status: str | None = None

    eligibility_status: str
    eligibility_reason: str | None
    lms_provider: str
    is_simulated: bool
    external_enrollment_id: str | None
    lms_launch_url: str | None

    enrollment_status: str
    required_hours: float
    completed_hours: float
    progress_pct: float
    module_progress: list[CurriculumModuleProgressOut]

    enrolled_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None

    exam_status: str
    exam_score_pct: float | None
    exam_attempts: int
    last_exam_at: datetime | None
    next_exam_eligible_at: datetime | None

    certification_status: str
    certificate_number: str | None
    certified_at: datetime | None
    certificate_valid_until: datetime | None

    sync_status: str
    sync_attempts: int
    max_sync_attempts: int
    last_sync_at: datetime | None
    next_retry_at: datetime | None
    last_error_code: str | None
    last_error_message: str | None

    updated_at: datetime
    adapter_status: LmsAdapterStatusOut
    sync_logs: list[LmsSyncLogOut] = Field(default_factory=list)


class TrainingSyncRequest(BaseModel):
    sandbox_action: Literal["ADVANCE_7_5H", "COMPLETE_15H", "PASS_EXAM", "FAIL_EXAM", "SIMULATE_SYNC_ERROR"] | None = (
        None
    )


class LmsWebhookPayload(BaseModel):
    event_id: str | None = Field(default=None, max_length=120)
    external_enrollment_id: str | None = Field(default=None, max_length=120)
    reference_code: str | None = Field(default=None, max_length=32)
    enrollment_status: Literal["ENROLLED", "IN_PROGRESS", "COMPLETED"] | None = None
    completed_hours: float | None = Field(default=None, ge=0.0, le=100.0)
    module_progress: list[CurriculumModuleProgressOut] | None = None
    exam_status: (
        Literal["NOT_ELIGIBLE", "ELIGIBLE", "SCHEDULED", "IN_PROGRESS", "PASSED", "FAILED", "COOLDOWN"] | None
    ) = None
    exam_score_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    exam_attempts: int | None = Field(default=None, ge=0, le=100)
    certificate_number: str | None = Field(default=None, max_length=64)
    certified_at: datetime | None = None


class TrainingQueueItemOut(BaseModel):
    application_id: uuid.UUID
    reference_code: str
    applicant_name: str | None
    region: str | None
    application_status: str
    eligibility_status: str
    enrollment_status: str
    completed_hours: float
    required_hours: float
    progress_pct: float
    exam_status: str
    exam_score_pct: float | None
    certification_status: str
    certificate_number: str | None
    sync_status: str
    sync_attempts: int
    next_retry_at: datetime | None
    last_error_code: str | None
    last_error_message: str | None
    is_simulated: bool
    updated_at: datetime


class TrainingOverviewOut(BaseModel):
    adapter_status: LmsAdapterStatusOut
    kyc_approved_awaiting_training: int
    training_in_progress_count: int
    training_completed_awaiting_exam: int
    certified_count: int
    sync_retry_pending_count: int
    sync_error_count: int
    items: list[TrainingQueueItemOut]
    total: int
    page: int
    page_size: int
    pages: int


class BatchRetryOut(BaseModel):
    attempted: int
    succeeded: int
    failed: int
    message: str
