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


def tenant_secret_name(identifier: str) -> str:
    """Vault entry for a tenant's own Graph client secret."""
    return f"unimonitor-tenant-{identifier}-graph-secret"


async def store_tenant_secret(identifier: str, value: str) -> str:
    """Write a tenant credential to the secret provider and return its reference.

    The `Tenant` model's plaintext column exists for legacy rows; new credentials are
    never written to the database.
    """
    from unimonitor.secrets import get_secret_resolver

    name = tenant_secret_name(identifier)
    await (await get_secret_resolver()).set(name, value, tags={"purpose": "tenant-graph"})
    return name


async def resolve_tenant_secret(tenant: Tenant) -> str | None:
    """A tenant's stored Graph secret: the vault reference first, legacy plaintext last."""
    ref = getattr(tenant, "client_secret_ref", None)
    if ref:
        from unimonitor.secrets import get_secret_resolver

        try:
            return await (await get_secret_resolver()).get(ref)
        except KeyError:
            return None
    return getattr(tenant, "client_secret", None)
