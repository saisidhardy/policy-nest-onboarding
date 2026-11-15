"""Product analytics, journey tracking, turnaround SLAs, and API/AI cost intelligence models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


class ProductEvent(Base):
    """Authoritative persisted product and applicant journey lifecycle event."""

    __tablename__ = "product_events"
    __table_args__ = (
        Index("ix_product_events_name_created", "event_name", "created_at"),
        Index("ix_product_events_app_created", "application_id", "created_at"),
        Index("ix_product_events_session", "session_id"),
        Index("ix_product_events_anon", "anonymous_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    anonymous_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), index=True
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(32), index=True)

    # Durations in milliseconds
    stage_duration_ms: Mapped[int | None] = mapped_column(Integer)
    active_time_ms: Mapped[int | None] = mapped_column(Integer)
    inactive_time_ms: Mapped[int | None] = mapped_column(Integer)
    waiting_time_ms: Mapped[int | None] = mapped_column(Integer)
    backend_time_ms: Mapped[int | None] = mapped_column(Integer)

    # Abandonment and error diagnostics
    is_abandonment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validation_errors_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Metadata
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="web")
    environment: Mapped[str] = mapped_column(String(24), nullable=False, default="production")
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WorkflowStageTiming(Base):
    """Server-side timing milestones for turnaround and SLA calculations."""

    __tablename__ = "workflow_stage_timings"
    __table_args__ = (
        Index("ix_stage_timings_app_stage", "application_id", "stage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    exited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Time breakdown (in milliseconds)
    active_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    waiting_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    backend_processing_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviewer_handling_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applicant_response_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # SLA metrics (Primary business objective: 5.7 days vs 8.4-day baseline)
    is_sla_breached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sla_threshold_hours: Mapped[float] = mapped_column(Float, nullable=False, default=136.8)  # 5.7 * 24 = 136.8h
    is_externally_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    external_block_reason: Mapped[str | None] = mapped_column(String(128))


class ApiCostRecord(Base):
    """Ledger recording external API, LLM, and vision operations for cost intelligence."""

    __tablename__ = "api_cost_records"
    __table_args__ = (
        Index("ix_cost_records_prov_created", "provider", "created_at"),
        Index("ix_cost_records_app", "application_id"),
        Index("ix_cost_records_correlation", "correlation_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    service: Mapped[str] = mapped_column(String(48), nullable=False)
    operation: Mapped[str] = mapped_column(String(48), nullable=False)
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(64))

    # Token and unit usage
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    units_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Execution telemetry
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="SUCCESS")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # INR financial accounting
    estimated_cost_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_cost_inr: Mapped[float | None] = mapped_column(Float)
    environment: Mapped[str] = mapped_column(String(24), nullable=False, default="production")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProviderPricingRegistry(Base):
    """Configurable provider pricing registry to prevent fabricated or assumed pricing."""

    __tablename__ = "provider_pricing_registry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    service: Mapped[str] = mapped_column(String(48), nullable=False)
    operation: Mapped[str] = mapped_column(String(48), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(64))
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 1K_INPUT_TOKENS, 1K_OUTPUT_TOKENS, PER_PAGE, PER_QUERY, PER_PENNYDROP
    unit_price_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
