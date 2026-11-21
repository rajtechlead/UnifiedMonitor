"""Delegated access to a tenant.

An MSP operator needs to see a client tenant without turning every operator into
an administrator of every client. This table grants one user one role on one
tenant; it is deliberately separate from ``AppUser.tenant_id`` (which stays the
user's home tenant) so delegation can be revoked without moving the account.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from unimonitor.db.base import Base


class TenantAccess(Base):
    __tablename__ = "tenant_access"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id", name="uq_tenant_access_user_tenant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    # Role is scoped to this tenant; it never widens the user's global role.
    role: Mapped[str] = mapped_column(String(32), default="viewer", nullable=False)
    granted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<TenantAccess {self.user_id}@{self.tenant_id} {self.role}>"
