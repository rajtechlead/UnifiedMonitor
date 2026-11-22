"""SSO provisioning, AI provider status and the remediation trigger."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from unimonitor.db.repositories.tenant_repo import UserRepository
from unimonitor.exceptions import AuthenticationError

pytestmark = pytest.mark.asyncio


class TestSsoProvisionsIntoATenant:
    async def test_a_first_time_sso_user_is_attached_to_the_only_tenant(self, db_session, tenant):
        """AppUser.tenant_id is NOT NULL; this used to fail with an integrity error."""
        repo = UserRepository(db_session)
        user = await repo.upsert_from_entra({"entra_oid": "new-oid", "email": "newcomer@contoso.com", "display_name": "Newcomer", "tenant_id": None})
        assert user.tenant_id == tenant.id
        assert user.role == "viewer"

    async def test_the_entra_tid_selects_the_matching_tenant(self, db_session, tenant):
        repo = UserRepository(db_session)
        user = await repo.upsert_from_entra(
            {
                "entra_oid": "oid-2",
                "email": "second@contoso.com",
                "display_name": "Second",
                "tenant_id": tenant.entra_tenant_id,
            }
        )
        assert user.tenant_id == tenant.id

    async def test_an_ambiguous_install_refuses_rather_than_guessing(self, db_session, tenant):
        from unimonitor.db.models.tenant import Tenant

        db_session.add(Tenant(tenant_id="other-org", name="Other Org", domain="other.example.com"))
        await db_session.flush()

        repo = UserRepository(db_session)
        with pytest.raises(AuthenticationError):
            await repo.upsert_from_entra({"entra_oid": "oid-3", "email": "who@example.com", "display_name": "Who", "tenant_id": None})


class TestSsoProvidersEndpoint:
    async def test_lists_only_configured_providers(self, client: AsyncClient):
        r = await client.get("/api/v1/auth/sso/providers")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        for entry in r.json():
            assert {"name", "label", "login_url"} <= set(entry)

    async def test_an_unknown_provider_redirects_to_the_login_error(self, client: AsyncClient):
        r = await client.get("/api/v1/auth/oidc/unknown/login", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/login?error=sso_unavailable"


class TestAiStatus:
    async def test_status_never_returns_a_key(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/ai/status", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["anonymised"] is True
        assert isinstance(body["providers"], list)
        assert "api_key" not in r.text
        assert "sk-" not in r.text

    async def test_ask_requires_authentication(self, client: AsyncClient):
        assert (await client.get("/api/v1/ai/status")).status_code == 401

    async def test_the_remediation_trigger_requires_a_finding(self, client: AsyncClient, auth_headers: dict):
        r = await client.post(
            "/api/v1/findings/does-not-exist/remediate",
            json={"force_refresh": False},
            headers=auth_headers,
        )
        assert r.status_code == 404
