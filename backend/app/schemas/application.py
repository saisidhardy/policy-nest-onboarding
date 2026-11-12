import re
import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.auth import normalize_mobile, normalize_name
from app.services.india_geo import normalize_indian_state

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
PINCODE_RE = re.compile(r"^[1-9][0-9]{5}$")
AADHAAR_LAST4_RE = re.compile(r"^[0-9]{4}$")
BANK_ACCOUNT_RE = re.compile(r"^[0-9]{9,18}$")

DocType = Literal[
    "PAN_CARD",
    "AADHAAR_FRONT",
    "AADHAAR_BACK",
    "CLASS_10_MARKSHEET",
    "BANK_DOCUMENT",
    "APPLICANT_SELFIE",
]
GenderType = Literal["MALE", "FEMALE", "OTHER", "PREFER_NOT_TO_SAY"]
EducationLevelType = Literal["CLASS_10", "CLASS_12", "GRADUATE", "POST_GRADUATE"]
ResultStatusType = Literal["PASS", "FAIL", "AWAITING"]
AccountType = Literal["SAVINGS", "CURRENT"]
LanguageCode = Literal["EN", "HI"]


def _clean_optional_text(value: str | None, max_len: int = 200) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split()).strip()
    if cleaned == "":
        return None
    if len(cleaned) > max_len:
        raise ValueError(f"Must be at most {max_len} characters.")
    return cleaned


class ApplicationCreateRequest(BaseModel):
    preferred_language: LanguageCode | None = None


