"""Phase 3 document intelligence: extractions, field corrections, verification checks.

Revision ID: 0003_phase3_doc_intelligence
Revises: 0002_phase2_applications
Create Date: 2026-11-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_phase3_doc_intelligence"
down_revision = "0002_phase2_applications"
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "document_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ocr_engine", sa.String(40), nullable=False),
        sa.Column("ai_assistant_provider", sa.String(40), nullable=False),
        sa.Column("predicted_doc_type", sa.String(32)),
        sa.Column("classification_confidence", sa.Float),
        sa.Column("classification_match", sa.Boolean),
        sa.Column("quality_status", sa.String(32), nullable=False),
        sa.Column("blur_score", sa.Float),
        sa.Column("glare_ratio", sa.Float),
        sa.Column("edge_clip_ratio", sa.Float),
        sa.Column("face_detected", sa.Boolean),
        sa.Column("ocr_confidence", sa.Float),
        sa.Column("raw_ocr_text_masked", sa.Text),
        sa.Column("extracted_fields", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("missing_fields", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("ai_explanation", sa.Text),
        sa.Column("aadhaar_masked_applied", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("redacted_storage_key", sa.String(512)),
        sa.Column("reviewer_corrected_fields", postgresql.JSONB),
        sa.Column("effective_fields", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("corrected_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("corrected_at", TZ),
        sa.Column("processed_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_document_extractions"),
        sa.UniqueConstraint("document_id", name="uq_document_extractions_document_id"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["application_documents.id"],
            ondelete="CASCADE",
            name="fk_document_extractions_document_id_application_documents",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name="fk_document_extractions_application_id_applications",
        ),
        sa.ForeignKeyConstraint(
            ["corrected_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_document_extractions_corrected_by_user_id_users",
        ),
    )
    op.create_index("ix_document_extractions_application_id", "document_extractions", ["application_id"])

    op.create_table(
        "document_field_corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("old_value", sa.Text),
        sa.Column("new_value", sa.Text),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("corrected_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_document_field_corrections"),
        sa.ForeignKeyConstraint(
            ["extraction_id"],
            ["document_extractions.id"],
            ondelete="CASCADE",
            name="fk_doc_field_corr_extraction_id",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name="fk_document_field_corrections_application_id_applications",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["application_documents.id"],
            ondelete="CASCADE",
            name="fk_doc_field_corr_document_id",
        ),
        sa.ForeignKeyConstraint(
            ["corrected_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_document_field_corrections_corrected_by_user_id_users",
        ),
    )
    op.create_index("ix_document_field_corrections_extraction_id", "document_field_corrections", ["extraction_id"])
    op.create_index("ix_document_field_corrections_application_id", "document_field_corrections", ["application_id"])

    op.create_table(
        "verification_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("check_type", sa.String(48), nullable=False),
        sa.Column("target_doc_type", sa.String(32)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("origin", sa.String(32), nullable=False),
        sa.Column("provider_name", sa.String(64)),
        sa.Column("provider_reference", sa.String(128)),
        sa.Column("is_simulated", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("confidence", sa.Float),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("explanation", sa.Text),
        sa.Column("checked_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_verification_checks"),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name="fk_verification_checks_application_id_applications",
        ),
    )
    op.create_index("ix_verification_checks_application_id", "verification_checks", ["application_id"])


def downgrade() -> None:
    op.drop_table("verification_checks")
    op.drop_table("document_field_corrections")
    op.drop_table("document_extractions")
