"""Built-in AI providers a tenant can connect and order for automatic failover.

The environment can carry a key per provider, but a tenant administrator may have their
own Freebuff/OpenAI/Anthropic/Groq credential and a different preference order. Keys go
to the secret provider (never to ``settings_json``), are write-only through the API and
are masked on read, exactly like tenant-defined custom providers.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from unimonitor.ai.custom import MASK, secret_name
from unimonitor.ai.providers import KNOWN_MODELS, Provider, configured_providers
from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger
from unimonitor.notifications.preferences import tenant_settings

logger = get_logger(__name__)

SETTINGS_KEY = "ai_builtin"
ORDER_KEY = "ai_order"
BUILTIN_NAMES = ("freebuff", "openai", "anthropic", "groq")


def _definition(name: str) -> dict[str, Any]:
    settings = get_settings()
    definitions = {
        "freebuff": {
            "label": "Freebuff gateway",
            "kind": "openai",
            "base_url": settings.FREEBUFF_BASE_URL,
            "model": settings.FREEBUFF_MODEL or KNOWN_MODELS["freebuff"][0],
            "free_tier": True,
        },
        "openai": {
            "label": "OpenAI",
            "kind": "openai",
            "base_url": settings.OPENAI_BASE_URL,
            "model": settings.OPENAI_MODEL,
            "free_tier": False,
        },
        "anthropic": {
            "label": "Anthropic Claude",
            "kind": "anthropic",
            "base_url": settings.ANTHROPIC_BASE_URL,
            "model": settings.ANTHROPIC_MODEL,
            "free_tier": False,
        },
        "groq": {
            "label": "Groq",
            "kind": "openai",
            "base_url": settings.GROQ_BASE_URL,
            "model": settings.GROQ_MODEL,
            "free_tier": True,
        },
    }
    if name not in definitions:
        raise ValueError(f"Unknown built-in provider '{name}'")
    return definitions[name]


class BuiltinProvider(BaseModel):
    """One built-in provider's tenant configuration. ``api_key`` is write-only."""

    name: str
    model: str = Field(default="", max_length=128)
    enabled: bool = True
    api_key: str = ""

    @field_validator("name")
    @classmethod
    def _known(cls, value: str) -> str:
        name = value.strip().lower()
        if name not in BUILTIN_NAMES:
            raise ValueError(f"Unknown built-in provider '{value}'")
        return name


def _key_name(tenant_id: str, name: str) -> str:
    return secret_name(tenant_id, f"builtin-{name}")


async def _read_key(tenant_id: str, name: str) -> str:
    from unimonitor.secrets import get_secret_resolver

    try:
        return await (await get_secret_resolver()).get(_key_name(tenant_id, name))
    except KeyError:
        return ""


async def key_for(tenant: Any, name: str) -> str:
    """The tenant's key for a built-in provider, falling back to the environment."""
    if tenant is not None:
        key = await _read_key(tenant.id, name)
        if key:
            return key
    return next((provider.api_key for provider in configured_providers() if provider.name == name), "")


async def _write_key(tenant_id: str, name: str, value: str) -> None:
    from unimonitor.secrets import get_secret_resolver

    resolver = await get_secret_resolver()
    full = _key_name(tenant_id, name)
    if value:
        await resolver.set(full, value, tags={"purpose": "ai-provider"})
        return
    try:
        await resolver.delete(full)
    except KeyError:
        pass


def _document(tenant: Any) -> dict[str, Any]:
    raw = tenant_settings(tenant).get(SETTINGS_KEY)
    return raw if isinstance(raw, dict) else {}


def stored(tenant: Any) -> dict[str, dict[str, Any]]:
    """Validated stored entries, skipping malformed ones instead of failing reads."""
    raw = _document(tenant).get("providers")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        try:
            provider = BuiltinProvider(
                name=str(name),
                model=str(entry.get("model") or ""),
                enabled=bool(entry.get("enabled", True)),
            )
        except (ValidationError, ValueError):
            continue
        result[provider.name] = {"model": provider.model, "enabled": provider.enabled}
    return result


def stored_order(tenant: Any) -> list[str]:
    raw = _document(tenant).get("order")
    if not isinstance(raw, list):
        return []
    return [str(name) for name in raw if str(name) in BUILTIN_NAMES]


