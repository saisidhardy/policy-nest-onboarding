"""Phase 4 rules engine, decision management, appeals and reapplications.

Revision ID: 0004_phase4_rules_engine
Revises: 0003_phase3_doc_intelligence
Create Date: 2026-11-12
"""

import json
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_phase4_rules_engine"
down_revision = "0003_phase3_doc_intelligence"
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)

DEFAULT_RULES_CONFIG = {
    "min_age_years": 18,
    "min_ocr_confidence": 0.75,
    "face_match_auto_pass_threshold": 0.75,
    "face_match_rework_threshold": 0.60,
    "max_rework_cycles_before_human": 2,
    "auto_approve_enabled": True,
    "auto_reject_statutory": True,
    "never_auto_reject_name_mismatch": True,
    "recognized_education_boards": [
        "CBSE",
        "CISCE",
        "ICSE",
        "NIOS",
        "STATE BOARD",
        "MAHARASHTRA",
        "KARNATAKA",
        "TAMIL NADU",
        "UTTAR PRADESH",
        "WEST BENGAL",
        "DELHI",
        "GUJARAT",
        "RAJASTHAN",
        "KERALA",
        "TELANGANA",
        "ANDHRA PRADESH",
        "MADHYA PRADESH",
        "BIHAR",
        "PUNJAB",
        "HARYANA",
    ],
    "require_all_six_documents": True,
    "allow_bank_truncation_match": True,
}


def upgrade() -> None:
    op.add_column("applications", sa.Column("parent_application_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("applications", sa.Column("resolution_kind", sa.String(32), nullable=True))
    op.add_column("applications", sa.Column("reapplication_reason", sa.Text, nullable=True))
    op.add_column(
        "applications",
        sa.Column("rework_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    op.create_foreign_key(
        "fk_applications_parent_application_id",
        "applications",
        "applications",
        ["parent_application_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_applications_parent_application_id", "applications", ["parent_application_id"])

    op.create_table(
        "rule_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("rules_config", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("activated_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("activated_at", TZ),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_rule_sets"),
        sa.UniqueConstraint("version", name="uq_rule_sets_version"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_rule_sets_created_by_user_id",
        ),
        sa.ForeignKeyConstraint(
            ["activated_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_rule_sets_activated_by_user_id",
        ),
    )
    op.create_index("ix_rule_sets_status", "rule_sets", ["status"])
    op.create_index(
        "uq_active_rule_set",
        "rule_sets",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    op.create_table(
        "rule_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ruleset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ruleset_version", sa.String(32), nullable=False),
        sa.Column("trigger_source", sa.String(32), nullable=False),
        sa.Column("triggered_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("recommended_status", sa.String(32), nullable=False),
        sa.Column("eligibility_status", sa.String(24), nullable=False),
        sa.Column("completeness_status", sa.String(24), nullable=False),
        sa.Column("consistency_status", sa.String(24), nullable=False),
        sa.Column("risk_level", sa.String(24), nullable=False),
        sa.Column("auto_pass_eligible", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("requires_human_review", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("reason_codes", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("rule_results", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("rework_items", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("risk_indicators", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("executed_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_rule_executions"),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="CASCADE", name="fk_rule_exec_app_id"
        ),
        sa.ForeignKeyConstraint(["ruleset_id"], ["rule_sets.id"], ondelete="RESTRICT", name="fk_rule_exec_ruleset_id"),
        sa.ForeignKeyConstraint(
            ["triggered_by_user_id"], ["users.id"], ondelete="SET NULL", name="fk_rule_exec_user_id"
        ),
    )
    op.create_index("ix_rule_executions_application_id", "rule_executions", ["application_id"])
    op.create_index("ix_rule_executions_outcome", "rule_executions", ["outcome"])

    op.create_table(
        "application_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_execution_id", postgresql.UUID(as_uuid=True)),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decided_by_role", sa.String(32), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=False),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("is_override", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("override_of_outcome", sa.String(32)),
        sa.Column("reason_codes", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("reason_text", sa.Text, nullable=False),
        sa.Column("rework_items", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_application_decisions"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE", name="fk_app_dec_app_id"),
        sa.ForeignKeyConstraint(
            ["rule_execution_id"], ["rule_executions.id"], ondelete="SET NULL", name="fk_app_dec_rule_exec_id"
        ),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="RESTRICT", name="fk_app_dec_user_id"),
    )
    op.create_index("ix_application_decisions_application_id", "application_decisions", ["application_id"])
    op.create_index("ix_application_decisions_decision", "application_decisions", ["decision"])

    op.create_table(
        "application_appeals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("appeal_reason", sa.Text, nullable=False),
        sa.Column("supporting_notes", sa.Text),
        sa.Column("resolution_notes", sa.Text),
        sa.Column("resolved_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("resolved_at", TZ),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_application_appeals"),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="CASCADE", name="fk_app_appeal_app_id"
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"], ["users.id"], ondelete="RESTRICT", name="fk_app_appeal_submit_user_id"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"], ["users.id"], ondelete="SET NULL", name="fk_app_appeal_resolve_user_id"
        ),
    )
    op.create_index("ix_application_appeals_application_id", "application_appeals", ["application_id"])
    op.create_index("ix_application_appeals_status", "application_appeals", ["status"])

    # Seed approved PS-01 v3.2.0 rule set
    default_id = str(uuid.uuid4())
    op.execute(
        sa.text(
            """
            INSERT INTO rule_sets (id, version, name, description, status, is_active, rules_config, activated_at)
            VALUES (
                CAST(:id AS uuid),
                '3.2.0',
                'PS-01 POSP Onboarding Rulebook v3.2.0',
                'Approved baseline deterministic onboarding rules: statutory eligibility, 6-doc completeness, OCR & cross-doc identity guardrails, consolidated EN/HI rework.',
                'ACTIVE',
                true,
                CAST(:config AS jsonb),
                NOW()
            )
            """
        ).bindparams(id=default_id, config=json.dumps(DEFAULT_RULES_CONFIG))
    )


def downgrade() -> None:
    op.drop_index("ix_application_appeals_status", table_name="application_appeals")
    op.drop_index("ix_application_appeals_application_id", table_name="application_appeals")
    op.drop_table("application_appeals")

    op.drop_index("ix_application_decisions_decision", table_name="application_decisions")
    op.drop_index("ix_application_decisions_application_id", table_name="application_decisions")
    op.drop_table("application_decisions")

    op.drop_index("ix_rule_executions_outcome", table_name="rule_executions")
    op.drop_index("ix_rule_executions_application_id", table_name="rule_executions")
    op.drop_table("rule_executions")

    op.drop_index("uq_active_rule_set", table_name="rule_sets")
    op.drop_index("ix_rule_sets_status", table_name="rule_sets")
    op.drop_table("rule_sets")

    op.drop_index("ix_applications_parent_application_id", table_name="applications")
    op.drop_constraint("fk_applications_parent_application_id", "applications", type_="foreignkey")
    op.drop_column("applications", "rework_count")
    op.drop_column("applications", "reapplication_reason")
    op.drop_column("applications", "resolution_kind")
    op.drop_column("applications", "parent_application_id")
