"""NotificationSetting model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from unimonitor.db.base import Base

if TYPE_CHECKING:
    from unimonitor.db.models.tenant import Tenant


class NotificationSetting(Base):
    __tablename__ = "notification_settings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, index=True
    )

    # SMTP
    smtp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    smtp_to_emails: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list

    # Webhooks (stored encrypted at app level)
    teams_webhook_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    slack_webhook_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    generic_webhook_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Schedule flags
    immediate_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_digest: Mapped[bool] = mapped_column(Boolean, default=False)
    weekly_digest: Mapped[bool] = mapped_column(Boolean, default=True)

    # Thresholds
    alert_severity_threshold: Mapped[str] = mapped_column(String(32), default="HIGH")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="notification_setting")
