"""Time-boxed finding exceptions.

Revision ID: 005
Revises: 004
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("suppression_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("findings", "suppression_expires_at")
