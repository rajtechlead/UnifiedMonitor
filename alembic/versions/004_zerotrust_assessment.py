"""Zero Trust assessment runs and checks.

Revision ID: 004
Revises: 003
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zerotrust_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="completed"),
        sa.Column("score", sa.Float, nullable=False, server_default="0"),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("passed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("warned", sa.Integer, nullable=False, server_default="0"),
        sa.Column("not_run", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pillars", sa.Text, nullable=True),
        sa.Column("origin", sa.String(32), nullable=False, server_default="import"),
        sa.Column("imported_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_zerotrust_runs_tenant_id", "zerotrust_runs", ["tenant_id"])
    op.create_index("ix_zerotrust_runs_source", "zerotrust_runs", ["source"])
    op.create_index("ix_zerotrust_runs_created_at", "zerotrust_runs", ["created_at"])

    op.create_table(
        "zerotrust_checks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("zerotrust_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("pillar", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column("remediation", sa.Text, nullable=True),
        sa.Column("reference", sa.String(512), nullable=True),
    )
    op.create_index("ix_zerotrust_checks_run_id", "zerotrust_checks", ["run_id"])
    op.create_index("ix_zerotrust_checks_pillar", "zerotrust_checks", ["pillar"])
    op.create_index("ix_zerotrust_checks_status", "zerotrust_checks", ["status"])


def downgrade() -> None:
    op.drop_table("zerotrust_checks")
    op.drop_table("zerotrust_runs")
