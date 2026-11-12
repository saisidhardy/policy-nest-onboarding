import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_RECOGNIZED_BOARDS = [
    "CBSE",
    "CISCE",
    "ICSE",
    "NIOS",
    "STATE BOARD",
    "MAHARASHTRA",
    "KARNATAKA",
    "TAMIL NADU",
    "UTTAR PRADESH",
    "WEST BENGAL",
    "DELHI",
    "GUJARAT",
    "RAJASTHAN",
    "KERALA",
    "TELANGANA",
    "ANDHRA PRADESH",
    "MADHYA PRADESH",
    "BIHAR",
    "PUNJAB",
    "HARYANA",
]


class RuleConfigSchema(BaseModel):
    min_age_years: int = Field(default=18, ge=18, le=25)
    min_ocr_confidence: float = Field(default=0.75, ge=0.40, le=0.99)
    face_match_auto_pass_threshold: float = Field(default=0.75, ge=0.50, le=0.99)
    face_match_rework_threshold: float = Field(default=0.60, ge=0.30, le=0.85)
    max_rework_cycles_before_human: int = Field(default=2, ge=1, le=5)
    auto_approve_enabled: bool = True
    auto_reject_statutory: bool = True
    never_auto_reject_name_mismatch: Literal[True] = True
    recognized_education_boards: list[str] = Field(default_factory=lambda: list(DEFAULT_RECOGNIZED_BOARDS))
    require_all_six_documents: bool = True
    allow_bank_truncation_match: bool = True

    @field_validator("face_match_rework_threshold")
    @classmethod
    def check_thresholds(cls, v: float, info) -> float:
        pass_t = info.data.get("face_match_auto_pass_threshold", 0.75)
        if v >= pass_t:
            raise ValueError("face_match_rework_threshold must be less than face_match_auto_pass_threshold")
        return v


class RuleSetCreateRequest(BaseModel):
    version: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9._-]+$")
    name: str = Field(min_length=3, max_length=128)
    description: str | None = Field(default=None, max_length=1000)
    rules_config: RuleConfigSchema = Field(default_factory=RuleConfigSchema)
    activate_immediately: bool = False


class RuleSetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: str
    name: str
    description: str | None
    status: str
    is_active: bool
    rules_config: dict[str, Any]
    created_by_user_id: uuid.UUID | None
    activated_by_user_id: uuid.UUID | None
    activated_at: datetime | None
    created_at: datetime


class RuleEvaluationItemOut(BaseModel):
    rule_id: str
    category: Literal["ELIGIBILITY", "COMPLETENESS", "CONSISTENCY", "RISK", "BIOMETRIC"]
    name: str
    status: Literal["PASS", "FAIL", "HUMAN_REVIEW", "INFO", "NOT_EVALUATED"]
    severity: Literal["HARD_REJECT", "REWORK", "HUMAN_ONLY", "INFO", "NONE"]
    reason_code: str | None = None
    explanation: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class ReworkItemOut(BaseModel):
    doc_type: str | None = None
    reason_code: str
    title_en: str
    title_hi: str
    action_en: str
    action_hi: str


class EvaluateApplicationRequest(BaseModel):
    apply_transition: bool = True
    trigger_source: str = Field(default="MANUAL_EVALUATE", max_length=32)


class RuleExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    ruleset_id: uuid.UUID
    ruleset_version: str
    trigger_source: str
    triggered_by_user_id: uuid.UUID | None
    outcome: str
    recommended_status: str
    eligibility_status: str
    completeness_status: str
    consistency_status: str
    risk_level: str
    auto_pass_eligible: bool
    requires_human_review: bool
    reason_codes: list[str]
    rule_results: list[dict[str, Any]]
    rework_items: list[dict[str, Any]]
    risk_indicators: list[dict[str, Any]]
    summary: str
    executed_at: datetime


class ReviewerDecisionRequest(BaseModel):
    decision: Literal["APPROVE", "NEEDS_MORE_INFO", "REJECT", "ESCALATE"]
    reason_codes: list[str] = Field(min_length=1, max_length=10)
    reason_text: str = Field(min_length=10, max_length=2000)
    rework_items: list[ReworkItemOut] = Field(default_factory=list)


class ApplicationDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    rule_execution_id: uuid.UUID | None
    decided_by_user_id: uuid.UUID
    decided_by_role: str
    decision: str
    previous_status: str
    new_status: str
    is_override: bool
    override_of_outcome: str | None
    reason_codes: list[str]
    reason_text: str
    rework_items: list[dict[str, Any]]
    created_at: datetime


class ReapplyRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


class AppealCreateRequest(BaseModel):
    appeal_reason: str = Field(min_length=15, max_length=2000)
    supporting_notes: str | None = Field(default=None, max_length=2000)


class AppealResolveRequest(BaseModel):
    resolution: Literal["UPHOLD_REJECTION", "REOPEN_FOR_REVIEW", "APPROVE_KYC"]
    resolution_notes: str = Field(min_length=10, max_length=2000)


class ApplicationAppealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    submitted_by_user_id: uuid.UUID
    status: str
    appeal_reason: str
    supporting_notes: str | None
    resolution_notes: str | None
    resolved_by_user_id: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime


class ApplicationDecisionSummaryOut(BaseModel):
    application_id: uuid.UUID
    application_status: str
    resolution_kind: str | None
    parent_application_id: uuid.UUID | None
    rework_count: int
    active_ruleset_version: str
    latest_execution: RuleExecutionOut | None
    execution_history: list[RuleExecutionOut]
    decisions: list[ApplicationDecisionOut]
    appeals: list[ApplicationAppealOut]
