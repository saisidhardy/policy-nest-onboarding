"""Phase 6 LMS training, examination, certification, and sync retry models."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utcnow


class TrainingRecord(TimestampMixin, Base):
    """Per-application external LMS enrollment, 15-hour progress, exam, and POSP certificate state."""

    __tablename__ = "training_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    eligibility_status: Mapped[str] = mapped_column(String(24), nullable=False, default="NOT_ELIGIBLE")
    eligibility_reason: Mapped[str | None] = mapped_column(Text)

    lms_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="not_configured")
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    external_enrollment_id: Mapped[str | None] = mapped_column(String(120), index=True)
    lms_launch_url: Mapped[str | None] = mapped_column(String(500))

    enrollment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_ENROLLED")
    required_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("15.00"), server_default=text("15.00")
    )
    completed_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00")
    )
    progress_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00"), server_default=text("0.00")
    )
    module_progress: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    exam_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_ELIGIBLE")
    exam_score_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    exam_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default=text("0"))
    last_exam_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_exam_eligible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    certification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_CERTIFIED")
    certificate_number: Mapped[str | None] = mapped_column(String(64), unique=True)
    certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    certificate_valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sync_status: Mapped[str] = mapped_column(String(24), nullable=False, default="IDLE", index=True)
    sync_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default=text("0"))
    max_sync_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=5, server_default=text("5"))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(Text)

    application = relationship("Application", foreign_keys=[application_id])
    sync_logs: Mapped[list["LmsSyncLog"]] = relationship(
        back_populates="training_record",
        cascade="all, delete-orphan",
        order_by="LmsSyncLog.occurred_at.desc()",
    )


class LmsSyncLog(Base):
    """Immutable log of outbound LMS sync attempts, retries, errors, and inbound webhooks."""

    __tablename__ = "lms_sync_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    training_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("training_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(32), nullable=False)
    adapter_origin: Mapped[str] = mapped_column(String(24), nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    attempt_number: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    request_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    response_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    training_record: Mapped["TrainingRecord"] = relationship(back_populates="sync_logs")
