"""Onboarding domain, review workflow, training, exam, and certification.

Revision ID: 0002_onboarding_domain
Revises: 0001_foundation
Create Date: 2026-11-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_onboarding_domain"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)
UUID = postgresql.UUID(as_uuid=True)
JSON = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("applicant_id", UUID, nullable=False),
        sa.Column("reference", sa.String(24), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("current_step", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("region", sa.String(32)),
        sa.Column("sensitivity", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("assigned_reviewer_id", UUID),
        sa.Column("date_of_birth", sa.Date),
        sa.Column("pan_number", sa.String(10)),
        sa.Column("aadhaar_last4", sa.String(4)),
        sa.Column("address", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("education", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("bank_details", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("declarations", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("rule_result", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("submitted_at", TZ),
        sa.Column("decided_at", TZ),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["applicant_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("applicant_id", name="uq_applications_applicant_id"),
        sa.UniqueConstraint("reference", name="uq_applications_reference"),
        sa.CheckConstraint("current_step BETWEEN 0 AND 5", name="current_step_range"),
        sa.CheckConstraint("sensitivity BETWEEN 1 AND 3", name="sensitivity_range"),
    )
    op.create_index("ix_applications_status_region", "applications", ["status", "region"])
    op.create_index("ix_applications_assigned_reviewer", "applications", ["assigned_reviewer_id"])

    op.create_table(
        "application_events",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("application_id", UUID, nullable=False),
        sa.Column("actor_user_id", UUID),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("from_status", sa.String(32)),
        sa.Column("to_status", sa.String(32)),
        sa.Column("details", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("occurred_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_application_events_application_time", "application_events", ["application_id", "occurred_at"])
    op.execute(
        """
        CREATE TRIGGER application_events_append_only BEFORE UPDATE OR DELETE ON application_events
        FOR EACH ROW EXECUTE FUNCTION audit_logs_block_mutation();
        """
    )

    op.create_table(
        "documents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("application_id", UUID, nullable=False),
        sa.Column("document_type", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("byte_size", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="UPLOADED"),
        sa.Column("quality_result", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("extracted_fields", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("superseded_at", TZ),
        sa.Column("uploaded_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("application_id", "document_type", "version", name="uq_document_version"),
        sa.CheckConstraint("byte_size > 0 AND byte_size <= 10485760", name="document_size_range"),
    )
    op.create_index("ix_documents_application_type", "documents", ["application_id", "document_type"])

    op.create_table(
        "verifications",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("application_id", UUID, nullable=False),
        sa.Column("verification_type", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("request_reference", sa.String(128)),
        sa.Column("result", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("requested_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", TZ),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_verifications_application_type", "verifications", ["application_id", "verification_type"])

    op.create_table(
        "correction_requests",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("application_id", UUID, nullable=False),
        sa.Column("reviewer_id", UUID, nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="OPEN"),
        sa.Column("issues", JSON, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("message_en", sa.Text, nullable=False),
        sa.Column("message_hi", sa.Text, nullable=False),
        sa.Column("resolved_at", TZ),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_corrections_application_status", "correction_requests", ["application_id", "status"])

    op.create_table(
        "review_decisions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("application_id", UUID, nullable=False),
        sa.Column("reviewer_id", UUID, nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("justification", sa.Text, nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=False),
        sa.Column("resulting_status", sa.String(32), nullable=False),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_review_decisions_application_time", "review_decisions", ["application_id", "created_at"])
    op.execute(
        """
        CREATE TRIGGER review_decisions_append_only BEFORE UPDATE OR DELETE ON review_decisions
        FOR EACH ROW EXECUTE FUNCTION audit_logs_block_mutation();
        """
    )

    op.create_table(
        "training_progress",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("application_id", UUID, nullable=False),
        sa.Column("module_code", sa.String(32), nullable=False),
        sa.Column("minutes_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("required_minutes", sa.Integer, nullable=False),
        sa.Column("completed_at", TZ),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("application_id", "module_code", name="uq_training_module"),
        sa.CheckConstraint("minutes_completed >= 0 AND required_minutes > 0", name="training_minutes_positive"),
    )

    op.create_table(
        "exam_attempts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("application_id", UUID, nullable=False),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("question_order", JSON, nullable=False),
        sa.Column("answers", JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("score_percent", sa.Numeric(5, 2)),
        sa.Column("passed", sa.Boolean),
        sa.Column("started_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_at", TZ),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("application_id", "attempt_number", name="uq_exam_attempt_number"),
    )

    op.create_table(
        "certificates",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("application_id", UUID, nullable=False),
        sa.Column("certificate_number", sa.String(40), nullable=False),
        sa.Column("issued_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("seal_sha256", sa.String(64), nullable=False),
        sa.Column("revoked_at", TZ),
        sa.Column("revocation_reason", sa.Text),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("application_id", name="uq_certificates_application_id"),
        sa.UniqueConstraint("certificate_number", name="uq_certificates_certificate_number"),
        sa.UniqueConstraint("seal_sha256", name="uq_certificates_seal_sha256"),
    )


def downgrade() -> None:
    for table in (
        "certificates",
        "exam_attempts",
        "training_progress",
        "review_decisions",
        "correction_requests",
        "verifications",
        "documents",
        "application_events",
        "applications",
    ):
        op.drop_table(table)
