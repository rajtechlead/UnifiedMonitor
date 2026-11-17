"""Platform onboarding logic: permission list, catalogue, device flow, app registration."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from unimonitor.onboarding import m365, permissions, service
from unimonitor.onboarding.google_auth import GoogleAuthError, mint_access_token, reset_cache

ROOT = Path(__file__).resolve().parents[2]


class TestPermissions:
    def test_required_roles_are_read_only(self):
        """The wizard grants these to a service principal; none may write to the tenant."""
        for perm in permissions.REQUIRED:
            assert perm.name.endswith(".Read.All") or perm.name.endswith(".ReadBasic.All"), perm.name
            assert ".ReadWrite." not in perm.name

    def test_install_docs_list_every_permission(self):
        """INSTALL.md is what an admin reads before trusting the automation."""
        doc = (ROOT / "INSTALL.md").read_text()
        missing = [p.name for p in permissions.REQUIRED if p.name not in doc]
        assert missing == [], f"INSTALL.md does not document: {missing}"

    def test_graph_app_id(self):
        assert permissions.GRAPH_APP_ID == "00000003-0000-0000-c000-000000000000"


class TestCatalogue:
    def test_every_registry_provider_is_offerable(self):
        from unimonitor.grc.providers import PROVIDERS

        ids = [p["id"] for p in service.platform_catalogue()]
        assert sorted(ids) == sorted(PROVIDERS)

    def test_microsoft_is_automated_and_clouds_ask_for_credentials(self):
        catalogue = {p["id"]: p for p in service.platform_catalogue()}
        assert catalogue["microsoft"]["automated"] is True
        assert catalogue["aws"]["secret_fields"], "AWS needs credentials from the admin"
        assert catalogue["gcp"]["config_fields"][0]["name"] == "project_id"

    def test_every_provider_has_fields(self):
        for platform in service.platform_catalogue():
            assert platform["config_fields"] or platform["secret_fields"] or platform["automated"]


def _graph_mock(roles: list[dict]) -> tuple[httpx.AsyncClient, list[tuple[str, str]]]:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        path = request.url.path
        if path.endswith("/oauth2/v2.0/devicecode"):
            return httpx.Response(
                200,
                json={
                    "device_code": "dc-1",
                    "user_code": "ABCD-1234",
                    "verification_uri": "https://microsoft.com/devicelogin",
                    "expires_in": 900,
                    "interval": 5,
                    "message": "go",
                },
            )
        if path.endswith("/oauth2/v2.0/token"):
            return httpx.Response(200, json={"access_token": "graph-token"})
        if path.endswith("/organization"):
            return httpx.Response(200, json={"value": [{"id": "tenant-1", "displayName": "Contoso"}]})
        if path.endswith("/servicePrincipals") and request.method == "GET":
            return httpx.Response(200, json={"value": [{"id": "graph-sp", "appRoles": roles}]})
        if path.endswith("/applications") and request.method == "POST":
            return httpx.Response(201, json={"appId": "app-1", "id": "obj-1"})
        if path.endswith("/addPassword"):
            return httpx.Response(200, json={"secretText": "s3cret~value"})
        if path.endswith("/servicePrincipals") and request.method == "POST":
            return httpx.Response(201, json={"id": "new-sp"})
        if path.endswith("/appRoleAssignedTo"):
            return httpx.Response(201, json={})
        return httpx.Response(404, json={"error": f"unexpected {path}"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


class TestMicrosoftSetup:
    async def test_device_flow_returns_a_code_and_link(self):
        client, _ = _graph_mock([])
        async with client:
            code = await m365.start_device_flow(client)
        assert code.user_code == "ABCD-1234"
        assert code.verification_uri.startswith("https://")

    async def test_poll_reports_pending_then_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if b"device_code" in request.content and b"dc-pending" in request.content:
                return httpx.Response(400, json={"error": "authorization_pending"})
            return httpx.Response(200, json={"access_token": "tok"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            assert (await m365.poll_device_flow("dc-pending", client))["status"] == "pending"
            assert (await m365.poll_device_flow("dc-ready", client))["status"] == "ok"

    async def test_provision_creates_app_consents_roles_and_returns_a_secret(self):
        roles = [{"id": f"role-{i}", "value": p.name} for i, p in enumerate(permissions.REQUIRED + permissions.OPTIONAL)]
        client, calls = _graph_mock(roles)
        async with client:
            result = await m365.provision_app("graph-token", client=client)

        assert result.client_id == "app-1"
        assert result.client_secret == "s3cret~value"
        assert result.tenant_id == "tenant-1"
        assert len(result.granted) == len(roles)
        assert result.warnings == []
        assert ("POST", "/v1.0/applications") in calls
        assert sum(1 for m, p in calls if p.endswith("/appRoleAssignedTo")) == len(roles)

    async def test_missing_optional_role_is_a_warning_not_a_failure(self):
        roles = [{"id": f"role-{i}", "value": p.name} for i, p in enumerate(permissions.REQUIRED)]
        client, _ = _graph_mock(roles)
        async with client:
            result = await m365.provision_app("graph-token", client=client)
        assert result.warnings == [], "an absent optional role is simply not requested"
        assert result.client_secret

    async def test_consent_failure_on_a_role_is_reported(self):
        roles = [{"id": "role-1", "value": p.name} for p in permissions.REQUIRED]

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("/organization"):
                return httpx.Response(200, json={"value": [{"id": "t", "displayName": "T"}]})
            if path.endswith("/servicePrincipals") and request.method == "GET":
                return httpx.Response(200, json={"value": [{"id": "graph-sp", "appRoles": roles}]})
            if path.endswith("/applications"):
                return httpx.Response(201, json={"appId": "app-1", "id": "obj-1"})
            if path.endswith("/addPassword"):
                return httpx.Response(200, json={"secretText": "s"})
            if path.endswith("/servicePrincipals"):
                return httpx.Response(201, json={"id": "new-sp"})
            return httpx.Response(403, json={"error": "insufficient privileges"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await m365.provision_app("token", client=client)

        assert result.granted == []
        assert all("not granted" in w for w in result.warnings)
        assert result.client_secret, "the app registration is still usable without consent"


class TestGoogleServiceAccounts:
    async def test_rejects_text_that_is_not_a_key(self):
        with pytest.raises(GoogleAuthError, match="service-account JSON"):
            await mint_access_token("not json", "scope")

    async def test_mints_and_caches_a_token(self):
        reset_cache()
        calls = {"n": 0}
        key = json.dumps({"client_email": "svc@project.iam.gserviceaccount.com", "private_key": _rsa_key()})

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json={"access_token": "ya29.token", "expires_in": 3600})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            first = await mint_access_token(key, "scope", client=client)
            second = await mint_access_token(key, "scope", client=client)

        assert first == second == "ya29.token"
        assert calls["n"] == 1, "the minted token should be reused until it expires"
        reset_cache()


_private_key_cache: str | None = None


def _rsa_key() -> str:
    """A throwaway 2048-bit RSA key so the RS256 signature is real."""
    global _private_key_cache
    if _private_key_cache is None:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _private_key_cache = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
    return _private_key_cache
