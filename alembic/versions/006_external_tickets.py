"""External tickets created by the Jira/ServiceNow sync.

Revision ID: 006
Revises: 005
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_tickets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(32), nullable=False, index=True),
        sa.Column("external_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("url", sa.String(512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("finding_id", "provider", name="uq_external_ticket_finding_provider"),
    )


def downgrade() -> None:
    op.drop_table("external_tickets")
