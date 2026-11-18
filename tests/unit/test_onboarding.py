"""Platform onboarding logic: permission list, catalogue, device flow, app registration."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from unimonitor.onboarding import certificates, m365, permissions, service
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
        if path.endswith("/addKey"):
            return httpx.Response(200, json={"keyId": "key-1"})
        if path.endswith("/owners/$ref"):
            return httpx.Response(204)
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

    async def test_provision_creates_app_consents_roles_and_uploads_a_certificate(self):
        roles = [{"id": f"role-{i}", "value": p.name} for i, p in enumerate(permissions.REQUIRED + permissions.OPTIONAL)]
        client, calls = _graph_mock(roles)
        async with client:
            result = await m365.provision_app("graph-token", client=client)

        assert result.client_id == "app-1"
        assert result.tenant_id == "tenant-1"
        assert result.auth_method == "certificate", "certificate is the default credential"
        assert result.certificate is not None
        assert "BEGIN CERTIFICATE" in result.certificate.certificate_pem
        assert result.certificate_uploaded is True
        assert result.certificate_error == ""
        assert result.manual_steps == []
        assert result.client_secret == "", "no secret is minted when a certificate is used"
        assert len(result.granted) == len(roles)
        assert result.warnings == []
        assert ("POST", "/v1.0/applications") in calls
        assert ("POST", "/v1.0/applications/obj-1/addKey") in calls
        assert not any(path.endswith("/addPassword") for _, path in calls)
        assert sum(1 for m, p in calls if p.endswith("/appRoleAssignedTo")) == len(roles)

    async def test_the_app_is_made_an_owner_so_it_can_rotate_its_own_certificate(self):
        """Rotation needs Application.ReadWrite.OwnedBy *and* ownership of itself."""
        roles = [{"id": f"role-{i}", "value": p.name} for i, p in enumerate(permissions.REQUIRED + permissions.SELF_MANAGEMENT)]
        client, calls = _graph_mock(roles)
        async with client:
            result = await m365.provision_app("graph-token", client=client)

        assert "Application.ReadWrite.OwnedBy" in result.granted
        assert ("POST", "/v1.0/applications/obj-1/owners/$ref") in calls
        assert result.warnings == []

    async def test_ownership_is_skipped_when_the_tenant_refuses_the_role(self):
        roles = [{"id": f"role-{i}", "value": p.name} for i, p in enumerate(permissions.REQUIRED)]
        client, calls = _graph_mock(roles)
        async with client:
            result = await m365.provision_app("graph-token", client=client)

        assert not any(path.endswith("owners/$ref") for _, path in calls)
        assert result.warnings == []

    async def test_a_client_secret_can_be_chosen_instead(self):
        roles = [{"id": f"role-{i}", "value": p.name} for i, p in enumerate(permissions.REQUIRED)]
        client, calls = _graph_mock(roles)
        async with client:
            result = await m365.provision_app("graph-token", auth_method="client_secret", client=client)

        assert result.auth_method == "client_secret"
        assert result.client_secret == "s3cret~value"
        assert result.certificate is None
        assert not any(path.endswith("/addKey") for _, path in calls)

    async def test_refused_certificate_upload_falls_back_to_the_portal(self):
        """The app and consent exist; only the file upload is left for the admin."""
        roles = [{"id": f"role-{i}", "value": p.name} for i, p in enumerate(permissions.REQUIRED)]

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("/organization"):
                return httpx.Response(200, json={"value": [{"id": "t", "displayName": "T"}]})
            if path.endswith("/servicePrincipals") and request.method == "GET":
                return httpx.Response(200, json={"value": [{"id": "graph-sp", "appRoles": roles}]})
            if path.endswith("/applications"):
                return httpx.Response(201, json={"appId": "app-1", "id": "obj-1"})
            if path.endswith("/servicePrincipals"):
                return httpx.Response(201, json={"id": "new-sp"})
            if path.endswith("/addKey"):
                return httpx.Response(403, json={"error": {"message": "Insufficient privileges"}})
            return httpx.Response(201, json={})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await m365.provision_app("token", client=client)

        assert result.certificate_uploaded is False
        assert result.certificate is not None, "the admin still needs the certificate to upload"
        assert result.certificate_error.startswith("Graph POST")
        assert result.manual_steps == list(m365.MANUAL_CERTIFICATE_STEPS)
        assert any("Certificate upload failed" in w for w in result.warnings)
        assert len(result.granted) == len(roles), "consent is unaffected by the upload failure"

    async def test_missing_optional_role_is_a_warning_not_a_failure(self):
        roles = [{"id": f"role-{i}", "value": p.name} for i, p in enumerate(permissions.REQUIRED)]
        client, _ = _graph_mock(roles)
        async with client:
            result = await m365.provision_app("graph-token", client=client)
        assert result.warnings == [], "an absent optional role is simply not requested"
        assert result.certificate_uploaded is True

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
            if path.endswith("/addKey"):
                return httpx.Response(200, json={})
            if path.endswith("/servicePrincipals"):
                return httpx.Response(201, json={"id": "new-sp"})
            return httpx.Response(403, json={"error": "insufficient privileges"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await m365.provision_app("token", auth_method="client_secret", client=client)

        assert result.granted == []
        assert all("not granted" in w for w in result.warnings)
        assert result.client_secret, "the app registration is still usable without consent"


class TestCertificates:
    def test_generates_a_usable_certificate_and_key(self):
        cert = certificates.generate_client_certificate("UniMonitor", 90)
        assert "BEGIN CERTIFICATE" in cert.certificate_pem
        assert "PRIVATE KEY" in cert.private_key_pem
        assert certificates.thumbprint(cert.certificate_pem) == cert.thumbprint
        remaining = (cert.not_after - datetime.now(UTC)).days
        assert 88 <= remaining <= 90

    def test_validity_is_clamped_to_defaults_and_a_maximum(self):
        assert certificates.clamp_validity_days(None) == 365
        assert certificates.clamp_validity_days(0) == 365
        assert certificates.clamp_validity_days(30) == 30
        assert certificates.clamp_validity_days(5000) == certificates.MAX_VALIDITY_DAYS

    def test_assertion_signed_with_the_private_key(self):
        import jwt

        cert = certificates.generate_client_certificate("UniMonitor", 1)
        assertion = certificates.client_assertion("app-1", "tenant-1", cert.private_key_pem, cert.certificate_pem)
        header = jwt.get_unverified_header(assertion)
        claims = jwt.decode(assertion, options={"verify_signature": False, "verify_aud": False})
        assert header["alg"] == "RS256"
        assert header["x5t"]
        assert claims["aud"].endswith("/tenant-1/oauth2/v2.0/token")
        assert claims["iss"] == claims["sub"] == "app-1"

    async def test_verifies_a_certificate_credential(self):
        cert = certificates.generate_client_certificate("UniMonitor", 1)
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/oauth2/v2.0/token"):
                seen["body"] = request.content.decode()
                return httpx.Response(200, json={"access_token": "tok"})
            if request.url.path.endswith("/organization"):
                return httpx.Response(200, json={"value": [{"id": "t", "displayName": "Contoso"}]})
            return httpx.Response(404, json={})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            name = await m365.verify_client_credentials(
                "tenant-1",
                "app-1",
                certificate_pem=cert.certificate_pem,
                private_key_pem=cert.private_key_pem,
                client=client,
            )

        assert name == "Contoso"
        assert "client_assertion=" in seen["body"]
        assert "client_secret=" not in seen["body"]

    async def test_rejects_missing_credentials(self):
        with pytest.raises(m365.M365Error, match="client secret or a certificate"):
            await m365.verify_client_credentials("tenant-1", "app-1")


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


class TestSignInClient:
    """The device-code sign-in must use a client Entra preauthorizes for app registration."""

    def test_default_client_is_not_the_azure_cli_client(self):
        assert m365.PUBLIC_CLIENT_ID == "14d82eec-204b-4c2f-b7e8-296a70dab67e"

    def test_tenant_can_point_the_wizard_at_its_own_app(self, monkeypatch):
        from unimonitor.config import get_settings

        monkeypatch.setattr(get_settings(), "ENTRA_SIGNIN_CLIENT_ID", "my-own-client")
        assert m365.sign_in_client_id() == "my-own-client"

    async def test_device_code_request_uses_the_configured_client(self):
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = request.content.decode()
            return httpx.Response(
                200,
                json={
                    "device_code": "dc",
                    "user_code": "CODE",
                    "verification_uri": "https://microsoft.com/devicelogin",
                    "expires_in": 900,
                    "interval": 5,
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await m365.start_device_flow(client)

        assert m365.PUBLIC_CLIENT_ID in seen["body"]

    def test_a_blocked_first_party_client_explains_the_way_out(self):
        message = m365._friendly("AADSTS65002: Consent between first party application ...")
        assert "ENTRA_SIGNIN_CLIENT_ID" in message
        assert "manually" in message

    def test_other_errors_are_passed_through(self):
        assert m365._friendly("network down") == "network down"


class TestCertificateHousekeeping:
    async def test_remove_certificate_deletes_the_matching_key(self):
        cert = certificates.generate_client_certificate("UniMonitor", 1)
        removed: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json={
                        "keyCredentials": [
                            {"keyId": "keep", "customKeyIdentifier": "other"},
                            {"keyId": "drop", "customKeyIdentifier": certificates.thumbprint_b64(cert.certificate_pem)},
                        ]
                    },
                )
            removed.append(json.loads(request.content)["keyId"])
            return httpx.Response(204)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            assert await m365.remove_certificate("token", "obj-1", cert.certificate_pem, client=client) is True

        assert removed == ["drop"]

    async def test_remove_certificate_is_a_no_op_when_the_key_is_gone(self):
        cert = certificates.generate_client_certificate("UniMonitor", 1)

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"keyCredentials": []})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            assert await m365.remove_certificate("token", "obj-1", cert.certificate_pem, client=client) is False

    def test_expiry_is_readable_from_the_certificate(self):
        cert = certificates.generate_client_certificate("UniMonitor", 10)
        remaining = (certificates.expiry(cert.certificate_pem) - datetime.now(UTC)).days
        assert 8 <= remaining <= 10
