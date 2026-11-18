"""Alert policies, alerts, and the audit hash chain.

Revision ID: 003
Revises: 002
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("kind", sa.String(32), nullable=False, server_default="metric"),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("comparator", sa.String(8), nullable=False, server_default=">="),
        sa.Column("threshold", sa.Float, nullable=False, server_default="1"),
        sa.Column("window_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("severity", sa.String(32), nullable=False, server_default="HIGH"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("notify", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("template_key", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alert_policies_tenant_id", "alert_policies", ["tenant_id"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "policy_id",
            sa.String(36),
            sa.ForeignKey("alert_policies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("severity", sa.String(32), nullable=False, server_default="HIGH"),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("metric", sa.String(64), nullable=True),
        sa.Column("metric_value", sa.Float, nullable=True),
        sa.Column("threshold", sa.Float, nullable=True),
        sa.Column("assigned_to", sa.String(36), sa.ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_alerts_tenant_id", "alerts", ["tenant_id"])
    op.create_index("ix_alerts_policy_id", "alerts", ["policy_id"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_assigned_to", "alerts", ["assigned_to"])
    op.create_index("ix_alerts_triggered_at", "alerts", ["triggered_at"])

    # audit_logs is created by the app's metadata on existing deployments; a fresh
    # `alembic upgrade head` never saw it, so create it when it is missing.
    inspector = sa.inspect(op.get_bind())
    if "audit_logs" not in inspector.get_table_names():
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action", sa.String(128), nullable=False),
            sa.Column("resource_type", sa.String(64), nullable=True),
            sa.Column("resource_id", sa.String(36), nullable=True),
            sa.Column("payload", sa.Text, nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("user_agent", sa.String(512), nullable=True),
            sa.Column("correlation_id", sa.String(36), nullable=True),
            sa.Column("prev_hash", sa.String(64), nullable=True),
            sa.Column("entry_hash", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
        op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
        op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])
        op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    else:
        with op.batch_alter_table("audit_logs") as batch:
            batch.add_column(sa.Column("prev_hash", sa.String(64), nullable=True))
            batch.add_column(sa.Column("entry_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    if "audit_logs" in sa.inspect(op.get_bind()).get_table_names():
        columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("audit_logs")}
        with op.batch_alter_table("audit_logs") as batch:
            if "entry_hash" in columns:
                batch.drop_column("entry_hash")
            if "prev_hash" in columns:
                batch.drop_column("prev_hash")

    for index in (
        "ix_alerts_triggered_at",
        "ix_alerts_assigned_to",
        "ix_alerts_status",
        "ix_alerts_severity",
        "ix_alerts_policy_id",
        "ix_alerts_tenant_id",
    ):
        op.drop_index(index, table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_alert_policies_tenant_id", table_name="alert_policies")
    op.drop_table("alert_policies")
