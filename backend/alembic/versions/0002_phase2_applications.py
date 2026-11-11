"""Phase 2 applicant portal: applications, document uploads, history events, notifications, user preferred language.

Revision ID: 0002_phase2_applications
Revises: 0001_foundation
Create Date: 2026-11-11
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_phase2_applications"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("preferred_language", sa.String(8), nullable=False, server_default="EN"),
    )

    op.execute("CREATE SEQUENCE IF NOT EXISTS app_reference_seq START WITH 260001")

    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference_code", sa.String(24), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("current_step", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("region", sa.String(32)),
        sa.Column("sensitivity", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("preferred_language", sa.String(8), nullable=False, server_default="EN"),
        sa.Column("channel", sa.String(32), nullable=False, server_default="SELF_SERVICE"),
        sa.Column("full_name", sa.String(200)),
        sa.Column("date_of_birth", sa.Date),
        sa.Column("gender", sa.String(24)),
        sa.Column("father_or_spouse_name", sa.String(200)),
        sa.Column("mobile", sa.String(16)),
        sa.Column("email", sa.String(320)),
        sa.Column("pan_number", sa.String(10)),
        sa.Column("aadhaar_last4", sa.String(4)),
        sa.Column("address_line1", sa.String(255)),
        sa.Column("address_line2", sa.String(255)),
        sa.Column("city", sa.String(100)),
        sa.Column("district", sa.String(100)),
        sa.Column("state", sa.String(64)),
        sa.Column("pincode", sa.String(6)),
        sa.Column("same_as_permanent", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("permanent_address_line1", sa.String(255)),
        sa.Column("permanent_address_line2", sa.String(255)),
        sa.Column("permanent_city", sa.String(100)),
        sa.Column("permanent_state", sa.String(64)),
        sa.Column("permanent_pincode", sa.String(6)),
        sa.Column("education_level", sa.String(32)),
        sa.Column("board_name", sa.String(128)),
        sa.Column("school_or_university", sa.String(200)),
        sa.Column("passing_year", sa.SmallInteger),
        sa.Column("roll_number", sa.String(64)),
        sa.Column("result_status", sa.String(16)),
        sa.Column("percentage_or_cgpa", sa.String(32)),
        sa.Column("account_holder_name", sa.String(200)),
        sa.Column("bank_name", sa.String(128)),
        sa.Column("branch_name", sa.String(128)),
        sa.Column("ifsc_code", sa.String(11)),
        sa.Column("account_number_last4", sa.String(4)),
        sa.Column("account_number_masked", sa.String(32)),
        sa.Column("account_number_encrypted", sa.Text),
        sa.Column("account_type", sa.String(16)),
        sa.Column("is_joint_account", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_primary_holder", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("consent_terms", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("consent_kyc_processing", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("declaration_no_other_posp", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("declared_at", TZ),
        sa.Column("submitted_at", TZ),
        sa.Column("last_saved_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_applications"),
        sa.UniqueConstraint("reference_code", name="uq_applications_reference_code"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_applications_user_id_users"),
        sa.CheckConstraint("current_step BETWEEN 1 AND 6", name="ck_applications_step_range"),
        sa.CheckConstraint("sensitivity BETWEEN 1 AND 3", name="ck_applications_sensitivity_range"),
        sa.CheckConstraint(
            "aadhaar_last4 IS NULL OR aadhaar_last4 ~ '^[0-9]{4}$'",
            name="ck_applications_aadhaar_last4_digits",
        ),
    )
    op.create_index("ix_applications_user_id", "applications", ["user_id"])
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_index("ix_applications_pan_number", "applications", ["pan_number"])

    op.create_table(
        "application_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(32), nullable=False, server_default="UPLOADED"),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256_hash", sa.String(64), nullable=False),
        sa.Column("storage_provider", sa.String(24), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_application_documents"),
        sa.UniqueConstraint("storage_key", name="uq_application_documents_storage_key"),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name="fk_application_documents_application_id_applications",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_application_documents_uploaded_by_user_id_users",
        ),
    )
    op.create_index("ix_application_documents_application_id", "application_documents", ["application_id"])
    op.create_index("ix_application_documents_uploaded_by_user_id", "application_documents", ["uploaded_by_user_id"])
    op.create_index(
        "uq_current_application_doc",
        "application_documents",
        ["application_id", "doc_type"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    op.create_table(
        "application_events",
        sa.Column("id", sa.BigInteger, sa.Identity(), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_role", sa.String(32)),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("from_status", sa.String(32)),
        sa.Column("to_status", sa.String(32)),
        sa.Column("summary", sa.String(255), nullable=False),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_application_events"),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name="fk_application_events_application_id_applications",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_application_events_actor_user_id_users",
        ),
    )
    op.create_index("ix_application_events_application_id", "application_events", ["application_id"])

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True)),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("action_url", sa.String(255)),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("read_at", TZ),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_notifications_user_id_users"),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
            name="fk_notifications_application_id_applications",
        ),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_application_id", "notifications", ["application_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("application_events")
    op.drop_table("application_documents")
    op.drop_table("applications")
    op.execute("DROP SEQUENCE IF EXISTS app_reference_seq")
    op.drop_column("users", "preferred_language")
