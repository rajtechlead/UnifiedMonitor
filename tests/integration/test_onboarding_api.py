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
        assert {p["id"] for p in body["platforms"]} == {"microsoft", "aws", "gcp", "google_workspace", "okta"}

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

        async def fake_validate(region, _key_id, _secret, token=None):
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

        async def fake_aws(region, _key_id, _secret, token=None):
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

        async def fake_aws(region, _key_id, _secret, token=None):
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

    async def test_status_offers_the_authentication_choices(self, client: AsyncClient):
        body = (await client.get("/api/v1/onboarding/status")).json()
        catalogue = {p["id"]: p for p in body["platforms"]}
        assert [m["id"] for m in catalogue["microsoft"]["auth_methods"]] == ["certificate", "client_secret"]
        assert [m["id"] for m in catalogue["aws"]["auth_methods"]] == ["access_keys", "iam_role"]
        assert "shared_service_account" in [m["id"] for m in catalogue["gcp"]["auth_methods"]]

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

    async def test_aws_role_is_accepted_instead_of_access_keys(self, client: AsyncClient, monkeypatch):
        admin = await _bootstrap(client)
        headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}

        async def fake_role(role_arn, region="us-east-1", external_id="", session_name="unimonitor-setup"):
            assert role_arn.endswith(":role/UniMonitorReadOnly")
            return "123456789012"

        monkeypatch.setattr("unimonitor.onboarding.service.clouds.validate_aws_role", fake_role)
        r = await client.post(
            "/api/v1/onboarding/connections/aws",
            json={
                "region": "us-east-1",
                "role_arn": "arn:aws:iam::123456789012:role/UniMonitorReadOnly",
                "auth_method": "iam_role",
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["connection"]["config"]["auth_mode"] == "iam_role"

    async def test_one_service_account_connects_both_google_platforms(self, client: AsyncClient, monkeypatch):
        admin = await _bootstrap(client)
        headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
        seen: dict[str, str] = {}

        async def fake_gcp(project_id, credentials_json="", access_token="", client=None):
            seen["project"] = project_id
            seen["key"] = credentials_json
            return "Security Project"

        async def fake_workspace(admin_email, customer_id="my_customer", credentials_json="", access_token="", client=None):
            seen["admin"] = admin_email
            assert credentials_json == seen["key"], "both platforms must use the same key"
            return customer_id

        monkeypatch.setattr("unimonitor.onboarding.service.clouds.validate_gcp", fake_gcp)
        monkeypatch.setattr("unimonitor.onboarding.service.clouds.validate_workspace", fake_workspace)

        r = await client.post(
            "/api/v1/onboarding/connections/google-service-account",
            json={
                "project_id": "proj-1",
                "admin_email": "admin@example.com",
                "credentials_json": '{"client_email": "svc@proj.iam.gserviceaccount.com"}',
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        providers = sorted(c["provider"] for c in r.json()["connections"])
        assert providers == ["gcp", "google_workspace"]
        assert seen["project"] == "proj-1"
        assert seen["admin"] == "admin@example.com"

        status = (await client.get("/api/v1/onboarding/status")).json()
        assert status["connected_providers"] == ["gcp", "google_workspace"]


class TestMicrosoftCertificateFallback:
    async def test_a_refused_certificate_upload_blocks_setup_until_verified(self, client: AsyncClient, monkeypatch):
        admin = await _bootstrap(client)
        headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}

        from unimonitor.onboarding import certificates, m365

        cert = certificates.generate_client_certificate("UniMonitor", 30)

        async def fake_poll(_device_code):
            return {"status": "ok", "access_token": "graph-token"}

        async def fake_provision(_token, **_kwargs):
            return m365.ProvisionResult(
                tenant_id="tenant-1",
                tenant_name="Contoso",
                client_id="app-1",
                auth_method="certificate",
                certificate=cert,
                certificate_uploaded=False,
                certificate_error="Graph POST /applications/obj-1/addKey failed: 403",
                manual_steps=list(m365.MANUAL_CERTIFICATE_STEPS),
            )

        monkeypatch.setattr("unimonitor.api.v1.onboarding.m365.poll_device_flow", fake_poll)
        monkeypatch.setattr("unimonitor.api.v1.onboarding.m365.provision_app", fake_provision)

        r = await client.post("/api/v1/onboarding/microsoft/complete", json={"device_code": "dc"}, headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "pending_certificate_upload"
        assert body["certificate"]["files"], "the admin must be able to save the certificate"
        assert body["manual_steps"]
        assert body["auth_method"] == "certificate"

        status = (await client.get("/api/v1/onboarding/status")).json()
        assert status["configured"] is False, "an unverified upload is not a usable connection"
        assert status["connected_providers"] == []

        async def fake_verify(*_args, **_kwargs):
            return "Contoso"

        monkeypatch.setattr("unimonitor.onboarding.m365.verify_client_credentials", fake_verify)
        verified = await client.post("/api/v1/onboarding/microsoft/verify", headers=headers)
        assert verified.status_code == 200, verified.text
        assert verified.json()["connection"]["status"] == "connected"

        status = (await client.get("/api/v1/onboarding/status")).json()
        assert status["configured"] is True
        assert status["connected_providers"] == ["microsoft"]


class TestCertificateRotation:
    """Settings → Platform connections: surfacing and rotating the Entra certificate."""

    async def _connect_with_certificate(self, client: AsyncClient, headers: dict, monkeypatch):
        from unimonitor.onboarding import certificates

        async def fake_verify(*_args, **_kwargs):
            return "Contoso"

        monkeypatch.setattr("unimonitor.onboarding.service.m365.verify_client_credentials", fake_verify)
        certificate = certificates.generate_client_certificate("UniMonitor", 30)
        r = await client.post(
            "/api/v1/onboarding/connections/microsoft",
            json={
                "tenant": "tenant-1",
                "client_id": "app-1",
                "auth_method": "certificate",
                "certificate_pem": certificate.certificate_pem,
                "private_key_pem": certificate.private_key_pem,
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        return certificate

    async def test_connection_reports_thumbprint_and_expiry(self, client: AsyncClient, monkeypatch):
        admin = await _bootstrap(client)
        headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
        certificate = await self._connect_with_certificate(client, headers, monkeypatch)

        status = (await client.get("/api/v1/onboarding/status")).json()
        config = status["connections"][0]["config"]
        assert config["certificate_thumbprint"] == certificate.thumbprint
        assert config["certificate_expires_at"], "the UI needs an expiry to warn on"

    async def test_rotation_adds_a_new_key_and_retires_the_old_one(self, client: AsyncClient, monkeypatch):
        from unimonitor.onboarding import certificates

        admin = await _bootstrap(client)
        headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
        old = await self._connect_with_certificate(client, headers, monkeypatch)

        calls: list[tuple] = []

        async def fake_token(*_args, **_kwargs):
            return "graph-token"

        async def fake_app_id(*_args, **_kwargs):
            return "obj-1"

        async def fake_add(_token, object_id, certificate):
            calls.append(("add", object_id, certificate.thumbprint))

        async def fake_remove(_token, object_id, certificate_pem):
            calls.append(("remove", object_id, certificates.thumbprint(certificate_pem)))
            return True

        monkeypatch.setattr("unimonitor.onboarding.service.m365.client_credentials_token", fake_token)
        monkeypatch.setattr("unimonitor.onboarding.service.m365.find_app_object_id", fake_app_id)
        monkeypatch.setattr("unimonitor.onboarding.service.m365.add_certificate", fake_add)
        monkeypatch.setattr("unimonitor.onboarding.service.m365.remove_certificate", fake_remove)

        r = await client.post(
            "/api/v1/onboarding/microsoft/certificate/rotate",
            json={"validity_days": 90},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        new_thumbprint = r.json()["connection"]["config"]["certificate_thumbprint"]
        assert new_thumbprint
        assert new_thumbprint != old.thumbprint
        assert r.json()["connection"]["config"]["certificate_expires_at"]

        assert ("add", "obj-1", new_thumbprint) in calls
        assert ("remove", "obj-1", old.thumbprint) in calls, "the old key must stop working"

    async def test_rotation_explains_a_registration_that_may_not_manage_itself(self, client: AsyncClient, monkeypatch):
        """A hand-made app has neither the permission nor the ownership: say so."""
        from unimonitor.onboarding.m365 import M365Error

        admin = await _bootstrap(client)
        headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
        await self._connect_with_certificate(client, headers, monkeypatch)

        async def fake_token(*_args, **_kwargs):
            return "graph-token"

        async def fake_app_id(*_args, **_kwargs):
            return "obj-1"

        async def forbidden(*_args, **_kwargs):
            raise M365Error('Graph POST /applications/obj-1/addKey failed: 403 {"error":{"code":"Forbidden"}}')

        monkeypatch.setattr("unimonitor.onboarding.service.m365.client_credentials_token", fake_token)
        monkeypatch.setattr("unimonitor.onboarding.service.m365.find_app_object_id", fake_app_id)
        monkeypatch.setattr("unimonitor.onboarding.service.m365.add_certificate", forbidden)

        r = await client.post("/api/v1/onboarding/microsoft/certificate/rotate", json={}, headers=headers)
        assert r.status_code == 400
        assert "Application.ReadWrite.OwnedBy" in r.json()["detail"]

    async def test_rotation_is_refused_for_a_client_secret_connection(self, client: AsyncClient, monkeypatch):
        async def fake_verify(*_args, **_kwargs):
            return "Contoso"

        admin = await _bootstrap(client)
        headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
        monkeypatch.setattr("unimonitor.onboarding.service.m365.verify_client_credentials", fake_verify)
        connected = await client.post(
            "/api/v1/onboarding/connections/microsoft",
            json={"tenant": "tenant-1", "client_id": "app-1", "auth_method": "client_secret", "client_secret": "s3cret"},
            headers=headers,
        )
        assert connected.status_code == 200, connected.text

        r = await client.post("/api/v1/onboarding/microsoft/certificate/rotate", json={}, headers=headers)
        assert r.status_code == 400
        assert "client secret" in r.json()["detail"]
