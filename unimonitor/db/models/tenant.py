"""Tenant model — multi-tenant isolation unit."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from unimonitor.db.base import Base

if TYPE_CHECKING:
    from unimonitor.db.models.user import AppUser


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Azure tenant ID (GUID) or "local" for local deployments
    # Also aliased as entra_tenant_id in the API layer
    tenant_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Human-readable display name (may differ from name slug)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_msp_client: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Graph API app registration — stored as references, resolved via secret provider
    client_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Secret reference key (not the actual secret) e.g. "unimonitor/tenants/{id}/client-secret"
    client_secret_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Plaintext secret for dev/test only (never stored in prod)
    client_secret: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Collection tracking
    last_collection_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_collection_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_collection_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSON blob for per-tenant config overrides
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def entra_tenant_id(self) -> str:
        """Alias for tenant_id — used by the API layer."""
        return self.tenant_id

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    users: Mapped[list[AppUser]] = relationship("AppUser", back_populates="tenant", lazy="select")
    assessments: Mapped[list[Assessment]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Assessment", back_populates="tenant", cascade="all, delete-orphan"
    )
    findings: Mapped[list[Finding]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Finding", back_populates="tenant", cascade="all, delete-orphan"
    )
    notification_setting: Mapped[NotificationSetting | None] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "NotificationSetting", back_populates="tenant", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.name!r} ({self.tenant_id})>"


class TenantConfig(Base):
    """Per-tenant configuration key-value store."""

    __tablename__ = "tenant_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # value is a secret reference (e.g. "azure_key_vault://...") or plain config value
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret_ref: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
