"""Imported Zero Trust assessment runs and their individual checks."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from unimonitor.db.base import Base


class ZeroTrustRun(Base):
    """One assessment snapshot for a platform.

    Microsoft 365 runs are imported from the Zero Trust Assessment export; the
    cloud platforms are evaluated from collected evidence on demand.
    """

    __tablename__ = "zerotrust_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    # microsoft | aws | gcp | google_workspace
    source: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    warned: Mapped[int] = mapped_column(Integer, default=0)
    not_run: Mapped[int] = mapped_column(Integer, default=0)
    # JSON: per-pillar breakdown from zerotrust.normalise.summarise
    pillars: Mapped[str | None] = mapped_column(Text, nullable=True)
    # How the run arrived: "import" (PowerShell export) or "collector" (evidence)
    origin: Mapped[str] = mapped_column(String(32), default="import")
    imported_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    checks: Mapped[list[ZeroTrustCheck]] = relationship("ZeroTrustCheck", back_populates="run", cascade="all, delete-orphan")


class ZeroTrustCheck(Base):
    """One test result inside a run, including the remediation Microsoft prints."""

    __tablename__ = "zerotrust_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("zerotrust_runs.id", ondelete="CASCADE"), index=True)
    check_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512))
    pillar: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    # pass | fail | warn | not_run | not_applicable
    status: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # JSON array of remediation steps
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(512), nullable=True)

    run: Mapped[ZeroTrustRun] = relationship("ZeroTrustRun", back_populates="checks")
