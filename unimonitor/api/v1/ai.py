"""AI provider status.

The settings page and the remediation button need to know which providers exist and
which are configured. Keys are never returned — only whether a provider has one.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from unimonitor.ai.providers import configured_providers, provider_status
from unimonitor.ai.service import list_live_models
from unimonitor.auth.dependencies import get_current_user
from unimonitor.config import get_settings

router = APIRouter()


@router.get("/status")
async def ai_status(
    current_user: Annotated[Any, Depends(get_current_user)],
) -> dict[str, Any]:
    """Which providers are configured, in failover order, and their known models."""
    settings = get_settings()
    return {
        "enabled": bool(settings.AI_ENABLED),
        "providers": provider_status(),
        "active": [provider.name for provider in configured_providers()],
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