async def public_status(tenant: Any) -> list[dict[str, Any]]:
    """Every built-in provider with its key state, model, position and enablement."""
    env_configured = {provider.name: provider for provider in configured_providers()}
    entries = stored(tenant) if tenant is not None else {}
    order = stored_order(tenant) if tenant is not None else []
    rows: list[dict[str, Any]] = []
    for name in BUILTIN_NAMES:
        definition = _definition(name)
        entry = entries.get(name, {})
        has_key = bool(await _read_key(tenant.id, name)) if tenant is not None else False
        rows.append(
            {
                "name": name,
                "label": definition["label"],
                "model": entry.get("model") or definition["model"],
                "default_model": definition["model"],
                "models": list(KNOWN_MODELS.get(name, ())),
                "free_tier": definition["free_tier"],
                "enabled": entry.get("enabled", True),
                "has_key": has_key,
                "env_configured": name in env_configured,
                "configured": has_key or name in env_configured,
                "key_hint": MASK if has_key else "",
                "position": order.index(name) if name in order else None,
            }
        )
    rows.sort(key=lambda row: (row["position"] is None, row["position"] or 0))
    return rows


async def save(tenant: Any, providers: list[BuiltinProvider], order: list[str] | None = None) -> list[dict[str, Any]]:
    """Persist models, enablement, keys and the failover order for one tenant."""
    names = [provider.name for provider in providers]
    if len(set(names)) != len(names):
        raise ValueError("Provider names must be unique")

    previous = set(stored(tenant))
    for provider in providers:
        if provider.api_key and provider.api_key != MASK:
            await _write_key(tenant.id, provider.name, provider.api_key)
        elif not provider.enabled and provider.name in previous:
            # Disabling keeps the key; only an explicit empty key removes it.
            continue
    for name in previous - set(names):
        await _write_key(tenant.id, name, "")

    wanted_order = [name for name in (order or names) if name in BUILTIN_NAMES]
    for name in names:
        if name not in wanted_order:
            wanted_order.append(name)

    document = tenant_settings(tenant)
    entry = _document(tenant)
    entry["providers"] = {provider.name: {"model": provider.model, "enabled": provider.enabled} for provider in providers}
    entry["order"] = wanted_order
    document[SETTINGS_KEY] = entry
    tenant.settings_json = json.dumps(document, sort_keys=True)
    return await public_status(tenant)


def provider_for(name: str, *, model: str = "", api_key: str = "") -> Provider:
    definition = _definition(name)
    return Provider(
        name=name,
        kind=definition["kind"],
        base_url=definition["base_url"],
        model=model or definition["model"],
        api_key=api_key,
        free_tier=definition["free_tier"],
        models=KNOWN_MODELS.get(name, ()),
    )


async def providers_for(tenant: Any) -> list[Provider]:
    """Tenant-keyed built-ins in the tenant's chosen order."""
    if tenant is None:
        return []
    entries = stored(tenant)
    order = stored_order(tenant) or list(entries)
    chain: list[Provider] = []
    for name in order:
        entry = entries.get(name)
        if not entry or not entry.get("enabled", True):
            continue
        key = await _read_key(tenant.id, name)
        if key:
            chain.append(provider_for(name, model=entry.get("model", ""), api_key=key))
    return chain


def failover_chain(tenant: Any, tenant_builtin: list[Provider], custom: list[Provider]) -> list[Provider]:
    """Custom providers first, then the tenant's built-ins, then environment ones.

    A provider the tenant configured themselves must not also be appended from the
    environment, otherwise a failed key would be retried with a different credential.
    """
    overridden = {provider.name for provider in tenant_builtin}
    return [*custom, *tenant_builtin, *[provider for provider in configured_providers() if provider.name not in overridden]]


async def test_provider(name: str, model: str = "", api_key: str = "") -> dict[str, Any]:
    """Make one small request so the UI can prove a key works before relying on it."""
    provider = provider_for(name, model=model, api_key=api_key)
    if not provider.api_key:
        return {"name": name, "ok": False, "error": "No API key is configured for this provider."}

    if provider.kind == "openai":
        url = f"{provider.base_url.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {provider.api_key}"}
    else:  # anthropic has no model list; a minimal message is the cheapest check
        url = f"{provider.base_url.rstrip('/')}/messages"
        headers = {"x-api-key": provider.api_key, "anthropic-version": "2023-06-01"}

    try:
        async with httpx.AsyncClient(timeout=15) as http:
            if provider.kind == "openai":
                response = await http.get(url, headers=headers)
            else:
                response = await http.post(
                    url,
                    headers=headers,
                    json={"model": provider.model, "max_tokens": 8, "messages": [{"role": "user", "content": "ping"}]},
                )
    except httpx.HTTPError as exc:
        return {"name": name, "ok": False, "error": type(exc).__name__}

    if response.status_code >= 400:
        return {"name": name, "ok": False, "error": f"HTTP {response.status_code}", "status_code": response.status_code}
    return {"name": name, "ok": True, "model": provider.model}


__all__ = [
    "BUILTIN_NAMES",
    "BuiltinProvider",
    "failover_chain",
    "key_for",
    "provider_for",
    "providers_for",
    "public_status",
    "save",
    "stored",
    "stored_order",
    "test_provider",
]
