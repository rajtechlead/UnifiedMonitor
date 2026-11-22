"""AI provider status and tenant-defined providers.

The settings page and the remediation button need to know which providers exist and
which are configured. Keys are never returned — only whether a provider has one.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.ai import custom
from unimonitor.ai.providers import configured_providers, provider_status
from unimonitor.ai.service import list_live_models
from unimonitor.auth.dependencies import get_current_user, require_role
from unimonitor.config import get_settings
from unimonitor.db.models.tenant import Tenant
from unimonitor.db.session import get_db

router = APIRouter()


async def _caller_tenant(current_user: Any, db: AsyncSession) -> Tenant:
    tenant = await db.get(Tenant, getattr(current_user, "tenant_id", "")) if current_user.tenant_id else None
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.get("/status")
async def ai_status(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Which providers are configured, in failover order, and their known models."""
    settings = get_settings()
    tenant = await db.get(Tenant, current_user.tenant_id) if current_user.tenant_id else None
    return {
        "enabled": bool(settings.AI_ENABLED),
        "providers": provider_status(),
        "active": [provider.name for provider in configured_providers()],
        "custom": await custom.public_list(tenant),
        "anonymised": True,
    }


@router.get("/models")
async def ai_models(
    current_user: Annotated[Any, Depends(get_current_user)],
) -> dict[str, Any]:
    """The full model list, asking each configured OpenAI-compatible provider live.

    A provider that cannot be reached is shown with its known catalogue instead, so the
    settings page still lists something useful while offline.
    """
    models: dict[str, list[str]] = {}
    for provider in configured_providers():
        models[provider.name] = await list_live_models(provider)
    return {"models": models}


class CustomProviderList(BaseModel):
    providers: list[custom.CustomProvider]


@router.get("/providers/custom")
async def list_custom_providers(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """The caller's tenant-defined OpenAI-compatible providers (keys masked)."""
    return await custom.public_list(await _caller_tenant(current_user, db))


@router.put(
    "/providers/custom",
    responses={
        400: {"description": "Duplicate or invalid provider"},
        404: {"description": "Tenant not found"},
    },
)
async def replace_custom_providers(
    body: CustomProviderList,
    current_user: Annotated[Any, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """Replace the tenant's provider list. Omitted keys keep their stored value.

    A provider that is dropped from the list has its key deleted from the secret
    provider, so removing one really removes the credential.
    """
    tenant = await _caller_tenant(current_user, db)
    try:
        updated = await custom.replace_all(tenant, body.providers)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.flush()
    return updated


__all__ = ["router"]
