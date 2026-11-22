"""One notification-preferences document, with every credential in the vault.

Two APIs edit notification settings: the flat shape the Settings page uses
(``/settings/notifications``) and the nested shape with test-delivery endpoints
(``/notifications/settings``). They used to write different places — one a tenant
JSON column, the other an attribute on ``Tenant`` that does not exist — so a save
from one was invisible to the other and the SMTP password sat in plaintext.

Both now go through this module: the non-secret fields live in
``Tenant.settings_json["notifications"]`` and every credential (the SMTP password
and the four webhook values, which are bearer credentials) lives in the configured
secret provider.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

NOTIFICATIONS_KEY = "notifications"
MASK = "******"
VAULT_KEY_TEMPLATE = "unimonitor-tenant-{tenant_id}-{suffix}"

# Model field -> vault entry suffix. Every entry written through this map.
SECRET_FIELDS: dict[str, str] = {
    # Field name in the preferences document, not a credential (S2068).
    "smtp_password": "smtp-credential",  # NOSONAR
    "teams_webhook_url": "teams-webhook",
    "slack_webhook_url": "slack-webhook",
    "generic_webhook_url": "generic-webhook-url",
    "generic_webhook_secret": "generic-webhook-secret",
}


class NotificationPreferences(BaseModel):
    """The flat notification shape, with the credentials masked by default."""

    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    smtp_use_tls: bool = True
    smtp_to_emails: list[str] = Field(default_factory=list)
    teams_webhook_url: str = ""
    slack_webhook_url: str = ""
    generic_webhook_url: str = ""
    generic_webhook_secret: str = ""
    immediate_alerts: bool = True
    daily_digest: bool = False
    weekly_digest: bool = True
    alert_severity_threshold: str = "HIGH"
    alert_thresholds: dict[str, Any] = Field(default_factory=dict)


def secret_name(tenant_id: str, field: str) -> str:
    """Vault entry for one tenant's credential (Key Vault-safe charset)."""
    return VAULT_KEY_TEMPLATE.format(tenant_id=tenant_id, suffix=SECRET_FIELDS[field])


def tenant_settings(tenant: Any) -> dict[str, Any]:
    try:
        data = json.loads(getattr(tenant, "settings_json", "") or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _stored_document(tenant: Any) -> dict[str, Any]:
    raw = tenant_settings(tenant).get(NOTIFICATIONS_KEY)
    return raw if isinstance(raw, dict) else {}


async def _read_secret(tenant: Any, field: str) -> str:
    from unimonitor.secrets import get_secret_resolver

    resolver = await get_secret_resolver()
    try:
        return await resolver.get(secret_name(tenant.id, field))
    except KeyError:
        # A credential saved into the settings row before the vault migration
        # still counts as set until the next save moves it across.
        return str(_stored_document(tenant).get(field, "") or "")


async def _write_secret(tenant_id: str, field: str, value: str) -> None:
    from unimonitor.secrets import get_secret_resolver

    resolver = await get_secret_resolver()
    name = secret_name(tenant_id, field)
    if value:
        await resolver.set(name, value, tags={"purpose": "notification"})
        return
    try:
        await resolver.delete(name)
    except KeyError:
        pass


async def load(tenant: Any, *, reveal: bool = False) -> NotificationPreferences:
    """Preferences for a tenant.

    ``reveal=False`` (the API default) masks every credential; ``reveal=True`` is
    for the delivery path, which needs the value to build the request.
    """
    if tenant is None:
        return NotificationPreferences()

    raw = {key: value for key, value in _stored_document(tenant).items() if key not in SECRET_FIELDS}
    try:
        prefs = NotificationPreferences(**raw)
    except ValidationError:
        prefs = NotificationPreferences()

    for field in SECRET_FIELDS:
        value = await _read_secret(tenant, field)
        presented = value if reveal else ""
        if not reveal and value:
            presented = MASK
        setattr(prefs, field, presented)
    return prefs


async def save(tenant: Any, prefs: NotificationPreferences) -> NotificationPreferences:
    """Persist preferences: credentials to the provider, everything else to the row.

    A credential equal to the mask keeps the stored value; an empty value deletes it.
    Returns the masked view, which is what both APIs respond with.
    """
    payload = prefs.model_dump()
    incoming = {field: payload.pop(field) for field in SECRET_FIELDS}

    for field, value in incoming.items():
        if value == MASK:
            # Keep the stored credential — and move a value that an earlier build
            # left in the settings row into the provider on the way past.
            current = await _read_secret(tenant, field)
            if current:
                await _write_secret(tenant.id, field, current)
            continue
        await _write_secret(tenant.id, field, value)

    document = tenant_settings(tenant)
    document[NOTIFICATIONS_KEY] = payload
    tenant.settings_json = json.dumps(document, sort_keys=True)
    return await load(tenant)


__all__ = [
    "MASK",
    "NOTIFICATIONS_KEY",
    "NotificationPreferences",
    "SECRET_FIELDS",
    "load",
    "save",
    "secret_name",
    "tenant_settings",
]
