"""Tenant repository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.db.models.tenant import Tenant, TenantConfig
from unimonitor.db.repositories.base import BaseRepository


class TenantRepository(BaseRepository[Tenant]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Tenant, session)

    # ── Convenience wrappers ──────────────────────────────────────

    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        return await self.get(tenant_id)

    async def update(self, tenant_id: str, **kwargs: Any) -> Tenant:  # type: ignore[override]
        obj = await self.get_or_raise(tenant_id)
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def soft_delete(self, tenant_id: str) -> None:
        obj = await self.get_or_raise(tenant_id)
        obj.is_active = False
        await self.session.flush()

    # ── Lookup by entra/ms tenant ID ─────────────────────────────

    async def get_by_entra_id(self, entra_tenant_id: str) -> Tenant | None:
        """Look up by the Azure AD / Entra tenant ID (tenant_id column)."""
        result = await self.session.execute(
            select(Tenant).where(Tenant.tenant_id == entra_tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_by_ms_tenant_id(self, ms_tenant_id: str) -> Tenant | None:
        """Alias for get_by_entra_id — backward compat."""
        return await self.get_by_entra_id(ms_tenant_id)

    # ── Paginated list ────────────────────────────────────────────

    async def list_paginated(
        self,
        page: int = 1,
        page_size: int = 25,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[Sequence[Tenant], int]:
        """Return (tenants, total) with optional search and active filter."""
        conditions = []
        if is_active is not None:
            conditions.append(Tenant.is_active.is_(is_active))
        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(
                    Tenant.name.ilike(pattern),
                    Tenant.display_name.ilike(pattern),
                    Tenant.domain.ilike(pattern),
                )
            )

        where_clause = and_(*conditions) if conditions else True

        # Count
        count_q = select(func.count(Tenant.id)).where(where_clause)
        total_result = await self.session.execute(count_q)
        total = total_result.scalar_one()

        # Rows
        offset = (page - 1) * page_size
        rows_q = (
            select(Tenant)
            .where(where_clause)
            .order_by(Tenant.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows_result = await self.session.execute(rows_q)
        return rows_result.scalars().all(), total

    # ── Collection stats ──────────────────────────────────────────

    async def get_collection_stats(self, tenant_id: str, hours: int = 24) -> dict:
        """Return basic collection statistics for a tenant over the past N hours."""
        # Try to import CollectionRun model; fall back gracefully if not present
        try:
            from unimonitor.db.models.collection import CollectionRun  # type: ignore[import]

            since = datetime.now(timezone.utc) - timedelta(hours=hours)
            total_q = select(func.count(CollectionRun.id)).where(
                and_(
                    CollectionRun.tenant_id == tenant_id,
                    CollectionRun.started_at >= since,
                )
            )
            total_result = await self.session.execute(total_q)
            total_runs = total_result.scalar_one()

            failed_q = select(func.count(CollectionRun.id)).where(
                and_(
                    CollectionRun.tenant_id == tenant_id,
                    CollectionRun.started_at >= since,
                    CollectionRun.status == "failed",
                )
            )
            failed_result = await self.session.execute(failed_q)
            failed_runs = failed_result.scalar_one()

            return {"total_runs": total_runs, "failed_runs": failed_runs}
        except Exception:
            # CollectionRun model not yet present — return zeros
            return {"total_runs": 0, "failed_runs": 0}

    # ── Config helpers ────────────────────────────────────────────

    async def get_with_config(self, tenant_id: str) -> Tenant | None:
        result = await self.session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs: Any) -> Tenant:  # type: ignore[override]
        """Override to remap entra_tenant_id → tenant_id before construction."""
        if "entra_tenant_id" in kwargs:
            kwargs["tenant_id"] = kwargs.pop("entra_tenant_id")
        return await super().create(**kwargs)

    async def get_or_create(
        self,
        ms_tenant_id: str,
        display_name: str,
        domain: str | None = None,
    ) -> tuple[Tenant, bool]:
        tenant = await self.get_by_ms_tenant_id(ms_tenant_id)
        if tenant:
            return tenant, False
        tenant = Tenant(
            tenant_id=ms_tenant_id,
            name=ms_tenant_id,
            display_name=display_name,
            domain=domain,
        )
        self.session.add(tenant)
        await self.session.flush()
        return tenant, True


class UserRepository(BaseRepository):  # type: ignore[type-arg]
    """Minimal user repository for OAuth upsert operations."""

    def __init__(self, session: AsyncSession) -> None:
        from unimonitor.db.models.user import AppUser
        super().__init__(AppUser, session)

    async def upsert_from_entra(self, user_info: dict):
        """Create or update an AppUser from Entra ID user info dict."""
        from unimonitor.db.models.user import AppUser
        from sqlalchemy import select

        entra_oid = user_info.get("entra_oid") or user_info.get("id", "")
        email = user_info.get("email", "")

        # Try by entra_oid first, then email
        result = await self.session.execute(
            select(AppUser).where(AppUser.entra_oid == entra_oid)
        )
        db_user = result.scalar_one_or_none()

        if not db_user and email:
            result = await self.session.execute(
                select(AppUser).where(AppUser.email == email)
            )
            db_user = result.scalar_one_or_none()

        if db_user:
            # Update existing
            db_user.entra_oid = entra_oid
            db_user.full_name = user_info.get("display_name", db_user.full_name)
            if email:
                db_user.email = email
            await self.session.flush()
            return db_user

        # Create new user
        db_user = AppUser(
            email=email,
            full_name=user_info.get("display_name", ""),
            entra_oid=entra_oid,
            role="viewer",
            is_active=True,
        )
        self.session.add(db_user)
        await self.session.flush()
        return db_user
