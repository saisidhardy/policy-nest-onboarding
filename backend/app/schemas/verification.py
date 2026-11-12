import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.ocr_pipeline import normalize_date_str, normalize_person_name

AADHAAR_FULL_DIGITS_RE = re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")
RAW_12_DIGITS_RE = re.compile(r"\d{12,}")

ALLOWED_CORRECTION_FIELDS = {
    "full_name",
    "dob",
    "pan_number",
    "aadhaar_last4",
    "pincode",
    "address_or_pincode",
    "board_name",
    "result_status",
    "roll_number",
    "passing_year",
    "ifsc_code",
    "account_last4",
    "bank_name",
    "face_detected",
}


class DocumentExtractionOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    doc_type: str
    application_id: uuid.UUID
    ocr_engine: str
    ai_assistant_provider: str

    predicted_doc_type: str | None
    classification_confidence: float | None
    classification_match: bool | None

    quality_status: str
    blur_score: float | None
    glare_ratio: float | None
    edge_clip_ratio: float | None
    face_detected: bool | None
    ocr_confidence: float | None

    raw_ocr_text_masked: str | None
    extracted_fields: dict[str, Any]
    missing_fields: list[str]
    ai_explanation: str | None

    aadhaar_masked_applied: bool
    has_redacted_image: bool

    reviewer_corrected_fields: dict[str, Any] | None
    effective_fields: dict[str, Any]
    corrected_by_user_id: uuid.UUID | None
    corrected_at: datetime | None
    processed_at: datetime


class VerificationCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    check_type: str
    target_doc_type: str | None
    status: str
    origin: str
    provider_name: str | None
    provider_reference: str | None
    is_simulated: bool
    confidence: float | None
    details: dict[str, Any]
    explanation: str | None
    checked_at: datetime


class FieldCorrectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    extraction_id: uuid.UUID
    application_id: uuid.UUID
    document_id: uuid.UUID
    field_name: str
    old_value: str | None
    new_value: str | None
    reason: str
    corrected_by_user_id: uuid.UUID | None
    created_at: datetime


class VerificationSummaryOut(BaseModel):
    documents_processed: int
    quality_passed: int
    quality_warn: int
    quality_failed: int
    checks_passed: int
    checks_warn: int
    checks_needs_info: int
    checks_failed: int
    checks_not_configured: int
    advisory_note: str


class ApplicationVerificationOut(BaseModel):
    application_id: uuid.UUID
    reference_code: str
    status: str
    extractions: list[DocumentExtractionOut]
    checks: list[VerificationCheckOut]
    corrections: list[FieldCorrectionOut]
    summary: VerificationSummaryOut


class ReviewerFieldCorrectionRequest(BaseModel):
    fields: dict[str, str] = Field(min_length=1)
    reason: str = Field(min_length=5, max_length=255)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, v: str) -> str:
        cleaned = " ".join(v.strip().split())
        if len(cleaned) < 5:
            raise ValueError("Correction reason must be at least 5 characters.")
        if AADHAAR_FULL_DIGITS_RE.search(cleaned):
            raise ValueError("Do not include 12-digit Aadhaar numbers in audit reasons.")
        return cleaned

    @field_validator("fields")
    @classmethod
    def validate_and_normalize_fields(cls, v: dict[str, str]) -> dict[str, str]:
        if not v:
            raise ValueError("Provide at least one corrected field.")
        cleaned: dict[str, str] = {}
        for key, raw_val in v.items():
            k = key.strip()
            if k not in ALLOWED_CORRECTION_FIELDS:
                raise ValueError(f"Unsupported extracted field '{k}'.")
            val = " ".join(str(raw_val).strip().split())
            if not val:
                raise ValueError(f"Corrected value for '{k}' cannot be blank.")
            if AADHAAR_FULL_DIGITS_RE.search(val) or (k == "aadhaar_last4" and RAW_12_DIGITS_RE.search(val)):
                raise ValueError(
                    "12-digit Aadhaar numbers must never be stored in extracted fields; store only last 4 digits."
                )
            if k == "pan_number":
                val = val.upper()
            elif k == "ifsc_code":
                val = val.upper()
            elif k == "aadhaar_last4":
                if not re.fullmatch(r"\d{4}", val):
                    raise ValueError("aadhaar_last4 must be exactly 4 digits.")
            elif k == "account_last4":
                if not re.fullmatch(r"\d{4}", val):
                    raise ValueError("account_last4 must be exactly 4 digits.")
            elif k == "full_name":
                val = normalize_person_name(val)
            elif k == "dob":
                norm = normalize_date_str(val)
                val = norm or val
            cleaned[k] = val
        return cleaned
