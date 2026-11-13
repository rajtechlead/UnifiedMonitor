"""Assessment and assessment run models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from unimonitor.db.base import Base

if TYPE_CHECKING:
    from unimonitor.db.models.tenant import Tenant


class AssessmentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Assessment(Base):
    """An assessment configuration (a set of frameworks/scopes for a tenant)."""

    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Comma-separated framework IDs
    frameworks: Mapped[str] = mapped_column(String(512), default="")
    # Comma-separated collector names
    collectors: Mapped[str] = mapped_column(String(512), default="")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="assessments")
    runs: Mapped[list[AssessmentRun]] = relationship("AssessmentRun", back_populates="assessment", cascade="all, delete-orphan")

    def framework_list(self) -> list[str]:
        return [f.strip() for f in self.frameworks.split(",") if f.strip()]

    def collector_list(self) -> list[str]:
        return [c.strip() for c in self.collectors.split(",") if c.strip()]


class AssessmentRun(Base):
    """A single execution run of an assessment."""

    __tablename__ = "assessment_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assessment_id: Mapped[str] = mapped_column(String(36), ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default=AssessmentStatus.PENDING.value, index=True)
    # Trigger: "scheduled", "manual", "api"
    trigger: Mapped[str] = mapped_column(String(32), default="manual")
    triggered_by: Mapped[str | None] = mapped_column(String(36), nullable=True)  # user ID

    # Scores (0–100)
    security_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    compliance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Finding counts
    critical_count: Mapped[int] = mapped_column(Integer, default=0)
    high_count: Mapped[int] = mapped_column(Integer, default=0)
    medium_count: Mapped[int] = mapped_column(Integer, default=0)
    low_count: Mapped[int] = mapped_column(Integer, default=0)
    informational_count: Mapped[int] = mapped_column(Integer, default=0)
    total_controls_checked: Mapped[int] = mapped_column(Integer, default=0)
    controls_passed: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Celery task ID for status tracking
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    assessment: Mapped[Assessment] = relationship("Assessment", back_populates="runs")
    findings: Mapped[list] = relationship(
        "Finding",
        primaryjoin="AssessmentRun.id == foreign(Finding.assessment_run_id)",
        viewonly=True,
        overlaps="findings",
    )

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
