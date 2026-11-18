"""Alert policy and alert models.

A policy describes a condition over findings or assessment history; an alert is
one triggered occurrence with the handler workflow (acknowledge, snooze, assign,
resolve). Kept separate from findings: a finding is a control result, an alert is
a notification that something crossed a threshold.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from unimonitor.db.base import Base

if TYPE_CHECKING:
    from unimonitor.db.models.tenant import Tenant


class AlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    SNOOZED = "snoozed"
    RESOLVED = "resolved"


class AlertKind(StrEnum):
    METRIC = "metric"
    ACTIVITY = "activity"
    ANOMALY = "anomaly"


# Metrics a policy can watch. `security_score_drop` and `new_findings` are the
# anomaly/activity metrics; the rest are point-in-time counts.
METRICS: dict[str, str] = {
    "critical_findings": "Unresolved critical findings",
    "high_findings": "Unresolved high findings",
    "open_findings": "All unresolved findings",
    "risk_score": "Average finding risk score",
    "new_findings": "Findings first seen in the window",
    "security_score_drop": "Security score drop over the window",
}

COMPARATORS = (">=", ">", "<=", "<")


class AlertPolicy(Base):
    __tablename__ = "alert_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(32), default=AlertKind.METRIC.value)
    metric: Mapped[str] = mapped_column(String(64))
    comparator: Mapped[str] = mapped_column(String(8), default=">=")
    threshold: Mapped[float] = mapped_column(Float, default=1.0)
    window_hours: Mapped[int] = mapped_column(Integer, default=24)
    severity: Mapped[str] = mapped_column(String(32), default="HIGH")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notify: Mapped[bool] = mapped_column(Boolean, default=True)
    template_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tenant: Mapped[Tenant] = relationship("Tenant")
    alerts: Mapped[list[Alert]] = relationship("Alert", back_populates="policy", cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    policy_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("alert_policies.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), default="HIGH", index=True)
    status: Mapped[str] = mapped_column(String(32), default=AlertStatus.OPEN.value, index=True)
    metric: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(36), ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    policy: Mapped[AlertPolicy | None] = relationship("AlertPolicy", back_populates="alerts")


# Seeded policy templates; the UI offers these and the API copies one into a policy.
ALERT_TEMPLATES: tuple[dict, ...] = (
    {
        "key": "critical-findings",
        "name": "Critical findings present",
        "description": "Alert when any unresolved critical finding exists.",
        "kind": "metric",
        "metric": "critical_findings",
        "comparator": ">=",
        "threshold": 1,
        "window_hours": 24,
        "severity": "CRITICAL",
    },
    {
        "key": "high-findings-spike",
        "name": "High findings spike",
        "description": "Alert when unresolved high findings reach ten.",
        "kind": "anomaly",
        "metric": "high_findings",
        "comparator": ">=",
        "threshold": 10,
        "window_hours": 24,
        "severity": "HIGH",
    },
    {
        "key": "new-findings",
        "name": "New findings in the last day",
        "description": "Alert on activity: findings first seen in the last 24 hours.",
        "kind": "activity",
        "metric": "new_findings",
        "comparator": ">=",
        "threshold": 5,
        "window_hours": 24,
        "severity": "MEDIUM",
    },
    {
        "key": "score-drop",
        "name": "Security score drop",
        "description": "Alert when the security score falls ten points over a week.",
        "kind": "anomaly",
        "metric": "security_score_drop",
        "comparator": ">=",
        "threshold": 10,
        "window_hours": 168,
        "severity": "HIGH",
    },
    {
        "key": "risk-spike",
        "name": "Average finding risk",
        "description": "Alert when the average finding risk score reaches eight.",
        "kind": "metric",
        "metric": "risk_score",
        "comparator": ">=",
        "threshold": 8,
        "window_hours": 24,
        "severity": "MEDIUM",
    },
)
