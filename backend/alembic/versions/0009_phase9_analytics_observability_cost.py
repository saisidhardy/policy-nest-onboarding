"""Phase 9 Product analytics, journey tracking, turnaround SLAs, and cost intelligence.

Revision ID: 0009_phase9_analytics
Revises: 0008_phase8_integrations
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_phase9_analytics"
down_revision: str | None = "0008_phase8_integrations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Product Events Table
    op.create_table(
        "product_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("anonymous_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="SET NULL"), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=True),
        sa.Column("stage_duration_ms", sa.Integer(), nullable=True),
        sa.Column("active_time_ms", sa.Integer(), nullable=True),
        sa.Column("inactive_time_ms", sa.Integer(), nullable=True),
        sa.Column("waiting_time_ms", sa.Integer(), nullable=True),
        sa.Column("backend_time_ms", sa.Integer(), nullable=True),
        sa.Column("is_abandonment", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("validation_errors_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="web"),
        sa.Column("environment", sa.String(length=24), nullable=False, server_default="production"),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_product_events_name_created", "product_events", ["event_name", "created_at"])
    op.create_index("ix_product_events_app_created", "product_events", ["application_id", "created_at"])
    op.create_index("ix_product_events_session", "product_events", ["session_id"])
    op.create_index("ix_product_events_anon", "product_events", ["anonymous_id"])

    # 2. Workflow Stage Timings Table
    op.create_table(
        "workflow_stage_timings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_duration_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("waiting_duration_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("backend_processing_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reviewer_handling_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("applicant_response_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_sla_breached", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sla_threshold_hours", sa.Float(), nullable=False, server_default=sa.text("136.8")),
        sa.Column("is_externally_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("external_block_reason", sa.String(length=128), nullable=True),
    )
    op.create_index("ix_stage_timings_app_stage", "workflow_stage_timings", ["application_id", "stage"])

    # 3. API Cost Records Table
    op.create_table(
        "api_cost_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("service", sa.String(length=48), nullable=False),
        sa.Column("operation", sa.String(length=48), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("units_processed", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="SUCCESS"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("estimated_cost_inr", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("actual_cost_inr", sa.Float(), nullable=True),
        sa.Column("environment", sa.String(length=24), nullable=False, server_default="production"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_cost_records_prov_created", "api_cost_records", ["provider", "created_at"])
    op.create_index("ix_cost_records_app", "api_cost_records", ["application_id"])
    op.create_index("ix_cost_records_correlation", "api_cost_records", ["correlation_id"])

    # 4. Provider Pricing Registry Table
    op.create_table(
        "provider_pricing_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("service", sa.String(length=48), nullable=False),
        sa.Column("operation", sa.String(length=48), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=True),
        sa.Column("unit_type", sa.String(length=32), nullable=False),
        sa.Column("unit_price_inr", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_provider_pricing_prov", "provider_pricing_registry", ["provider"])

    # Seed baseline pricing records for standard providers
    op.execute(
        """
        INSERT INTO provider_pricing_registry (id, provider, service, operation, model_name, unit_type, unit_price_inr, is_active, notes)
        VALUES
            (gen_random_uuid(), 'GEMINI', 'GEMINI_VISION_OCR', 'DOCUMENT_EXTRACTION', 'gemini-1.5-flash', '1K_INPUT_TOKENS', 0.00625, true, 'Official Google Gemini Flash input token rate in INR'),
            (gen_random_uuid(), 'GEMINI', 'GEMINI_VISION_OCR', 'DOCUMENT_EXTRACTION', 'gemini-1.5-flash', '1K_OUTPUT_TOKENS', 0.025, true, 'Official Google Gemini Flash output token rate in INR'),
            (gen_random_uuid(), 'SETU', 'DIGILOCKER_GATEWAY', 'FETCH_DOCUMENT_XML', NULL, 'PER_VERIFICATION', 1.50, true, 'DigiLocker document retrieval via Setu/Sandbox API'),
            (gen_random_uuid(), 'CASHFREE', 'NPCI_IMPS_RAIL', 'BANK_ACCOUNT_PENNYDROP', NULL, 'PER_PENNYDROP', 1.00, true, 'Statutory 1.00 INR penny-drop verification inquiry'),
            (gen_random_uuid(), 'INDIA_POST', 'POSTAL_PIN_DIRECTORY', 'PINCODE_LOCATION_LOOKUP', NULL, 'PER_QUERY', 0.00, true, 'Free public master node (NIC / India Post)'),
            (gen_random_uuid(), 'RAZORPAY', 'RBI_IFSC_DIRECTORY', 'IFSC_BRANCH_LOOKUP', NULL, 'PER_QUERY', 0.00, true, 'Free open RBI branch directory lookup node')
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_table("provider_pricing_registry")
    op.drop_table("api_cost_records")
    op.drop_table("workflow_stage_timings")
    op.drop_table("product_events")
