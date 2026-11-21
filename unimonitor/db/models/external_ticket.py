"""Tickets created in an external tracker for a finding.

One row per (finding, provider) so a sync is idempotent: pressing sync twice
updates nothing and opens no duplicate tickets.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from unimonitor.db.base import Base

if TYPE_CHECKING:
    from unimonitor.db.models.finding import Finding


class ExternalTicket(Base):
    """A Jira/ServiceNow/generic ticket opened for a finding."""

    __tablename__ = "external_tickets"
    __table_args__ = (UniqueConstraint("finding_id", "provider", name="uq_external_ticket_finding_provider"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    finding_id: Mapped[str] = mapped_column(String(36), ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(128), default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    finding: Mapped[Finding] = relationship("Finding")
