import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

REQUIRED_DOC_TYPES = (
    "PAN_CARD",
    "AADHAAR_FRONT",
    "AADHAAR_BACK",
    "CLASS_10_MARKSHEET",
    "BANK_DOCUMENT",
    "APPLICANT_SELFIE",
)

EDITABLE_STATUSES = {"DRAFT", "NEEDS_MORE_INFO"}
ACTIVE_APPLICATION_STATUSES = {
    "DRAFT",
    "SUBMITTED",
    "IN_REVIEW",
    "NEEDS_MORE_INFO",
    "REWORK_SUBMITTED",
    "KYC_APPROVED",
    "TRAINING_IN_PROGRESS",
}


class Application(TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint("current_step BETWEEN 1 AND 6", name="step_range"),
        CheckConstraint("sensitivity BETWEEN 1 AND 3", name="sensitivity_range"),
        CheckConstraint("aadhaar_last4 IS NULL OR aadhaar_last4 ~ '^[0-9]{4}$'", name="aadhaar_last4_digits"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference_code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)
    current_step: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    region: Mapped[str | None] = mapped_column(String(32))
    sensitivity: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    preferred_language: Mapped[str] = mapped_column(String(8), nullable=False, default="EN")
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="SELF_SERVICE")

    # Personal details
    full_name: Mapped[str | None] = mapped_column(String(200))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(24))
    father_or_spouse_name: Mapped[str | None] = mapped_column(String(200))
    mobile: Mapped[str | None] = mapped_column(String(16))
    email: Mapped[str | None] = mapped_column(String(320))
    pan_number: Mapped[str | None] = mapped_column(String(10), index=True)
    aadhaar_last4: Mapped[str | None] = mapped_column(String(4))

    # Address details
    address_line1: Mapped[str | None] = mapped_column(String(255))
    address_line2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(64))
    pincode: Mapped[str | None] = mapped_column(String(6))
    same_as_permanent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    permanent_address_line1: Mapped[str | None] = mapped_column(String(255))
    permanent_address_line2: Mapped[str | None] = mapped_column(String(255))
    permanent_city: Mapped[str | None] = mapped_column(String(100))
    permanent_state: Mapped[str | None] = mapped_column(String(64))
    permanent_pincode: Mapped[str | None] = mapped_column(String(6))

    # Education details
    education_level: Mapped[str | None] = mapped_column(String(32))
    board_name: Mapped[str | None] = mapped_column(String(128))
    school_or_university: Mapped[str | None] = mapped_column(String(200))
    passing_year: Mapped[int | None] = mapped_column(SmallInteger)
    roll_number: Mapped[str | None] = mapped_column(String(64))
    result_status: Mapped[str | None] = mapped_column(String(16))
    percentage_or_cgpa: Mapped[str | None] = mapped_column(String(32))

    # Bank details (full account number stored encrypted; masked/last4 exposed in responses)
    account_holder_name: Mapped[str | None] = mapped_column(String(200))
    bank_name: Mapped[str | None] = mapped_column(String(128))
    branch_name: Mapped[str | None] = mapped_column(String(128))
    ifsc_code: Mapped[str | None] = mapped_column(String(11))
    account_number_last4: Mapped[str | None] = mapped_column(String(4))
    account_number_masked: Mapped[str | None] = mapped_column(String(32))
    account_number_encrypted: Mapped[str | None] = mapped_column(Text)
    account_type: Mapped[str | None] = mapped_column(String(16))
    is_joint_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_primary_holder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Declarations and lifecycle
    consent_terms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_kyc_processing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    declaration_no_other_posp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    declared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    parent_application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL", name="fk_applications_parent_application_id"),
        index=True,
    )
    resolution_kind: Mapped[str | None] = mapped_column(String(32))
    reapplication_reason: Mapped[str | None] = mapped_column(Text)
    rework_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    assigned_reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_applications_assigned_reviewer_id"),
        index=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_applications_escalated_by_user_id")
    )
    escalation_reason: Mapped[str | None] = mapped_column(Text)
    fraud_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )
    fraud_reason: Mapped[str | None] = mapped_column(Text)
    fraud_escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    documents: Mapped[list["ApplicationDocument"]] = relationship(
        back_populates="application",
        order_by="ApplicationDocument.created_at.desc()",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application",
        order_by="ApplicationEvent.id.desc()",
        cascade="all, delete-orphan",
    )


class ApplicationDocument(TimestampMixin, Base):
    __tablename__ = "application_documents"
    __table_args__ = (
        Index(
            "uq_current_application_doc",
            "application_id",
            "doc_type",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="UPLOADED")
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(24), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    application: Mapped[Application] = relationship(back_populates="documents")


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_role: Mapped[str | None] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str | None] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application: Mapped[Application] = relationship(back_populates="events")
