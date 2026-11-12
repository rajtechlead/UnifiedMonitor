"""Control, framework, and crosswalk mapping models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from unimonitor.db.base import Base


class Framework(Base):
    """A compliance/security framework (ISO 27001, NIST CSF, etc.)."""

    __tablename__ = "frameworks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Short identifier: "iso27001", "nist_csf", "cis_controls_v8", etc.
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    version: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Icon/badge for UI
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    controls: Mapped[list["Control"]] = relationship(
        "Control", back_populates="framework", cascade="all, delete-orphan"
    )


class Control(Base):
    """A single control within a framework."""

    __tablename__ = "controls"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    framework_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("frameworks.id", ondelete="CASCADE"), index=True
    )
    # Control reference number (e.g. "A.5.1", "PR.AA-01")
    reference: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Domain/category within the framework
    domain: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Collector that evaluates this control
    collector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Graph API endpoint(s) used (JSON array)
    graph_endpoints: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Recommended severity if failing
    default_severity: Mapped[str] = mapped_column(String(32), default="medium")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    framework: Mapped[Framework] = relationship("Framework", back_populates="controls")
    mappings: Mapped[list["ControlMapping"]] = relationship(
        "ControlMapping",
        foreign_keys="ControlMapping.source_control_id",
        back_populates="source_control",
        cascade="all, delete-orphan",
    )
    findings: Mapped[list["Finding"]] = relationship("Finding", back_populates="control")  # type: ignore[name-defined]  # noqa: F821


class ControlMapping(Base):
    """Cross-framework control mapping (crosswalk)."""

    __tablename__ = "control_mappings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source_control_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("controls.id", ondelete="CASCADE"), index=True
    )
    target_control_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("controls.id", ondelete="CASCADE"), index=True
    )
    # Mapping strength: "full", "partial", "related"
    relationship_type: Mapped[str] = mapped_column(String(32), default="full")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    source_control: Mapped[Control] = relationship(
        "Control",
        foreign_keys=[source_control_id],
        back_populates="mappings",
    )
    target_control: Mapped[Control] = relationship(
        "Control",
        foreign_keys=[target_control_id],
    )
