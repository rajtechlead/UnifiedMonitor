"""Risk item and risk score models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from unimonitor.db.base import Base


class RiskItem(Base):
    """A risk item derived from one or more findings."""

    __tablename__ = "risk_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), index=True)
    # Likelihood 1-5, Impact 1-5
    likelihood: Mapped[float] = mapped_column(Float, default=3.0)
    impact: Mapped[float] = mapped_column(Float, default=3.0)
    inherent_risk_score: Mapped[float] = mapped_column(Float, default=9.0)
    residual_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Risk level: low, medium, high, critical
    risk_level: Mapped[str] = mapped_column(String(32), default="medium")
    # Treatment: accept, mitigate, transfer, avoid
    treatment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(256), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_accepted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    scores: Mapped[list[RiskScore]] = relationship(
        "RiskScore", back_populates="risk_item", cascade="all, delete-orphan"
    )


class RiskScore(Base):
    """Point-in-time risk score snapshot for trending."""

    __tablename__ = "risk_scores"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    risk_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("risk_items.id", ondelete="CASCADE"), nullable=True, index=True
    )
    score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float, default=100.0)
    score_type: Mapped[str] = mapped_column(String(32))  # "security", "compliance", "risk"
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    risk_item: Mapped[RiskItem | None] = relationship("RiskItem", back_populates="scores")
