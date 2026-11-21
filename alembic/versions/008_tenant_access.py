"""Delegated per-tenant access for MSP operators.

Revision ID: 008
Revises: 007
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_access",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("granted_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_tenant_access_user_tenant"),
    )


def downgrade() -> None:
    op.drop_table("tenant_access")
