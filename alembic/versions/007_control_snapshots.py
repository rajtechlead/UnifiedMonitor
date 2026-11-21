"""Immutable per-control state written by every assessment run.

Revision ID: 007
Revises: 006
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "control_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "assessment_run_id",
            sa.String(36),
            sa.ForeignKey("assessment_runs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("control_id", sa.String(64), nullable=False, index=True),
        sa.Column("external_control_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("severity", sa.String(32), nullable=False, server_default="medium"),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )
    op.create_index(
        "ix_control_snapshots_tenant_control_time",
        "control_snapshots",
        ["tenant_id", "control_id", "checked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_control_snapshots_tenant_control_time", table_name="control_snapshots")
    op.drop_table("control_snapshots")
