"""Tenant resolution shared by the API modules."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.db.models.tenant import Tenant


async def resolve_tenant(db: AsyncSession, tenant_id: str | None) -> Tenant:
    """The requested tenant, or the first active one for single-tenant installs."""
    stmt = select(Tenant).where(Tenant.id == tenant_id) if tenant_id else select(Tenant).where(Tenant.is_active)
    tenant = (await db.execute(stmt.order_by(Tenant.created_at).limit(1))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant
