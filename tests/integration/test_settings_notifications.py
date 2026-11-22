"""Notification preferences: the flat shape the Settings page edits.

The SMTP password is the only secret in this payload. It lives in the secret
provider (an encrypted local vault here), never in the tenant settings row, and
the API only ever returns a mask. The mask is honoured on the next save.
"""

import json

import pytest
from httpx import AsyncClient

from unimonitor.secrets.local_vault import LocalVaultProvider
from unimonitor.secrets.resolver import SecretResolver

pytestmark = pytest.mark.asyncio

URL = "/api/v1/settings/notifications"
MASK = "******"


def _payload(password: str) -> dict:
    return {
        "smtp_enabled": True,
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "smtp_username": "alerts@contoso.com",
        "smtp_password": password,
        "smtp_to_emails": ["soc@contoso.com"],
        "alert_severity_threshold": "HIGH",
    }


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """Point the API at a throwaway encrypted vault instead of the real one."""
    provider = LocalVaultProvider(vault_dir=tmp_path / "vault")

    async def _resolver():
        return SecretResolver(primary_provider=provider)

    monkeypatch.setattr("unimonitor.secrets.get_secret_resolver", _resolver)
    return provider


async def _stored(provider, tenant_id: str) -> str:
    from unimonitor.api.v1.settings import _smtp_secret_name

    return await provider.get_secret(_smtp_secret_name(tenant_id))


class TestNotificationPreferences:
    async def test_smtp_password_is_stored_in_the_vault_and_masked(self, client: AsyncClient, auth_headers: dict, db_session, tenant, vault):
        r = await client.put(URL, json=_payload("correct-horse-battery"), headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["smtp_password"] == MASK

        r = await client.get(URL, headers=auth_headers)
        body = r.json()
        assert r.status_code == 200
        assert body["smtp_password"] == MASK
        assert body["smtp_host"] == "smtp.office365.com"
        assert body["smtp_to_emails"] == ["soc@contoso.com"]

        assert await _stored(vault, tenant.id) == "correct-horse-battery"

        # The settings row must not carry the secret in any form.
        await db_session.refresh(tenant)
        stored_row = json.loads(tenant.settings_json)["notifications"]
        assert "smtp_password" not in stored_row
        assert "correct-horse-battery" not in tenant.settings_json

    async def test_echoing_the_mask_keeps_the_stored_password(self, client: AsyncClient, auth_headers: dict, tenant, vault):
        await client.put(URL, json=_payload("correct-horse-battery"), headers=auth_headers)

        r = await client.put(URL, json=_payload(MASK), headers=auth_headers)
        assert r.status_code == 200
        assert await _stored(vault, tenant.id) == "correct-horse-battery"

    async def test_a_new_password_replaces_the_old_one(self, client: AsyncClient, auth_headers: dict, tenant, vault):
        await client.put(URL, json=_payload("first-password-value"), headers=auth_headers)
        r = await client.put(URL, json=_payload("second-password-value"), headers=auth_headers)
        assert r.status_code == 200

        assert await _stored(vault, tenant.id) == "second-password-value"
        r = await client.get(URL, headers=auth_headers)
        assert r.json()["smtp_password"] == MASK

    async def test_an_empty_password_clears_the_stored_one(self, client: AsyncClient, auth_headers: dict, tenant, vault):
        await client.put(URL, json=_payload("correct-horse-battery"), headers=auth_headers)
        r = await client.put(URL, json=_payload(""), headers=auth_headers)
        assert r.status_code == 200

        with pytest.raises(KeyError):
            await _stored(vault, tenant.id)
        r = await client.get(URL, headers=auth_headers)
        assert r.json()["smtp_password"] == ""

    async def test_a_legacy_settings_password_is_migrated_on_save(self, client: AsyncClient, auth_headers: dict, db_session, tenant, vault):
        """A password written into the settings row by the earlier build moves out."""
        tenant.settings_json = json.dumps({"notifications": {"smtp_password": "legacy-password"}})
        await db_session.flush()

        r = await client.get(URL, headers=auth_headers)
        assert r.json()["smtp_password"] == MASK

        r = await client.put(URL, json=_payload(MASK), headers=auth_headers)
        assert r.status_code == 200

        assert await _stored(vault, tenant.id) == "legacy-password"
        await db_session.refresh(tenant)
        assert "smtp_password" not in json.loads(tenant.settings_json)["notifications"]

    async def test_requires_auth(self, client: AsyncClient):
        r = await client.get(URL)
        assert r.status_code == 401

    async def test_rejects_a_port_outside_the_valid_range(self, client: AsyncClient, auth_headers: dict, vault):
        body = _payload("")
        body["smtp_port"] = 70000
        r = await client.put(URL, json=body, headers=auth_headers)
        assert r.status_code == 422
