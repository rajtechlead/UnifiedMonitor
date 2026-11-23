"""Tenant-defined AI providers.

Not every deployment wants the built-in providers: some run an internal gateway or a
regional vendor. A tenant administrator can register an OpenAI-compatible endpoint
here, and it is tried before the built-in chain. The API key never touches
``settings_json`` — it goes to the secret provider like every other credential.
"""

from __future__ import annotations

import ipaddress
import json
import re
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, ValidationError, field_validator

from unimonitor.ai.providers import Provider
from unimonitor.core.logging import get_logger
from unimonitor.notifications.preferences import tenant_settings

logger = get_logger(__name__)

SETTINGS_KEY = "ai_providers"
MASK = "******"
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")

# Names and addresses that answer with cloud instance credentials. A tenant
# administrator may point a provider at an internal gateway, but never at the
# host's metadata service: that would let a model request mint cloud credentials.
_BLOCKED_HOSTNAMES = frozenset(
    {
        "metadata",
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
        "instance-data.ec2.internal",
    }
)
_BLOCKED_ADDRESSES = frozenset(
    ipaddress.ip_address(address)
    for address in (
        "169.254.169.254",  # AWS, Azure, GCP, OpenStack
        "169.254.170.2",  # ECS task credentials
        "100.100.100.200",  # Alibaba Cloud
        "192.0.0.192",  # Oracle Cloud
        "fd00:ec2::254",  # AWS IPv6
    )
)
_LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain"})


def _is_loopback(host: str) -> bool:
    """True for a host that only reaches the local machine."""
    if host in _LOOPBACK_NAMES or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _validate_target(value: str) -> str:
    """Reject schemes, credentials and addresses a provider must never reach."""
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https"):
        raise ValueError("base_url must start with https:// (or http:// for a local gateway)")
    if parts.username or parts.password:
        raise ValueError("base_url must not carry credentials")
    host = (parts.hostname or "").strip().rstrip(".").lower()
    if not host:
        raise ValueError("base_url must include a host")
    if host in _BLOCKED_HOSTNAMES:
        raise ValueError("base_url must not point at a cloud metadata service")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
        # A single all-numeric label is an alternative encoding of an IPv4 literal.
        if host.replace(".", "").isdigit():
            raise ValueError("base_url must use a hostname or canonical IP address") from None

    if address is not None:
        candidates: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = [address]
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
            candidates.append(address.ipv4_mapped)
        if any(candidate.is_link_local or candidate in _BLOCKED_ADDRESSES or candidate.is_unspecified for candidate in candidates):
            raise ValueError("base_url must not point at a link-local or cloud metadata address")

    if parts.scheme == "http" and not _is_loopback(host):
        raise ValueError("base_url must use https://; http:// is only allowed for a loopback gateway")
    return value.rstrip("/")


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
        return _validate_target(value)


def secret_name(tenant_id: str, name: str) -> str:
    """Vault entry holding a tenant's key for its own provider."""
    return f"unimonitor-tenant-{tenant_id}-ai-{name}"


def stored(tenant: Any) -> list[dict[str, Any]]:
    """Custom providers as persisted, without their keys.

    A hand-edited ``settings_json`` (or an entry written by an older version) must
    not break the settings page, so every entry is validated and a malformed one is
    skipped with a warning rather than raising on read.
    """
    raw = tenant_settings(tenant).get(SETTINGS_KEY)
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        enabled = entry.get("enabled", True)
        try:
            provider = CustomProvider(
                name=str(entry.get("name") or ""),
                base_url=str(entry.get("base_url") or ""),
                model=str(entry.get("model") or ""),
                enabled=enabled if isinstance(enabled, bool) else True,
            )
        except (ValidationError, TypeError, ValueError) as exc:
            logger.warning(
                "custom_ai_provider_skipped",
                name=str(entry.get("name"))[:64],
                error=str(exc)[:200],
            )
            continue
        items.append(
            {
                "name": provider.name,
                "base_url": provider.base_url,
                "model": provider.model,
                "enabled": provider.enabled,
            }
        )
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
