"""Composite index for the findings list.

The list endpoint filters on tenant, state and severity and orders by recency; the
single-column indexes forced a scan per filter combination.

Revision ID: 009
Revises: 008
"""

from __future__ import annotations

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

INDEX = "ix_findings_tenant_state_severity_seen"


def upgrade() -> None:
    op.create_index(INDEX, "findings", ["tenant_id", "state", "severity", "last_seen_at"])


def downgrade() -> None:
    op.drop_index(INDEX, table_name="findings")
