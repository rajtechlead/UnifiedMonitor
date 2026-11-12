"""User model — authentication and authorization."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from unimonitor.db.base import Base

if TYPE_CHECKING:
    from unimonitor.db.models.tenant import Tenant

# Exported as both names for backwards compat with imports
UserRole = Literal["admin", "analyst", "auditor", "viewer"]


class AppUser(Base):
    """Application user — supports both local auth and Entra ID SSO."""

    __tablename__ = "app_users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Entra ID object ID for SSO users (no local password)
    entra_oid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    role: Mapped[str] = mapped_column(String(50), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="users")
    audit_logs: Mapped[list[AuditLog]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "AuditLog", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def can_write(self) -> bool:
        return self.role in ("admin", "analyst")

    def has_role(self, *roles: str) -> bool:
        """Return True if the user's role matches any of the given role names.

        Accepts both plain string roles and UserRole literal values.
        ``require_role("analyst")`` also grants access to ``"admin"`` role.
        """
        # Admin always has access to everything
        if self.role == "admin":
            return True
        return self.role in roles

    def __repr__(self) -> str:
        return f"<AppUser {self.email!r} role={self.role}>"


# Alias for code that imports User
User = AppUser
