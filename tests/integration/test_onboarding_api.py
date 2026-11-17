"""Setup API: first-run window, platform selection and the add-later path."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _isolated_vault(tmp_path, monkeypatch):
    """Keep connection secrets out of the developer's real vault."""
    monkeypatch.setenv("VAULT_DIR", str(tmp_path / "vault"))
    monkeypatch.setenv("VAULT_KEY_PATH", str(tmp_path / "vault" / "vault.key"))
    from unimonitor.secrets.resolver import reset_resolver

    reset_resolver()
    yield
    reset_resolver()


async def _bootstrap(client: AsyncClient):
    return await client.post(
        "/api/v1/onboarding/admin",
        json={"email": "ciso@example.com", "password": "correct-horse-battery"},
    )


class TestFirstRunWindow:
    async def test_status_offers_every_platform_and_needs_an_admin(self, client: AsyncClient):
        r = await client.get("/api/v1/onboarding/status")
        assert r.status_code == 200
        body = r.json()
        assert body["needs_admin"] is True
        assert body["configured"] is False
        assert {p["id"] for p in body["platforms"]} == {"microsoft", "aws", "gcp", "google_workspace"}

    async def test_admin_bootstrap_returns_a_token_and_closes_the_window(self, client: AsyncClient):
        r = await _bootstrap(client)
        assert r.status_code == 200
        assert r.json()["access_token"]
        assert r.json()["user"]["role"] == "admin"

        again = await _bootstrap(client)
        assert again.status_code == 409

        status = await client.get("/api/v1/onboarding/status")
        assert status.json()["needs_admin"] is False

    async def test_short_password_is_refused(self, client: AsyncClient):
        r = await client.post(
            "/api/v1/onboarding/admin",
            json={"email": "ciso@example.com", "password": "short"},
        )
        assert r.status_code == 422

    async def test_connections_require_the_admin_once_setup_exists(self, client: AsyncClient):
        await _bootstrap(client)
        r = await client.post("/api/v1/onboarding/connections/aws", json={"region": "us-east-1"})
        assert r.status_code == 401


class TestConnectPlatforms:
    async def test_connect_aws_validates_then_stores_the_connection(self, client: AsyncClient, monkeypatch):
        admin = await _bootstrap(client)
        headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}

        async def fake_validate(region, key_id, secret, token=None):
            assert region == "eu-west-1"
            return "123456789012"

        monkeypatch.setattr("unimonitor.onboarding.service.clouds.validate_aws", fake_validate)

        r = await client.post(
            "/api/v1/onboarding/connections/aws",
            json={"region": "eu-west-1", "access_key_id": "AKIAEXAMPLE", "secret_access_key": "shh"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["connection"]["account"] == "123456789012"

        status = (await client.get("/api/v1/onboarding/status")).json()
        assert status["configured"] is True
        assert status["connected_providers"] == ["aws"]

    async def test_a_rejected_platform_is_not_saved(self, client: AsyncClient, monkeypatch):
        admin = await _bootstrap(client)
        headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}

        async def fake_validate(*_args, **_kwargs):
            from unimonitor.onboarding.clouds import CloudError

            raise CloudError("AWS rejected those credentials: InvalidClientTokenId")

        monkeypatch.setattr("unimonitor.onboarding.service.clouds.validate_aws", fake_validate)

        r = await client.post(
            "/api/v1/onboarding/connections/aws",
            json={"region": "us-east-1", "access_key_id": "bad", "secret_access_key": "bad"},
            headers=headers,
        )
        assert r.status_code == 400
        assert "rejected" in r.json()["detail"]

        status = (await client.get("/api/v1/onboarding/status")).json()
        assert status["connections"] == []
        assert status["configured"] is False

    async def test_unknown_platform_is_rejected(self, client: AsyncClient):
        admin = await _bootstrap(client)
        headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
        r = await client.post("/api/v1/onboarding/connections/oracle", json={}, headers=headers)
        assert r.status_code == 400

    async def test_add_a_second_platform_later(self, client: AsyncClient, monkeypatch):
        admin = await _bootstrap(client)
        headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}

        async def fake_aws(region, key_id, secret, token=None):
            return "123456789012"

        async def fake_gcp(project_id, credentials_json="", access_token="", client=None):
            return "Security Project"

        monkeypatch.setattr("unimonitor.onboarding.service.clouds.validate_aws", fake_aws)
        monkeypatch.setattr("unimonitor.onboarding.service.clouds.validate_gcp", fake_gcp)

        first = await client.post(
            "/api/v1/onboarding/connections/aws",
            json={"region": "us-east-1", "access_key_id": "k", "secret_access_key": "s"},
            headers=headers,
        )
        assert first.status_code == 200

        second = await client.post(
            "/api/v1/onboarding/connections/gcp",
            json={"project_id": "proj-1"},
            headers=headers,
        )
        assert second.status_code == 200, second.text

        listed = (await client.get("/api/v1/onboarding/status")).json()
        assert sorted(listed["connected_providers"]) == ["aws", "gcp"]

    async def test_disconnecting_the_last_platform_returns_to_setup(self, client: AsyncClient, monkeypatch):
        admin = await _bootstrap(client)
        headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}

        async def fake_aws(region, key_id, secret, token=None):
            return "123456789012"

        monkeypatch.setattr("unimonitor.onboarding.service.clouds.validate_aws", fake_aws)
        await client.post(
            "/api/v1/onboarding/connections/aws",
            json={"region": "us-east-1", "access_key_id": "k", "secret_access_key": "s"},
            headers=headers,
        )

        r = await client.delete("/api/v1/onboarding/connections/aws", headers=headers)
        assert r.status_code == 200

        status = (await client.get("/api/v1/onboarding/status")).json()
        assert status["configured"] is False, "a dashboard with no platform has nothing to show"

    async def test_device_flow_is_open_only_during_the_first_run_window(self, client: AsyncClient, monkeypatch):
        async def fake_start():
            from unimonitor.onboarding.m365 import DeviceCode

            return DeviceCode("dc", "CODE-1", "https://microsoft.com/devicelogin", 900, 5, "")

        monkeypatch.setattr("unimonitor.api.v1.onboarding.m365.start_device_flow", fake_start)

        open_window = await client.post("/api/v1/onboarding/microsoft/device-code")
        assert open_window.status_code == 200
        assert open_window.json()["user_code"] == "CODE-1"

        await _bootstrap(client)
        locked = await client.post("/api/v1/onboarding/microsoft/device-code")
        assert locked.status_code == 401, "after setup only an admin may start a connection"
