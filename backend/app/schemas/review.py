import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReviewQueueKpis(BaseModel):
    pending_review_count: int
    submitted_count: int
    rework_submitted_count: int
    in_review_count: int
    escalated_count: int
    fraud_flagged_count: int
    open_appeals_count: int
    assigned_to_me_count: int
    unassigned_pending_count: int
    kyc_approved_count: int
    rejected_count: int


class ReviewQueueItemOut(BaseModel):
    id: uuid.UUID
    reference_code: str
    status: str
    region: str | None
    sensitivity: int
    full_name: str | None
    city: str | None
    state: str | None
    submitted_at: datetime | None
    last_saved_at: datetime
    rework_count: int
    resolution_kind: str | None
    assigned_reviewer_id: uuid.UUID | None
    assigned_reviewer_name: str | None
    assigned_at: datetime | None
    escalated_at: datetime | None
    escalation_reason: str | None
    fraud_flag: bool
    fraud_reason: str | None
    fraud_escalated_at: datetime | None
    latest_outcome: str | None
    latest_reason_codes: list[str]
    open_appeal_count: int
    uploaded_document_count: int
    required_document_count: int


class ReviewQueuePageOut(BaseModel):
    items: list[ReviewQueueItemOut]
    total: int
    page: int
    page_size: int
    kpis: ReviewQueueKpis


class ReviewClaimRequest(BaseModel):
    action: Literal["claim", "release", "assign"] = "claim"
    target_user_id: uuid.UUID | None = None


class FraudEscalationRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


class FraudResolutionRequest(BaseModel):
    resolution: Literal["CLEAR_FLAG", "CONFIRM_FRAUD_REJECT"]
    reason_text: str = Field(min_length=10, max_length=2000)


class ReviewHistoryItemOut(BaseModel):
    decision_id: uuid.UUID
    application_id: uuid.UUID
    reference_code: str
    applicant_name: str | None
    region: str | None
    decided_by_user_id: uuid.UUID
    decided_by_name: str
    decided_by_role: str
    decision: str
    previous_status: str
    new_status: str
    is_override: bool
    override_of_outcome: str | None
    reason_codes: list[str]
    reason_text: str
    created_at: datetime


class ReviewHistoryPageOut(BaseModel):
    items: list[ReviewHistoryItemOut]
    total: int
    page: int
    page_size: int


class ReviewerProductivityOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    role_code: str
    decisions_count: int
    approvals_count: int
    rework_count: int
    rejections_count: int
    escalations_count: int
    overrides_count: int
    field_corrections_count: int


class ReviewAnalyticsOut(BaseModel):
    total_submitted_or_decided: int
    status_counts: dict[str, int]
    rule_outcome_counts: dict[str, int]
    stp_auto_pass_rate_pct: float
    rework_rate_pct: float
    escalation_rate_pct: float
    fraud_flagged_active_count: int
    avg_turnaround_hours: float | None
    open_appeals_count: int
    resolved_appeals_count: int
    reviewer_productivity: list[ReviewerProductivityOut]


class AssignableReviewerOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    role_code: str
    region: str | None
