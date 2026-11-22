"""Tenant scoping for every endpoint that accepts a ``tenant_id``.

A query parameter is caller-controlled, so it can never be trusted on its own.
These helpers decide what a request may see:

* an administrator may read any tenant, and may omit ``tenant_id`` to read the
  whole install (the MSP rollup and cross-tenant dashboards rely on that);
* everyone else is pinned to their home tenant, plus any tenant they hold a
  delegated ``tenant_access`` grant on;
* an authenticated account with no home tenant and no grant sees nothing.

Endpoints take ``tenant_id: Annotated[str | None, Depends(tenant_scope)]`` so the
check cannot be forgotten in a handler.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user
from unimonitor.db import get_async_session
from unimonitor.exceptions import AuthorisationError


async def has_tenant_access(session: AsyncSession, user: Any, tenant_id: str) -> bool:
    """Home tenant, delegated grant, or the administrator role."""
    if getattr(user, "role", "") == "admin":
        return True
    if getattr(user, "tenant_id", None) == tenant_id:
        return True

    from unimonitor.db.models.tenant_access import TenantAccess

    granted = await session.execute(
        select(TenantAccess.id).where(TenantAccess.user_id == getattr(user, "id", None), TenantAccess.tenant_id == tenant_id)
    )
    return granted.scalar_one_or_none() is not None


async def resolve_tenant(session: AsyncSession, user: Any, requested: str | None) -> str | None:
    """The tenant this caller may act on, or 403 when it may not act on it.

    Use this for ``tenant_id`` values carried in a request body or a Pydantic
    query model, which bypass a parameter dependency.
    """
    if getattr(user, "role", "") == "admin":
        return requested

    home = getattr(user, "tenant_id", None)
    if requested is None:
        if not home:
            raise AuthorisationError("This account is not attached to a tenant.")
        return home
    if requested == home:
        return requested
    if await has_tenant_access(session, user, requested):
        return requested
    raise AuthorisationError("You do not have access to this tenant.")


async def tenant_scope(
    current_user: Annotated[Any, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[
        str | None,
        Query(description="Tenant to read. Administrators may omit it for the whole install."),
    ] = None,
) -> str | None:
    """The tenant this request may read, or 403 when it may not read it."""
    # Declared as a Query so the parameter appears in the OpenAPI document the SPA is
    # written against; reading request.query_params hid it from every client generator.
    return await resolve_tenant(session, current_user, tenant_id)


__all__ = ["has_tenant_access", "resolve_tenant", "tenant_scope"]
