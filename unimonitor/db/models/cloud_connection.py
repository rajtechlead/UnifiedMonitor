"""Monitored-platform connection — one row per platform connected during setup.

This is the record the first-run wizard writes and the dashboard's "Connections"
settings read. Credentials never live here: `secret_refs` holds vault keys, so a
database dump or backup does not leak an app secret.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from unimonitor.db.base import Base


class CloudConnection(Base):
    __tablename__ = "cloud_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Registry id: microsoft | aws | gcp | google_workspace
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Account the connection points at: Entra tenant id, AWS account id, GCP project, Workspace customer
    account: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="connected")

    # Non-secret settings, JSON (region, project id, admin email, granted permissions)
    config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # Vault references, JSON: {"client_secret": "local_vault://unimonitor/..."}
    secret_refs: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<CloudConnection {self.provider} account={self.account!r} status={self.status}>"