class ApplicationDraftUpdate(BaseModel):
    current_step: int | None = Field(default=None, ge=1, le=6)
    preferred_language: LanguageCode | None = None

    # Personal details
    full_name: str | None = Field(default=None, max_length=200)
    date_of_birth: date | None = None
    gender: GenderType | None = None
    father_or_spouse_name: str | None = Field(default=None, max_length=200)
    mobile: str | None = None
    email: EmailStr | None = None
    pan_number: str | None = None
    aadhaar_last4: str | None = None

    # Address details
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=64)
    pincode: str | None = None
    same_as_permanent: bool | None = None
    permanent_address_line1: str | None = Field(default=None, max_length=255)
    permanent_address_line2: str | None = Field(default=None, max_length=255)
    permanent_city: str | None = Field(default=None, max_length=100)
    permanent_state: str | None = Field(default=None, max_length=64)
    permanent_pincode: str | None = None

    # Education details
    education_level: EducationLevelType | None = None
    board_name: str | None = Field(default=None, max_length=128)
    school_or_university: str | None = Field(default=None, max_length=200)
    passing_year: int | None = Field(default=None, ge=1950, le=2030)
    roll_number: str | None = Field(default=None, max_length=64)
    result_status: ResultStatusType | None = None
    percentage_or_cgpa: str | None = Field(default=None, max_length=32)

    # Bank details
    account_holder_name: str | None = Field(default=None, max_length=200)
    bank_name: str | None = Field(default=None, max_length=128)
    branch_name: str | None = Field(default=None, max_length=128)
    ifsc_code: str | None = None
    account_number: str | None = None
    account_type: AccountType | None = None
    is_joint_account: bool | None = None
    is_primary_holder: bool | None = None

    # Declarations
    consent_terms: bool | None = None
    consent_kyc_processing: bool | None = None
    declaration_no_other_posp: bool | None = None

    @field_validator("full_name", "father_or_spouse_name", "account_holder_name")
    @classmethod
    def _validate_person_names(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        return normalize_name(v)

    _mobile = field_validator("mobile")(normalize_mobile)

    @field_validator("date_of_birth")
    @classmethod
    def _validate_dob(cls, v: date | None) -> date | None:
        if v is None:
            return None
        today = date.today()
        if v >= today or v.year < 1920:
            raise ValueError("Enter a valid date of birth.")
        return v

    @field_validator("pan_number")
    @classmethod
    def _validate_pan(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        cleaned = v.strip().upper()
        if not PAN_RE.match(cleaned):
            raise ValueError("Enter a valid PAN in format AAAAA9999A.")
        return cleaned

    @field_validator("aadhaar_last4")
    @classmethod
    def _validate_aadhaar_last4(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        cleaned = re.sub(r"[\s\-]", "", v.strip())
        if len(cleaned) == 12 and cleaned.isdigit():
            raise ValueError("Do not enter your full 12-digit Aadhaar number. Enter only the last 4 digits.")
        if not AADHAAR_LAST4_RE.match(cleaned):
            raise ValueError("Enter exactly the last 4 digits of your Aadhaar number.")
        return cleaned

    @field_validator("state", "permanent_state")
    @classmethod
    def _validate_state(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        return normalize_indian_state(v)

    @field_validator("pincode", "permanent_pincode")
    @classmethod
    def _validate_pincode(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        cleaned = v.strip()
        if not PINCODE_RE.match(cleaned):
            raise ValueError("Enter a valid 6-digit Indian PIN code.")
        return cleaned

    @field_validator("ifsc_code")
    @classmethod
    def _validate_ifsc(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        cleaned = v.strip().upper()
        if not IFSC_RE.match(cleaned):
            raise ValueError("Enter a valid 11-character IFSC code (e.g. HDFC0000240).")
        return cleaned

    @field_validator("account_number")
    @classmethod
    def _validate_account_number(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        cleaned = re.sub(r"\s+", "", v.strip())
        if not BANK_ACCOUNT_RE.match(cleaned):
            raise ValueError("Enter a valid bank account number (9 to 18 digits).")
        return cleaned

    @field_validator(
        "address_line1",
        "address_line2",
        "city",
        "district",
        "permanent_address_line1",
        "permanent_address_line2",
        "permanent_city",
        "board_name",
        "school_or_university",
        "roll_number",
        "percentage_or_cgpa",
        "bank_name",
        "branch_name",
    )
    @classmethod
    def _clean_text(cls, v: str | None) -> str | None:
        return _clean_optional_text(v, 255)


class ApplicationSubmitRequest(BaseModel):
    consent_terms: bool
    consent_kyc_processing: bool
    declaration_no_other_posp: bool


class WithdrawApplicationRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=240)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    doc_type: str
    version: int
    is_current: bool
    status: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    sha256_hash: str
    storage_provider: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_role: str | None
    event_type: str
    from_status: str | None
    to_status: str | None
    summary: str
    details: dict[str, Any]
    created_at: datetime


class SectionCompleteness(BaseModel):
    personal: bool
    address: bool
    education: bool
    bank: bool
    documents: bool
    declarations: bool


class CompletenessOut(BaseModel):
    sections: SectionCompleteness
    missing_fields: list[str]
    missing_documents: list[str]
    uploaded_document_count: int
    required_document_count: int
    completed_sections: int
    total_sections: int
    ready_to_submit: bool


class ApplicationSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference_code: str
    status: str
    current_step: int
    region: str | None
    preferred_language: str
    full_name: str | None
    submitted_at: datetime | None
    last_saved_at: datetime
    resolution_kind: str | None = None
    rework_count: int = 0
    created_at: datetime
    updated_at: datetime
    completeness: CompletenessOut


class ApplicationDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference_code: str
    user_id: uuid.UUID
    status: str
    current_step: int
    region: str | None
    sensitivity: int
    preferred_language: str
    channel: str

    full_name: str | None
    date_of_birth: date | None
    gender: str | None
    father_or_spouse_name: str | None
    mobile: str | None
    email: str | None
    pan_number: str | None
    aadhaar_last4: str | None

    address_line1: str | None
    address_line2: str | None
    city: str | None
    district: str | None
    state: str | None
    pincode: str | None
    same_as_permanent: bool
    permanent_address_line1: str | None
    permanent_address_line2: str | None
    permanent_city: str | None
    permanent_state: str | None
    permanent_pincode: str | None

    education_level: str | None
    board_name: str | None
    school_or_university: str | None
    passing_year: int | None
    roll_number: str | None
    result_status: str | None
    percentage_or_cgpa: str | None

    account_holder_name: str | None
    bank_name: str | None
    branch_name: str | None
    ifsc_code: str | None
    account_number_last4: str | None
    account_number_masked: str | None
    has_account_number: bool
    account_type: str | None
    is_joint_account: bool
    is_primary_holder: bool

    consent_terms: bool
    consent_kyc_processing: bool
    declaration_no_other_posp: bool
    declared_at: datetime | None
    submitted_at: datetime | None
    last_saved_at: datetime
    parent_application_id: uuid.UUID | None = None
    resolution_kind: str | None = None
    reapplication_reason: str | None = None
    rework_count: int = 0
    created_at: datetime
    updated_at: datetime

    documents: list[DocumentOut]
    document_history: list[DocumentOut]
    events: list[ApplicationEventOut]
    completeness: CompletenessOut
