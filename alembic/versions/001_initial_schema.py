"""Initial schema — all tables.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── tenants ──────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("entra_tenant_id", sa.String(36), nullable=False, unique=True),
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("client_secret", sa.Text, nullable=False),
        sa.Column("domain", sa.String(256), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, server_default="1"),
        sa.Column("plan", sa.String(32), default="standard", server_default="standard"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tenants_entra_tenant_id", "tenants", ["entra_tenant_id"])

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(256), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(256), nullable=True),
        sa.Column("full_name", sa.String(256), nullable=True),
        sa.Column("role", sa.String(32), server_default="viewer"),
        sa.Column("entra_user_id", sa.String(36), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="1"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"])

    # ── controls ──────────────────────────────────────────────────────────────
    op.create_table(
        "controls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_id", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("service", sa.String(64), nullable=True),
        sa.Column("framework_ids", sa.Text, nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("remediation", sa.Text, nullable=True),
        sa.Column("evaluate_code", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── assessments ───────────────────────────────────────────────────────────
    op.create_table(
        "assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("frameworks", sa.String(512), server_default=""),
        sa.Column("collectors", sa.String(512), server_default=""),
        sa.Column("is_active", sa.Boolean, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_assessments_tenant_id", "assessments", ["tenant_id"])

    # ── assessment_runs ───────────────────────────────────────────────────────
    op.create_table(
        "assessment_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("assessment_id", sa.String(36), sa.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("trigger", sa.String(32), server_default="manual"),
        sa.Column("triggered_by", sa.String(36), nullable=True),
        sa.Column("security_score", sa.Float, nullable=True),
        sa.Column("compliance_score", sa.Float, nullable=True),
        sa.Column("risk_score", sa.Float, nullable=True),
        sa.Column("critical_count", sa.Integer, server_default="0"),
        sa.Column("high_count", sa.Integer, server_default="0"),
        sa.Column("medium_count", sa.Integer, server_default="0"),
        sa.Column("low_count", sa.Integer, server_default="0"),
        sa.Column("informational_count", sa.Integer, server_default="0"),
        sa.Column("total_controls_checked", sa.Integer, server_default="0"),
        sa.Column("controls_passed", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("task_id", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_assessment_runs_assessment_id", "assessment_runs", ["assessment_id"])
    op.create_index("ix_assessment_runs_status", "assessment_runs", ["status"])

    # ── findings ──────────────────────────────────────────────────────────────
    op.create_table(
        "findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_run_id", sa.String(36), sa.ForeignKey("assessment_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("control_id", sa.String(36), sa.ForeignKey("controls.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_control_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), server_default="not_implemented"),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("service", sa.String(64), nullable=True),
        sa.Column("framework_ids", sa.Text, nullable=True),
        sa.Column("ai_remediation", sa.Text, nullable=True),
        sa.Column("risk_score", sa.Integer, server_default="0"),
        sa.Column("is_suppressed", sa.Boolean, server_default="0"),
        sa.Column("suppression_reason", sa.Text, nullable=True),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_findings_tenant_id", "findings", ["tenant_id"])
    op.create_index("ix_findings_severity", "findings", ["severity"])
    op.create_index("ix_findings_state", "findings", ["state"])
    op.create_index("ix_findings_external_control_id", "findings", ["external_control_id"])

    # ── finding_evidence ──────────────────────────────────────────────────────
    op.create_table(
        "finding_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_type", sa.String(64), nullable=False),
        sa.Column("source", sa.String(256), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_finding_evidence_finding_id", "finding_evidence", ["finding_id"])

    # ── finding_history ───────────────────────────────────────────────────────
    op.create_table(
        "finding_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_state", sa.String(32), nullable=False),
        sa.Column("new_state", sa.String(32), nullable=False),
        sa.Column("changed_by", sa.String(36), nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── reports ───────────────────────────────────────────────────────────────
    op.create_table(
        "reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_run_id", sa.String(36), sa.ForeignKey("assessment_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("formats", sa.Text, nullable=True),
        sa.Column("file_paths", sa.Text, nullable=True),
        sa.Column("report_type", sa.String(64), server_default="full"),
        sa.Column("task_id", sa.String(64), nullable=True),
        sa.Column("requested_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reports_tenant_id", "reports", ["tenant_id"])

    # ── notification_settings ─────────────────────────────────────────────────
    op.create_table(
        "notification_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("smtp_enabled", sa.Boolean, server_default="0"),
        sa.Column("smtp_to_emails", sa.Text, nullable=True),
        sa.Column("teams_webhook_url", sa.String(1024), nullable=True),
        sa.Column("slack_webhook_url", sa.String(1024), nullable=True),
        sa.Column("generic_webhook_url", sa.String(1024), nullable=True),
        sa.Column("immediate_alerts", sa.Boolean, server_default="1"),
        sa.Column("daily_digest", sa.Boolean, server_default="0"),
        sa.Column("weekly_digest", sa.Boolean, server_default="1"),
        sa.Column("alert_severity_threshold", sa.String(32), server_default="HIGH"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("notification_settings")
    op.drop_table("reports")
    op.drop_table("finding_history")
    op.drop_table("finding_evidence")
    op.drop_table("findings")
    op.drop_table("assessment_runs")
    op.drop_table("assessments")
    op.drop_table("controls")
    op.drop_table("users")
    op.drop_table("tenants")
