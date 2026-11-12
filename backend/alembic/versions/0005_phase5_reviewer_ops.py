"""Phase 5 reviewer operations: assignment, escalation tracking, and fraud desk flags.

Revision ID: 0005_phase5_reviewer_ops
Revises: 0004_phase4_rules_engine
Create Date: 2026-11-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005_phase5_reviewer_ops"
down_revision = "0004_phase4_rules_engine"
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("applications", sa.Column("assigned_reviewer_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("applications", sa.Column("assigned_at", TZ, nullable=True))
    op.add_column("applications", sa.Column("escalated_at", TZ, nullable=True))
    op.add_column("applications", sa.Column("escalated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("applications", sa.Column("escalation_reason", sa.Text, nullable=True))
    op.add_column(
        "applications",
        sa.Column("fraud_flag", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.add_column("applications", sa.Column("fraud_reason", sa.Text, nullable=True))
    op.add_column("applications", sa.Column("fraud_escalated_at", TZ, nullable=True))

    op.create_foreign_key(
        "fk_applications_assigned_reviewer_id",
        "applications",
        "users",
        ["assigned_reviewer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_applications_escalated_by_user_id",
        "applications",
        "users",
        ["escalated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_applications_assigned_reviewer_id", "applications", ["assigned_reviewer_id"])
    op.create_index("ix_applications_fraud_flag", "applications", ["fraud_flag"])


def downgrade() -> None:
    op.drop_index("ix_applications_fraud_flag", table_name="applications")
    op.drop_index("ix_applications_assigned_reviewer_id", table_name="applications")
    op.drop_constraint("fk_applications_escalated_by_user_id", "applications", type_="foreignkey")
    op.drop_constraint("fk_applications_assigned_reviewer_id", "applications", type_="foreignkey")
    op.drop_column("applications", "fraud_escalated_at")
    op.drop_column("applications", "fraud_reason")
    op.drop_column("applications", "fraud_flag")
    op.drop_column("applications", "escalation_reason")
    op.drop_column("applications", "escalated_by_user_id")
    op.drop_column("applications", "escalated_at")
    op.drop_column("applications", "assigned_at")
    op.drop_column("applications", "assigned_reviewer_id")
