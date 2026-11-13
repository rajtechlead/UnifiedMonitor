"""Finding, evidence and history models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from unimonitor.db.base import Base

if TYPE_CHECKING:
    from unimonitor.db.models.control import Control
    from unimonitor.db.models.tenant import Tenant


class FindingState(StrEnum):
    IMPLEMENTED = "implemented"
    PARTIALLY_IMPLEMENTED = "partially_implemented"
    NOT_IMPLEMENTED = "not_implemented"
    NOT_APPLICABLE = "not_applicable"


class FindingSeverity(StrEnum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_WEIGHTS = {
    FindingSeverity.INFORMATIONAL: 1,
    FindingSeverity.LOW: 3,
    FindingSeverity.MEDIUM: 5,
    FindingSeverity.HIGH: 8,
    FindingSeverity.CRITICAL: 10,
}


class Finding(Base):
    """A security or compliance finding from a monitoring assessment."""

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    assessment_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assessment_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    control_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("controls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Identifier from the source control (e.g. "APP-001", "ZT-21894")
    external_control_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    state: Mapped[str] = mapped_column(String(32), default=FindingState.NOT_IMPLEMENTED.value, index=True)
    # Category / pillar (e.g. "Identity", "Devices")
    category: Mapped[str] = mapped_column(String(64), index=True)
    service: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "entra_id"
    # AI-generated remediation (JSON blob)
    ai_remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Risk scoring
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    # Flags
    is_suppressed: Mapped[bool] = mapped_column(default=False)
    suppression_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="findings")
    control: Mapped[Control | None] = relationship("Control", back_populates="findings")
    evidence: Mapped[list[FindingEvidence]] = relationship("FindingEvidence", back_populates="finding", cascade="all, delete-orphan")
    history: Mapped[list[FindingHistory]] = relationship("FindingHistory", back_populates="finding", cascade="all, delete-orphan")

    @property
    def severity_weight(self) -> int:
        return SEVERITY_WEIGHTS.get(FindingSeverity(self.severity), 0)

    def __repr__(self) -> str:
        return f"<Finding {self.external_control_id} [{self.severity}/{self.state}]>"


class FindingEvidence(Base):
    """Evidence artefact attached to a finding."""

    __tablename__ = "finding_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    finding_id: Mapped[str] = mapped_column(String(36), ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(64))  # "api_response", "screenshot", "log"
    source: Mapped[str] = mapped_column(String(256))  # Graph API endpoint or description
    content: Mapped[str] = mapped_column(Text)  # JSON or text evidence
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    finding: Mapped[Finding] = relationship("Finding", back_populates="evidence")


class FindingHistory(Base):
    """Audit trail of state changes on a finding."""

    __tablename__ = "finding_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    finding_id: Mapped[str] = mapped_column(String(36), ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    previous_state: Mapped[str] = mapped_column(String(32))
    new_state: Mapped[str] = mapped_column(String(32))
    changed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)  # user ID
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    finding: Mapped[Finding] = relationship("Finding", back_populates="history")
