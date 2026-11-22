"""A caller-controlled ``tenant_id`` must never widen what a request can read.

Administrators may read any tenant and may omit the parameter to read the whole
install; everyone else is pinned to their home tenant plus any delegated grant.
"""

import bcrypt
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

PASSWORD = "TestPassword123!"
OTHER_TENANT_ID = "other-tenant-id-000000000002"


@pytest.fixture
async def other_tenant(db_session):
    from unimonitor.db.models.tenant import Tenant

    tenant = Tenant(
        id=OTHER_TENANT_ID,
        name="Other Organization",
        tenant_id="other-tenant",
        domain="other.example.com",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


async def _make_user(db_session, tenant_id: str, role: str = "analyst", email: str = "analyst@test.example.com"):
    from unimonitor.db.models.user import AppUser

    user = AppUser(
        id=f"user-{role}-{(tenant_id or 'none')[-4:]}",
        email=email,
        full_name="Tenant Analyst",
        hashed_password=bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode("utf-8"),
        role=role,
        is_active=True,
        tenant_id=tenant_id,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _headers(client: AsyncClient, email: str) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _finding(tenant_id: str, control_id: str, service: str = "entra_id"):
    from unimonitor.db.models.finding import Finding

    return Finding(
        tenant_id=tenant_id,
        external_control_id=control_id,
        title=f"Finding {control_id}",
        description="scoped",
        severity="high",
        state="not_implemented",
        category="identity",
        service=service,
        risk_score=8,
    )


class TestTenantScope:
    async def test_analyst_cannot_read_another_tenant(self, client: AsyncClient, db_session, tenant, other_tenant):
        await _make_user(db_session, tenant.id)
        headers = await _headers(client, "analyst@test.example.com")
        db_session.add(_finding(other_tenant.id, "CTRL-OTHER-001"))
        await db_session.flush()

        for path in ("/api/v1/findings", "/api/v1/dashboard/risk", "/api/v1/dashboard/ciso"):
            response = await client.get(path, params={"tenant_id": other_tenant.id}, headers=headers)
            assert response.status_code == 403, f"{path} leaked tenant data: {response.status_code}"

    async def test_analyst_is_pinned_to_the_home_tenant(self, client: AsyncClient, db_session, tenant, other_tenant):
        await _make_user(db_session, tenant.id)
        headers = await _headers(client, "analyst@test.example.com")
        db_session.add_all(
            [
                _finding(tenant.id, "CTRL-HOME-001"),
                _finding(other_tenant.id, "CTRL-OTHER-001"),
            ]
        )
        await db_session.flush()

        response = await client.get("/api/v1/findings", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["external_control_id"] == "CTRL-HOME-001"

    async def test_delegated_grant_opens_the_tenant(self, client: AsyncClient, db_session, tenant, other_tenant):
        user = await _make_user(db_session, tenant.id)
        headers = await _headers(client, "analyst@test.example.com")
        db_session.add(_finding(other_tenant.id, "CTRL-OTHER-001"))
        await db_session.flush()

        blocked = await client.get("/api/v1/findings", params={"tenant_id": other_tenant.id}, headers=headers)
        assert blocked.status_code == 403

        from unimonitor.db.models.tenant_access import TenantAccess

        db_session.add(TenantAccess(user_id=user.id, tenant_id=other_tenant.id, role="viewer"))
        await db_session.flush()

        allowed = await client.get("/api/v1/findings", params={"tenant_id": other_tenant.id}, headers=headers)
        assert allowed.status_code == 200
        assert allowed.json()["total"] == 1

    async def test_admin_may_read_any_tenant(self, client: AsyncClient, auth_headers: dict, db_session, other_tenant):
        db_session.add(_finding(other_tenant.id, "CTRL-OTHER-001"))
        await db_session.flush()

        response = await client.get("/api/v1/findings", params={"tenant_id": other_tenant.id}, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["total"] == 1

    async def test_insufficient_role_is_403_not_500(self, client: AsyncClient, db_session, tenant):
        await _make_user(db_session, tenant.id)
        headers = await _headers(client, "analyst@test.example.com")

        response = await client.get("/api/v1/users", headers=headers)
        assert response.status_code == 403

    async def test_a_body_carried_tenant_id_is_scoped_too(self, client: AsyncClient, db_session, tenant, other_tenant):
        """A Pydantic request field bypasses the parameter dependency."""
        await _make_user(db_session, tenant.id)
        headers = await _headers(client, "analyst@test.example.com")

        response = await client.post(
            "/api/v1/reports/generate",
            json={"run_id": "does-not-exist", "tenant_id": other_tenant.id},
            headers=headers,
        )
        assert response.status_code == 403
