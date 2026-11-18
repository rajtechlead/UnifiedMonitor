"""Finding triage workflow columns.

Revision ID: 002
Revises: 001
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("findings") as batch:
        batch.add_column(sa.Column("triage_status", sa.String(32), nullable=False, server_default="open"))
        batch.add_column(sa.Column("assignee_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_findings_triage_status", ["triage_status"])
        batch.create_index("ix_findings_assignee_id", ["assignee_id"])
        batch.create_foreign_key(
            "fk_findings_assignee_id_app_users",
            "app_users",
            ["assignee_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("findings") as batch:
        batch.drop_constraint("fk_findings_assignee_id_app_users", type_="foreignkey")
        batch.drop_index("ix_findings_assignee_id")
        batch.drop_index("ix_findings_triage_status")
        batch.drop_column("snoozed_until")
        batch.drop_column("assignee_id")
        batch.drop_column("triage_status")
