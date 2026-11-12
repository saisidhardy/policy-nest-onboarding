import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApplicationPatch(BaseModel):
    current_step: int = Field(ge=0, le=5)
    date_of_birth: date | None = None
    pan_number: str | None = Field(default=None, min_length=10, max_length=10)
    aadhaar_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    region: str | None = Field(default=None, min_length=2, max_length=32)
    address: dict[str, Any] | None = None
    education: dict[str, Any] | None = None
    bank_details: dict[str, Any] | None = None
    declarations: dict[str, Any] | None = None

    @field_validator("pan_number")
    @classmethod
    def uppercase_pan(cls, value: str | None) -> str | None:
        return value.upper().strip() if value else value


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_type: str
    version: int
    filename: str
    content_type: str
    byte_size: int
    sha256: str
    status: str
    quality_result: dict[str, Any]
    extracted_fields: dict[str, Any]
    uploaded_at: datetime


class VerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    verification_type: str
    provider: str
    environment: str
    status: str
    result: dict[str, Any]
    requested_at: datetime
    completed_at: datetime | None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    applicant_id: uuid.UUID
    reference: str
    status: str
    current_step: int
    region: str | None
    sensitivity: int
    date_of_birth: date | None
    pan_number: str | None
    aadhaar_last4: str | None
    address: dict[str, Any]
    education: dict[str, Any]
    bank_details: dict[str, Any]
    declarations: dict[str, Any]
    rule_result: dict[str, Any]
    submitted_at: datetime | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime
    documents: list[DocumentOut] = []
    verifications: list[VerificationOut] = []
    applicant_name: str | None = None
    applicant_email: str | None = None


class VerificationRequestIn(BaseModel):
    verification_type: Literal["PAN", "BANK", "DIGILOCKER", "FACE_MATCH"]
    consent: bool


class ReviewActionIn(BaseModel):
    action: Literal["ASSIGN_TO_ME", "REQUEST_CORRECTION", "APPROVE_KYC", "REJECT", "ESCALATE"]
    justification: str = Field(min_length=10, max_length=2000)
    issues: list[dict[str, str]] = Field(default_factory=list, max_length=20)


class TrainingUpdateIn(BaseModel):
    minutes_completed: int = Field(ge=0, le=900)


class ExamSubmitIn(BaseModel):
    answers: dict[str, int]


class ExamQuestionOut(BaseModel):
    id: str
    category: str
    prompt: str
    options: list[str]


class ExamAttemptOut(BaseModel):
    id: uuid.UUID
    attempt_number: int
    questions: list[ExamQuestionOut]
    started_at: datetime


class TrainingModuleOut(BaseModel):
    code: str
    title: str
    required_minutes: int
    minutes_completed: int
    completed: bool


class OperationsSummary(BaseModel):
    total_applications: int
    by_status: dict[str, int]
    submitted_last_30_days: int
    average_review_hours: float | None
    pending_review: int
    corrections_open: int
    certificates_issued: int
    verification_statuses: dict[str, int]
