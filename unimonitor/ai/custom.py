"""Tenant-defined AI providers.

Not every deployment wants the built-in providers: some run an internal gateway or a
regional vendor. A tenant administrator can register an OpenAI-compatible endpoint
here, and it is tried before the built-in chain. The API key never touches
``settings_json`` — it goes to the secret provider like every other credential.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from unimonitor.ai.providers import Provider
from unimonitor.notifications.preferences import tenant_settings

SETTINGS_KEY = "ai_providers"
MASK = "******"
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")


class CustomProvider(BaseModel):
    """One tenant-provided endpoint. ``api_key`` is write-only."""

    name: str = Field(min_length=2, max_length=32)
    base_url: str = Field(min_length=8, max_length=512)
    model: str = Field(min_length=1, max_length=128)
    api_key: str = ""
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def _slug(cls, value: str) -> str:
        if not _NAME.match(value):
            raise ValueError("Use 2-32 lowercase letters, digits or dashes")
        return value

    @field_validator("base_url")
    @classmethod
    def _https(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("base_url must start with https:// (or http:// for a local gateway)")
        return value.rstrip("/")


def secret_name(tenant_id: str, name: str) -> str:
    """Vault entry holding a tenant's key for its own provider."""
    return f"unimonitor-tenant-{tenant_id}-ai-{name}"


def stored(tenant: Any) -> list[dict[str, Any]]:
    """Custom providers as persisted, without their keys."""
    raw = tenant_settings(tenant).get(SETTINGS_KEY)
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in raw:
        if isinstance(entry, dict) and entry.get("name") and entry.get("base_url"):
            items.append(entry)
    return items


async def _read_key(tenant_id: str, name: str) -> str:
    from unimonitor.secrets import get_secret_resolver

    resolver = await get_secret_resolver()
    try:
        return await resolver.get(secret_name(tenant_id, name))
    except KeyError:
        return ""


async def _write_key(tenant_id: str, name: str, value: str) -> None:
    from unimonitor.secrets import get_secret_resolver

    resolver = await get_secret_resolver()
    full = secret_name(tenant_id, name)
    if value:
        await resolver.set(full, value, tags={"purpose": "ai-provider"})
        return
    try:
        await resolver.delete(full)
    except KeyError:
        pass


async def public_list(tenant: Any) -> list[dict[str, Any]]:
    """The tenant's providers with a masked key, for the settings page."""
    if tenant is None:
        return []
    result: list[dict[str, Any]] = []
    for entry in stored(tenant):
        has_key = bool(await _read_key(tenant.id, entry["name"]))
        result.append(
            {
                "name": entry["name"],
                "base_url": entry["base_url"],
                "model": entry["model"],
                "enabled": bool(entry.get("enabled", True)),
                "has_key": has_key,
                "api_key": MASK if has_key else "",
            }
        )
    return result


async def replace_all(tenant: Any, providers: list[CustomProvider]) -> list[dict[str, Any]]:
    """Replace the tenant's provider list.

    A key equal to the mask keeps the stored one; an empty key removes it; a provider
    that is no longer listed has its key deleted, so removing a provider really
    removes the credential.
    """
    names = [provider.name for provider in providers]
    if len(set(names)) != len(names):
        raise ValueError("Provider names must be unique")

    previous = {entry["name"] for entry in stored(tenant)}
    for provider in providers:
        if provider.api_key == MASK:
            continue
        await _write_key(tenant.id, provider.name, provider.api_key)
    for name in previous - set(names):
        await _write_key(tenant.id, name, "")

    document = tenant_settings(tenant)
    document[SETTINGS_KEY] = [
        {
            "name": provider.name,
            "base_url": provider.base_url,
            "model": provider.model,
            "enabled": provider.enabled,
        }
        for provider in providers
    ]
    tenant.settings_json = json.dumps(document, sort_keys=True)
    return await public_list(tenant)


async def providers_for(tenant: Any) -> list[Provider]:
    """Enabled custom providers, ready for the failover chain (keys resolved)."""
    result: list[Provider] = []
    for entry in stored(tenant):
        if not entry.get("enabled", True):
            continue
        key = await _read_key(tenant.id, entry["name"])
        if not key:
            continue
        result.append(
            Provider(
                name=f"custom:{entry['name']}",
                kind="openai",
                base_url=str(entry["base_url"]),
                model=str(entry["model"]),
                api_key=key,
                free_tier=False,
            )
        )
    return result


__all__ = ["CustomProvider", "MASK", "providers_for", "public_list", "replace_all", "secret_name", "stored"]
