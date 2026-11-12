"""Phase 6 LMS training, examination, certification, and sync retry tracking.

Revision ID: 0006_phase6_training_lms
Revises: 0005_phase5_reviewer_ops
Create Date: 2026-11-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_phase6_training_lms"
down_revision = "0005_phase5_reviewer_ops"
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "training_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("eligibility_status", sa.String(24), nullable=False),
        sa.Column("eligibility_reason", sa.Text),
        sa.Column("lms_provider", sa.String(32), nullable=False),
        sa.Column("is_simulated", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("external_enrollment_id", sa.String(120)),
        sa.Column("lms_launch_url", sa.String(500)),
        sa.Column("enrollment_status", sa.String(32), nullable=False),
        sa.Column("required_hours", sa.Numeric(5, 2), nullable=False, server_default=sa.text("15.00")),
        sa.Column("completed_hours", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("progress_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("module_progress", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("enrolled_at", TZ),
        sa.Column("started_at", TZ),
        sa.Column("completed_at", TZ),
        sa.Column("exam_status", sa.String(32), nullable=False),
        sa.Column("exam_score_pct", sa.Numeric(5, 2)),
        sa.Column("exam_attempts", sa.SmallInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("last_exam_at", TZ),
        sa.Column("next_exam_eligible_at", TZ),
        sa.Column("certification_status", sa.String(32), nullable=False),
        sa.Column("certificate_number", sa.String(64), unique=True),
        sa.Column("certified_at", TZ),
        sa.Column("certificate_valid_until", TZ),
        sa.Column("sync_status", sa.String(24), nullable=False),
        sa.Column("sync_attempts", sa.SmallInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("max_sync_attempts", sa.SmallInteger, nullable=False, server_default=sa.text("5")),
        sa.Column("last_sync_at", TZ),
        sa.Column("next_retry_at", TZ),
        sa.Column("last_error_code", sa.String(64)),
        sa.Column("last_error_message", sa.Text),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_training_records_external_enrollment_id", "training_records", ["external_enrollment_id"])
    op.create_index("ix_training_records_sync_status", "training_records", ["sync_status"])

    op.create_table(
        "lms_sync_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "training_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("training_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("provider_name", sa.String(32), nullable=False),
        sa.Column("adapter_origin", sa.String(24), nullable=False),
        sa.Column("is_simulated", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("attempt_number", sa.SmallInteger, nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("http_status", sa.SmallInteger),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.Text),
        sa.Column("request_payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("response_payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("occurred_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lms_sync_logs_training_record_id", "lms_sync_logs", ["training_record_id"])
    op.create_index("ix_lms_sync_logs_application_id", "lms_sync_logs", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_lms_sync_logs_application_id", table_name="lms_sync_logs")
    op.drop_index("ix_lms_sync_logs_training_record_id", table_name="lms_sync_logs")
    op.drop_table("lms_sync_logs")
    op.drop_index("ix_training_records_sync_status", table_name="training_records")
    op.drop_index("ix_training_records_external_enrollment_id", table_name="training_records")
    op.drop_table("training_records")
