"""Report model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from unimonitor.db.base import Base


class ReportStatus(enum.StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    assessment_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("assessment_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default=ReportStatus.PENDING.value)
    formats: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list: ["pdf", "excel"]
    file_paths: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON dict: {fmt: path}
    report_type: Mapped[str] = mapped_column(String(64), default="full")
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)  # user ID
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
