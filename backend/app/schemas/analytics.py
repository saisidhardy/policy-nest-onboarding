"""Schemas for product journey tracking, SLA turnaround, cost intelligence, and observability."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProductEventCreate(BaseModel):
    """Client-submitted or backend-injected analytics event."""

    event_name: str = Field(..., max_length=64)
    anonymous_id: str = Field(..., max_length=64)
    session_id: str = Field(..., max_length=64)
    application_id: uuid.UUID | None = None
    stage: str | None = Field(None, max_length=32)

    stage_duration_ms: int | None = None
    active_time_ms: int | None = None
    inactive_time_ms: int | None = None
    waiting_time_ms: int | None = None
    backend_time_ms: int | None = None

    is_abandonment: bool = False
    validation_errors_count: int = 0
    attempt_number: int = 1

    source: str = Field(default="web", max_length=32)
    environment: str = Field(default="production", max_length=24)
    properties: dict[str, Any] = Field(default_factory=dict)


class ProductEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_name: str
    anonymous_id: str
    user_id: uuid.UUID | None
    application_id: uuid.UUID | None
    session_id: str
    stage: str | None
    stage_duration_ms: int | None
    active_time_ms: int | None
    inactive_time_ms: int | None
    waiting_time_ms: int | None
    backend_time_ms: int | None
    is_abandonment: bool
    validation_errors_count: int
    attempt_number: int
    source: str
    environment: str
    properties: dict[str, Any]
    created_at: datetime


class FunnelStageMetric(BaseModel):
    step_number: int
    stage_name: str
    display_label: str
    count: int
    conversion_from_prev_pct: float
    conversion_from_top_pct: float
    abandonment_count: int
    abandonment_rate_pct: float
    avg_active_time_seconds: float


class FunnelDashboardOut(BaseModel):
    funnel_stages: list[FunnelStageMetric]
    overall_completion_rate_pct: float
    avg_sessions_to_complete: float
    returning_applicant_rate_pct: float
    total_visitors: int
    total_certified: int
    document_dropoff_breakdown: dict[str, int]


class TurnaroundDashboardOut(BaseModel):
    p50_turnaround_days: float
    p90_turnaround_days: float
    p95_turnaround_days: float
    avg_turnaround_days: float
    baseline_median_days: float = 8.4
    target_operational_days: float = 5.7
    pct_completed_within_5_7_days: float
    calendar_vs_business_days: dict[str, float]
    stage_duration_breakdown_hours: dict[str, float]
    active_vs_waiting_hours: dict[str, float]
    sla_breaches_count: int
    sla_breach_reasons: list[dict[str, Any]]
    externally_blocked_cases_count: int


class CostDashboardOut(BaseModel):
    total_api_expenditure_inr: float
    total_llm_expenditure_inr: float
    total_ocr_expenditure_inr: float
    avg_cost_per_document_inr: float
    avg_cost_per_application_inr: float
    avg_cost_per_certified_posp_inr: float
    avg_cost_per_correction_cycle_inr: float
    cost_by_provider: dict[str, float]
    cost_by_model: dict[str, float]
    failed_call_expenditure_inr: float
    monthly_projected_burn_inr: float


class ObservabilityDashboardOut(BaseModel):
    api_latency_p50_ms: int
    api_latency_p95_ms: int
    api_latency_p99_ms: int
    error_rate_pct: float
    error_distribution: dict[str, int]
    db_pool_status: dict[str, Any]
    queue_wait_p95_ms: int
    background_jobs_health: list[dict[str, Any]]
    integration_node_status: list[dict[str, Any]]


class ExecutiveDashboardOut(BaseModel):
    end_to_end_completion_rate_pct: float
    median_cycle_time_days: float
    cycle_time_reduction_pct: float
    total_cost_per_onboarded_agent_inr: float
    traditional_paper_cost_per_agent_inr: float = 1450.00
    net_cost_savings_pct: float
    regulatory_leakage_rate_pct: float = 0.00
    monthly_volume_projection: int
    acquisition_channels: dict[str, int]


class ApplicantJourneyOut(BaseModel):
    application_id: uuid.UUID
    reference_code: str
    total_events_count: int
    events: list[ProductEventOut]
    total_elapsed_hours: float
    active_time_hours: float
    waiting_time_hours: float
    is_completed: bool
    final_status: str
