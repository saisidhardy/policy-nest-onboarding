"""Pydantic schemas for RAG knowledge base, applicant state monitoring, and AI Chatbot."""

from datetime import datetime
import uuid
from pydantic import BaseModel, Field


class RAGChunkOut(BaseModel):
    id: str
    source: str
    section: str
    stage: str
    title: str
    text: str
    citations: list[str]
    actionable_steps: list[str] = Field(default_factory=list)
    sample_script: str | None = None
    is_escalation_indicator: bool = False


class ApplicantBlockerItem(BaseModel):
    blocker_code: str
    title: str
    description: str
    severity: str  # "BLOCKING", "WARNING", "INFO"
    suggested_action: str
    manual_citation: str
    can_appeal: bool = False


class ApplicantLiveState(BaseModel):
    has_application: bool
    application_id: str | None = None
    reference_code: str | None = None
    status: str | None = None
    priority_group: str  # "NEVER_UPLOADED_DOCS", "REJECTED_ELIGIBILITY", "NO_REPLY_CORRECTION", "VERIFIED_TRAINING_PENDING", "IN_PROGRESS", "CERTIFIED", "FRESH"
    priority_group_label: str
    current_stage: str
    documents_completed_count: int = 0
    documents_total_count: int = 6
    missing_documents: list[str] = Field(default_factory=list)
    active_blockers: list[ApplicantBlockerItem] = Field(default_factory=list)
    has_open_appeal: bool = False
    training_hours_completed: float = 0.0
    training_hours_required: float = 15.0
    days_since_created: int = 0
    days_remaining_before_expiry: int = 7


class RAGChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    application_id: uuid.UUID | None = None
    language: str = Field(default="EN", pattern="^(EN|HI)$")


class RAGChatResponse(BaseModel):
    query: str
    answer: str
    language: str
    citations: list[str]
    relevant_chunks: list[RAGChunkOut]
    applicant_state: ApplicantLiveState
    can_appeal: bool = False
    appeal_prefill_reason: str | None = None
    appeal_guidance: str | None = None
    voice_script: str
    latency_ms: float
    session_id: str | None = None
