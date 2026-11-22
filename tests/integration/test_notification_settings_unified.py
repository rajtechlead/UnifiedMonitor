"""One notification document for both APIs, and every credential in the vault.

The Settings page uses the flat shape (``/settings/notifications``); the delivery
endpoints use the nested shape (``/notifications/settings``). They used to write
different places, so a webhook saved in one was invisible to the other and the
credentials sat in the tenant row. These tests pin the merged behaviour.
"""

import json

import pytest
from httpx import AsyncClient

from unimonitor.notifications.preferences import secret_name
from unimonitor.secrets.local_vault import LocalVaultProvider
from unimonitor.secrets.resolver import SecretResolver

pytestmark = pytest.mark.asyncio

NESTED = "/api/v1/notifications/settings"
FLAT = "/api/v1/settings/notifications"
MASK = "******"
SECRETS = {
    "smtp_password": "smtp-password-value",
    "teams_webhook_url": "https://contoso.webhook.office.com/webhookb2/teams-token",
    "slack_webhook_url": "https://hooks.slack.com/services/T00/B00/slack-token",
    "generic_webhook_url": "https://siem.contoso.com/ingest/unimonitor",
    "generic_webhook_secret": "generic-shared-secret",
}


@pytest.fixture
def vault(tmp_path, monkeypatch):
    provider = LocalVaultProvider(vault_dir=tmp_path / "vault")

    async def _resolver():
        return SecretResolver(primary_provider=provider)

    monkeypatch.setattr("unimonitor.secrets.get_secret_resolver", _resolver)
    return provider


def _nested_payload() -> dict:
    return {
        "smtp": {
            "host": "smtp.office365.com",
            "port": 587,
            "username": "alerts@contoso.com",
            "password": SECRETS["smtp_password"],
            "from_address": "alerts@contoso.com",
            "use_tls": True,
            "enabled": True,
        },
        "teams": {"webhook_url": SECRETS["teams_webhook_url"], "enabled": True},
        "slack": {"webhook_url": SECRETS["slack_webhook_url"], "enabled": True},
        "generic_webhook": {
            "url": SECRETS["generic_webhook_url"],
            "secret": SECRETS["generic_webhook_secret"],
            "enabled": True,
        },
        "thresholds": {
            "new_critical_finding": True,
            "new_high_finding": True,
            "score_drop_threshold": 5.0,
            "collection_failure": True,
        },
        "daily_digest_enabled": True,
        "weekly_digest_enabled": False,
    }


async def _secrets_in_vault(provider, tenant_id: str) -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for field in SECRETS:
        try:
            found[field] = await provider.get_secret(secret_name(tenant_id, field))
        except KeyError:
            found[field] = None
    return found


class TestUnifiedNotificationSettings:
    async def test_every_credential_from_the_nested_api_lands_in_the_vault(self, client: AsyncClient, auth_headers: dict, db_session, tenant, vault):
        r = await client.put(NESTED, params={"tenant_id": tenant.id}, json=_nested_payload(), headers=auth_headers)
        assert r.status_code == 200, r.text

        assert await _secrets_in_vault(vault, tenant.id) == SECRETS

        await db_session.refresh(tenant)
        row = json.loads(tenant.settings_json)["notifications"]
        for value in SECRETS.values():
            assert value not in tenant.settings_json
        assert row["smtp_host"] == "smtp.office365.com"
        assert row["daily_digest"] is True
        assert row["weekly_digest"] is False
        assert row["alert_thresholds"]["score_drop_threshold"] == 5.0

    async def test_nested_read_masks_every_credential(self, client: AsyncClient, auth_headers: dict, tenant, vault):
        await client.put(NESTED, params={"tenant_id": tenant.id}, json=_nested_payload(), headers=auth_headers)

        r = await client.get(NESTED, params={"tenant_id": tenant.id}, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["smtp"]["password"] == MASK
        assert body["teams"]["webhook_url"] == MASK
        assert body["slack"]["webhook_url"] == MASK
        assert body["generic_webhook"]["url"] == MASK
        assert body["generic_webhook"]["secret"] == MASK
        assert body["smtp"]["host"] == "smtp.office365.com"

    async def test_a_save_through_either_api_is_visible_to_the_other(self, client: AsyncClient, auth_headers: dict, tenant, vault):
        await client.put(NESTED, params={"tenant_id": tenant.id}, json=_nested_payload(), headers=auth_headers)

        flat = await client.get(FLAT, headers=auth_headers)
        assert flat.status_code == 200
        assert flat.json()["smtp_host"] == "smtp.office365.com"
        assert flat.json()["slack_webhook_url"] == MASK
        assert flat.json()["daily_digest"] is True

        r = await client.put(
            FLAT,
            json={"smtp_host": "smtp.contoso.com", "smtp_username": "alerts@contoso.com", "smtp_password": MASK},
            headers=auth_headers,
        )
        assert r.status_code == 200

        nested = await client.get(NESTED, params={"tenant_id": tenant.id}, headers=auth_headers)
        assert nested.json()["smtp"]["host"] == "smtp.contoso.com"
        assert nested.json()["smtp"]["password"] == MASK

        # A host-only save must not wipe the other channels or the credentials.
        assert await _secrets_in_vault(vault, tenant.id) == SECRETS

    async def test_a_partial_nested_update_leaves_other_channels_alone(self, client: AsyncClient, auth_headers: dict, tenant, vault):
        await client.put(NESTED, params={"tenant_id": tenant.id}, json=_nested_payload(), headers=auth_headers)

        r = await client.put(
            NESTED,
            params={"tenant_id": tenant.id},
            json={"slack": {"webhook_url": "https://hooks.slack.com/services/T00/B00/replaced"}},
            headers=auth_headers,
        )
        assert r.status_code == 200

        assert (await vault.get_secret(secret_name(tenant.id, "slack_webhook_url"))) == "https://hooks.slack.com/services/T00/B00/replaced"
        assert (await vault.get_secret(secret_name(tenant.id, "smtp_password"))) == SECRETS["smtp_password"]
        assert (await vault.get_secret(secret_name(tenant.id, "teams_webhook_url"))) == SECRETS["teams_webhook_url"]


class TestTestDeliveryUsesTheVault:
    async def test_slack_test_posts_to_the_stored_webhook(self, client: AsyncClient, auth_headers: dict, tenant, vault, monkeypatch):
        await client.put(NESTED, params={"tenant_id": tenant.id}, json=_nested_payload(), headers=auth_headers)

        calls: list[tuple[str, dict]] = []

        class _Response:
            is_success = True

        class _Client:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def post(self, url, json=None, headers=None):
                calls.append((url, json or {}))
                return _Response()

        monkeypatch.setattr("httpx.AsyncClient", _Client)

        r = await client.post(
            "/api/v1/notifications/test",
            params={"tenant_id": tenant.id},
            json={"channel": "slack"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True
        assert calls and calls[0][0] == SECRETS["slack_webhook_url"]

    async def test_a_channel_with_no_stored_credential_reports_it(self, client: AsyncClient, auth_headers: dict, tenant, vault):
        r = await client.post(
            "/api/v1/notifications/test",
            params={"tenant_id": tenant.id},
            json={"channel": "teams"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["success"] is False
        assert "not configured" in r.json()["message"]
