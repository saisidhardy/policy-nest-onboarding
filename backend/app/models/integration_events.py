"""Phase 8 SMS delivery, inbound webhook delivery, and active integration health probe models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class SmsDelivery(Base):
    """Outbound SMS delivery attempt tracking without fabricating provider message IDs."""

    __tablename__ = "sms_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), index=True
    )
    recipient_mobile: Mapped[str] = mapped_column(String(24), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    body_preview: Mapped[str] = mapped_column(String(320), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    provider_message_id: Mapped[str | None] = mapped_column(String(128))
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default=text("1"))
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WebhookDelivery(Base):
    """Inbound signed webhook log with per-source idempotency protection."""

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index(
            "uq_webhook_source_event",
            "source",
            "external_event_id",
            unique=True,
            postgresql_where=text("external_event_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_event_id: Mapped[str | None] = mapped_column(String(128))
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IntegrationProbeResult(Base):
    """Latest active health check telemetry recorded per integration key."""

    __tablename__ = "integration_probes"

    adapter_key: Mapped[str] = mapped_column(String(48), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    mode: Mapped[str] = mapped_column(String(24), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    checked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
