"""
Integration-style unit tests for api/v1/auth.py using the ASGI test client.
Covers: login (success/failure/inactive), /me, refresh, logout.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# /login  (POST)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success(client, admin_user):
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": admin_user.email, "password": "TestPassword123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    # The SPA stores this profile; without it every login looked like a viewer.
    assert body["user"]["role"] == "admin"
    assert body["user"]["email"] == admin_user.email


@pytest.mark.asyncio
async def test_second_login_still_reports_the_admin_role(client, admin_user):
    """Sign out and back in must not downgrade the account in the UI."""
    for _ in range(2):
        r = await client.post(
            "/api/v1/auth/login",
            data={"username": admin_user.email, "password": "TestPassword123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_login_wrong_password(client, admin_user):
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": admin_user.email, "password": "WrongPassword!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 401
    assert "Incorrect" in r.json()["detail"]


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody@nowhere.com", "password": "Whatever1!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client, admin_user, db_session):
    # Deactivate the user
    admin_user.is_active = False
    await db_session.flush()

    r = await client.post(
        "/api/v1/auth/login",
        data={"username": admin_user.email, "password": "TestPassword123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 401
    assert "disabled" in r.json()["detail"].lower()

    # Re-activate so other tests are not affected
    admin_user.is_active = True
    await db_session.flush()


# ---------------------------------------------------------------------------
# /me  (GET)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_authenticated(client, auth_headers, admin_user):
    r = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == admin_user.email
    assert body["role"] == admin_user.role
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_me_bad_token(client):
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# /refresh  (POST)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_success(client, admin_user):
    # First login to get tokens
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": admin_user.email, "password": "TestPassword123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    tokens = r.json()

    r2 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert "access_token" in body
    assert "refresh_token" in body


@pytest.mark.asyncio
async def test_refresh_bad_token(client):
    r = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not.a.valid.token"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_access_token_rejected(client, admin_user):
    """An access token cannot be used as a refresh token."""
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": admin_user.email, "password": "TestPassword123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    tokens = r.json()

    r2 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["access_token"]},  # wrong type
    )
    assert r2.status_code == 401


# ---------------------------------------------------------------------------
# /logout  (POST)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_success(client, auth_headers):
    r = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_logout_unauthenticated(client):
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# /login (Entra redirect) and /callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_entra_login_redirects(client):
    """GET /login goes straight to Entra with the connected app and our scopes."""
    connected = {"configured": True, "client_id": "client-123", "directory": "tenant-123", "source": "connection"}
    with patch("unimonitor.onboarding.service.microsoft_app", new=AsyncMock(return_value=connected)):
        with patch("unimonitor.api.v1.auth.cache_set", new=AsyncMock(return_value=True)):
            r = await client.get("/api/v1/auth/login", follow_redirects=False)
    assert r.status_code in (302, 307)
    location = r.headers.get("location", "")
    assert location.startswith("https://login.microsoftonline.com/tenant-123/oauth2/v2.0/authorize?")
    assert "client_id=client-123" in location
    assert "redirect_uri=" in location
    assert "User.Read" in location


@pytest.mark.asyncio
async def test_entra_login_without_an_app_explains_why(client):
    """No connected app is a redirect with a reason, not a bare JSON error."""
    with patch(
        "unimonitor.onboarding.service.microsoft_app",
        new=AsyncMock(return_value={"configured": False, "client_id": "", "directory": ""}),
    ):
        r = await client.get("/api/v1/auth/login", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    assert "error=sso_unavailable" in r.headers["location"]
    assert "reason=" in r.headers["location"]


@pytest.mark.asyncio
async def test_callback_error_param_returns_to_the_login_page(client):
    """A denied sign-in shows the reason on the login page, not a JSON page."""
    r = await client.get(
        "/api/v1/auth/callback",
        params={"code": "x", "state": "s", "error": "access_denied", "error_description": "User denied"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303, 307)
    assert "error=sso_failed" in r.headers["location"]
    assert "User%20denied" in r.headers["location"]


@pytest.mark.asyncio
async def test_callback_invalid_state(client):
    """OAuth callback with unknown state returns 400."""
    with patch("unimonitor.api.v1.auth.cache_get", new=AsyncMock(return_value=None)):
        r = await client.get(
            "/api/v1/auth/callback",
            params={"code": "auth_code", "state": "unknown_state"},
        )
    assert r.status_code == 400
    assert "state" in r.json()["detail"].lower()
