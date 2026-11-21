"""Per-control state captured at the end of every assessment run.

Findings are mutable — triage, suppression and re-collection overwrite them — so
they cannot answer "how did this control trend over the last quarter". Each run
appends one immutable row per evaluated control instead, which is what the
control-level trend endpoints read.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from unimonitor.db.base import Base


class ControlSnapshot(Base):
    __tablename__ = "control_snapshots"
    __table_args__ = (Index("ix_control_snapshots_tenant_control_time", "tenant_id", "control_id", "checked_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("assessment_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    control_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_control_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<ControlSnapshot {self.control_id} {self.state} @{self.checked_at}>"
