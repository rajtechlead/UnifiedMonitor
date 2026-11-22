"""Notification preferences: the flat shape the Settings page edits.

The SMTP password is the only secret in this payload. It must be stored, never
returned, and survive the client echoing the mask back on the next save.
"""

import json

import pytest
from httpx import AsyncClient

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


class TestNotificationPreferences:
    async def test_smtp_password_is_stored_and_masked(self, client: AsyncClient, auth_headers: dict):
        r = await client.put(URL, json=_payload("correct-horse-battery"), headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["smtp_password"] == MASK

        r = await client.get(URL, headers=auth_headers)
        body = r.json()
        assert r.status_code == 200
        assert body["smtp_password"] == MASK
        assert body["smtp_host"] == "smtp.office365.com"
        assert body["smtp_to_emails"] == ["soc@contoso.com"]

    async def test_echoing_the_mask_keeps_the_stored_password(self, client: AsyncClient, auth_headers: dict, db_session, tenant):
        await client.put(URL, json=_payload("correct-horse-battery"), headers=auth_headers)

        r = await client.put(URL, json=_payload(MASK), headers=auth_headers)
        assert r.status_code == 200

        await db_session.refresh(tenant)
        stored = json.loads(tenant.settings_json)["notifications"]
        assert stored["smtp_password"] == "correct-horse-battery"

    async def test_a_new_password_replaces_the_old_one(self, client: AsyncClient, auth_headers: dict):
        await client.put(URL, json=_payload("first-password-value"), headers=auth_headers)
        r = await client.put(URL, json=_payload("second-password-value"), headers=auth_headers)
        assert r.status_code == 200

        r = await client.get(URL, headers=auth_headers)
        assert r.json()["smtp_password"] == MASK

    async def test_requires_auth(self, client: AsyncClient):
        r = await client.get(URL)
        assert r.status_code == 401

    async def test_rejects_a_port_outside_the_valid_range(self, client: AsyncClient, auth_headers: dict):
        body = _payload("")
        body["smtp_port"] = 70000
        r = await client.put(URL, json=body, headers=auth_headers)
        assert r.status_code == 422
