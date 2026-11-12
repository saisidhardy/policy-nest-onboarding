import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RuleSet(Base):
    """Versioned deterministic business rules configuration (PS-01)."""

    __tablename__ = "rule_sets"
    __table_args__ = (
        Index(
            "uq_active_rule_set",
            "is_active",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    rules_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_rule_sets_created_by_user_id")
    )
    activated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_rule_sets_activated_by_user_id")
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RuleExecution(Base):
    """Immutable log of a deterministic rule engine evaluation for an application."""

    __tablename__ = "rule_executions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE", name="fk_rule_exec_app_id"),
        nullable=False,
        index=True,
    )
    ruleset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="RESTRICT", name="fk_rule_exec_ruleset_id"),
        nullable=False,
    )
    ruleset_version: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_source: Mapped[str] = mapped_column(String(32), nullable=False)
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_rule_exec_user_id")
    )
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    recommended_status: Mapped[str] = mapped_column(String(32), nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String(24), nullable=False)
    completeness_status: Mapped[str] = mapped_column(String(24), nullable=False)
    consistency_status: Mapped[str] = mapped_column(String(24), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(24), nullable=False)
    auto_pass_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    rule_results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    rework_items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    risk_indicators: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ApplicationDecision(Base):
    """Explicit human reviewer / senior reviewer decision or override with mandatory reason."""

    __tablename__ = "application_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE", name="fk_app_dec_app_id"),
        nullable=False,
        index=True,
    )
    rule_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rule_executions.id", ondelete="SET NULL", name="fk_app_dec_rule_exec_id")
    )
    decided_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_app_dec_user_id"),
        nullable=False,
    )
    decided_by_role: Mapped[str] = mapped_column(String(32), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    is_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_of_outcome: Mapped[str | None] = mapped_column(String(32))
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    rework_items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ApplicationAppeal(Base):
    """Formal appeal against a REJECTED application (separate from in-place correction and new reapplication)."""

    __tablename__ = "application_appeals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE", name="fk_app_appeal_app_id"),
        nullable=False,
        index=True,
    )
    submitted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_app_appeal_submit_user_id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN", index=True)
    appeal_reason: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_notes: Mapped[str | None] = mapped_column(Text)
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_app_appeal_resolve_user_id")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
