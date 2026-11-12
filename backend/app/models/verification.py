import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DocumentExtraction(Base):
    __tablename__ = "document_extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("application_documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ocr_engine: Mapped[str] = mapped_column(String(40), nullable=False)
    ai_assistant_provider: Mapped[str] = mapped_column(String(40), nullable=False)

    predicted_doc_type: Mapped[str | None] = mapped_column(String(32))
    classification_confidence: Mapped[float | None] = mapped_column(Float)
    classification_match: Mapped[bool | None] = mapped_column(Boolean)

    quality_status: Mapped[str] = mapped_column(String(32), nullable=False)
    blur_score: Mapped[float | None] = mapped_column(Float)
    glare_ratio: Mapped[float | None] = mapped_column(Float)
    edge_clip_ratio: Mapped[float | None] = mapped_column(Float)
    face_detected: Mapped[bool | None] = mapped_column(Boolean)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)

    raw_ocr_text_masked: Mapped[str | None] = mapped_column(Text)
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    missing_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    ai_explanation: Mapped[str | None] = mapped_column(Text)

    aadhaar_masked_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    redacted_storage_key: Mapped[str | None] = mapped_column(String(512))

    reviewer_corrected_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    effective_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    corrected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DocumentFieldCorrection(Base):
    __tablename__ = "document_field_corrections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extraction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_extractions.id", ondelete="CASCADE", name="fk_doc_field_corr_extraction_id"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("application_documents.id", ondelete="CASCADE", name="fk_doc_field_corr_document_id"),
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    corrected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VerificationCheck(Base):
    __tablename__ = "verification_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    check_type: Mapped[str] = mapped_column(String(48), nullable=False)
    target_doc_type: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(64))
    provider_reference: Mapped[str | None] = mapped_column(String(128))
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    explanation: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
