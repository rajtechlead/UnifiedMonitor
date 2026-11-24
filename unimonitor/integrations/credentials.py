"""Per-connector credentials, stored in the secret vault rather than the environment.

SIEM and ticketing connectors used to be configurable only through deployment
environment variables, so an administrator could not connect one from the product.
Each connector's settings are now written to the secret provider under one reference
(``unimonitor-connector-<kind>-<provider>``) as a JSON document; the API never returns
the values, only whether the connector is ready.

Environment variables remain a fallback so existing deployments keep working, and a
vault entry always wins over the environment for the fields it contains.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from unimonitor.core.logging import get_logger
from unimonitor.integrations.siem import CONNECTORS
from unimonitor.integrations.ticketing import PROVIDERS

logger = get_logger(__name__)

MAX_VALUE_LENGTH = 4096

_DEFINITIONS: dict[str, dict[str, Any]] = {"siem": CONNECTORS, "ticketing": PROVIDERS}
_URL_FIELDS = ("URL", "ENDPOINT")
_HOST_FIELDS = ("HOST",)


class ConnectorConfigError(ValueError):
    """The connector or one of its values is not acceptable."""


def fields_for(kind: str, provider: str) -> tuple[str, ...]:
    """The settings a connector needs, in its declared order."""
    definitions = _DEFINITIONS.get(kind)
    if definitions is None:
        raise ConnectorConfigError(f"Unknown connector kind '{kind}'")
    definition = definitions.get(provider)
    if definition is None:
        raise ConnectorConfigError(f"Unknown {kind} connector '{provider}'")
    return tuple(definition.env)


def secret_name(kind: str, provider: str) -> str:
    """Vault reference for one connector's settings document."""
    return f"unimonitor-connector-{kind}-{provider}"


def _check_value(name: str, value: str) -> None:
    """Reject a value the connector's request builder must never receive."""
    if len(value) > MAX_VALUE_LENGTH:
        raise ConnectorConfigError(f"{name} is longer than {MAX_VALUE_LENGTH} characters")
    if name.endswith(_URL_FIELDS):
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ConnectorConfigError(f"{name} must be an http(s) URL")
        # The same public-target rule as a custom AI endpoint: no loopback,
        # private-range or cloud-metadata host, which would turn a webhook into
        # an authenticated request against the host's own network.
        from unimonitor.ai.custom import validate_base_url

        # shortcut: hostnames are checked syntactically; a public name that resolves
        # to a private address (DNS rebinding) needs a connect-time address check.
        try:
            validate_base_url(value)
        except ValueError as exc:
            raise ConnectorConfigError(f"{name}: {exc}") from exc
    elif name.endswith(_HOST_FIELDS) and ("://" in value or "/" in value or " " in value):
        raise ConnectorConfigError(f"{name} must be a bare hostname or IP address")


def _clean(kind: str, provider: str, values: dict[str, Any]) -> dict[str, str]:
    allowed = fields_for(kind, provider)
    cleaned: dict[str, str] = {}
    for name in allowed:
        if name not in values:
            continue
        raw = values[name]
        if not isinstance(raw, str):
            raise ConnectorConfigError(f"{name} must be a string")
        value = raw.strip()
        if not value:
            continue
        _check_value(name, value)
        cleaned[name] = value
    return cleaned


async def save(kind: str, provider: str, values: dict[str, Any]) -> list[str]:
    """Merge *values* into a connector's vault entry; returns the stored field names.

    The document is merged rather than replaced so a rotation can update one token
    without re-entering the URL. Values are never logged.
    """
    from unimonitor.secrets import get_secret_resolver

    cleaned = _clean(kind, provider, values)
    if not cleaned:
        raise ConnectorConfigError("No settings were supplied")
    current = await load(kind, provider) or {}
    current.update(cleaned)
    resolver = await get_secret_resolver()
    await resolver.set(secret_name(kind, provider), json.dumps(current, sort_keys=True), tags={"purpose": f"{kind}-connector"})
    logger.info("connector_config_saved", kind=kind, provider=provider, fields=sorted(cleaned))
    return sorted(cleaned)


async def load(kind: str, provider: str) -> dict[str, str] | None:
    """The connector's stored settings, or None when nothing is stored in the vault."""
    from unimonitor.secrets import get_secret_resolver

    fields_for(kind, provider)
    try:
        raw = await (await get_secret_resolver()).get(secret_name(kind, provider))
    except KeyError:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        logger.warning("connector_config_unreadable", kind=kind, provider=provider)
        return None
    if not isinstance(data, dict):
        return None
    # A hand-edited entry must not smuggle an unknown setting into a request builder.
    allowed = set(fields_for(kind, provider))
    return {str(key): str(value) for key, value in data.items() if key in allowed}


async def load_all(kind: str) -> dict[str, dict[str, str]]:
    """Every vault-managed connector of one kind, keyed by provider slug."""
    definitions = _DEFINITIONS.get(kind)
    if definitions is None:
        raise ConnectorConfigError(f"Unknown connector kind '{kind}'")
    configs: dict[str, dict[str, str]] = {}
    for provider in definitions:
        stored = await load(kind, provider)
        if stored:
            configs[provider] = stored
    return configs


async def delete(kind: str, provider: str) -> None:
    """Remove a connector's vault entry; environment fallback applies again."""
    from unimonitor.secrets import get_secret_resolver

    fields_for(kind, provider)
    resolver = await get_secret_resolver()
    try:
        await resolver.delete(secret_name(kind, provider))
    except KeyError:
        return
    logger.info("connector_config_deleted", kind=kind, provider=provider)


__all__ = [
    "ConnectorConfigError",
    "delete",
    "fields_for",
    "load",
    "load_all",
    "save",
    "secret_name",
]
