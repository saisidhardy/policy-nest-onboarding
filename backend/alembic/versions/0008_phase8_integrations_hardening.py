"""Phase 8 SMS delivery, inbound webhook logs, email retry telemetry, and health probes.

Revision ID: 0008_phase8_integrations
Revises: 0007_phase7_admin_config
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_phase8_integrations"
down_revision: str | None = "0007_phase7_admin_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "email_deliveries",
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "email_deliveries",
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "sms_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="SET NULL"),
        ),
        sa.Column("recipient_mobile", sa.String(length=24), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("body_preview", sa.String(length=320), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("provider_message_id", sa.String(length=128), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_sms_deliveries_user_id", "sms_deliveries", ["user_id"])
    op.create_index("ix_sms_deliveries_application_id", "sms_deliveries", ["application_id"])
    op.create_index("ix_sms_deliveries_status", "sms_deliveries", ["status"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("external_event_id", sa.String(length=128), nullable=True),
        sa.Column("signature_valid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="SET NULL"),
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_webhook_deliveries_source", "webhook_deliveries", ["source"])
    op.create_index("ix_webhook_deliveries_processing_status", "webhook_deliveries", ["processing_status"])
    op.create_index("ix_webhook_deliveries_application_id", "webhook_deliveries", ["application_id"])
    op.create_index(
        "uq_webhook_source_event",
        "webhook_deliveries",
        ["source", "external_event_id"],
        unique=True,
        postgresql_where=sa.text("external_event_id IS NOT NULL"),
    )

    op.create_table(
        "integration_probes",
        sa.Column("adapter_key", sa.String(length=48), primary_key=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("mode", sa.String(length=24), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("http_status", sa.SmallInteger(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("checked_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
    )


def downgrade() -> None:
    op.drop_table("integration_probes")
    op.drop_index("uq_webhook_source_event", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_application_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_processing_status", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_source", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_sms_deliveries_status", table_name="sms_deliveries")
    op.drop_index("ix_sms_deliveries_application_id", table_name="sms_deliveries")
    op.drop_index("ix_sms_deliveries_user_id", table_name="sms_deliveries")
    op.drop_table("sms_deliveries")
    op.drop_column("email_deliveries", "last_attempt_at")
    op.drop_column("email_deliveries", "attempts")
