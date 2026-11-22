"""Generic OIDC sign-in: provider selection, redirect, code exchange, profile."""

from __future__ import annotations

import httpx
import pytest

from unimonitor.auth import oidc


def _settings(**overrides):
    from unimonitor.config import Settings

    base = Settings(
        ENTRA_TENANT_ID="contoso.onmicrosoft.com",
        ENTRA_CLIENT_ID="entra-app",
        ENTRA_REDIRECT_URI="https://unimonitor.contoso.com/api/v1/auth/callback",
        GOOGLE_CLIENT_ID="google-app",
        GOOGLE_CLIENT_SECRET="google-secret",
        OKTA_ISSUER="https://contoso.okta.com",
        OKTA_CLIENT_ID="okta-app",
        OKTA_CLIENT_SECRET="okta-secret",
        SSO_PROVIDER_ORDER="microsoft,google,okta",
    )
    return base.model_copy(update=overrides)


@pytest.fixture
def configured(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(oidc, "get_settings", lambda: settings)
    return settings


class TestProviders:
    def test_all_three_providers_are_offered_when_configured(self, configured):
        names = [provider["name"] for provider in oidc.public_providers()]
        assert names == ["microsoft", "google", "okta"]
        assert oidc.public_providers()[1]["login_url"] == "/api/v1/auth/oidc/google/login"

    def test_an_unconfigured_provider_is_not_offered(self, monkeypatch):
        settings = _settings(GOOGLE_CLIENT_ID="", OKTA_CLIENT_ID="")
        monkeypatch.setattr(oidc, "get_settings", lambda: settings)
        assert [provider["name"] for provider in oidc.public_providers()] == ["microsoft"]

    def test_the_configured_order_is_respected(self, monkeypatch):
        settings = _settings(SSO_PROVIDER_ORDER="okta,microsoft")
        monkeypatch.setattr(oidc, "get_settings", lambda: settings)
        assert [provider["name"] for provider in oidc.public_providers()] == ["okta", "microsoft"]

    def test_each_provider_gets_its_own_callback(self, configured):
        assert oidc.redirect_uri("google") == "https://unimonitor.contoso.com/api/v1/auth/oidc/google/callback"


class TestAuthorize:
    def test_the_authorization_url_carries_client_state_and_scope(self, configured):
        provider = oidc.providers()["google"]
        url = oidc.authorize_url(provider, "state-123")
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert "client_id=google-app" in url
        assert "state=state-123" in url
        assert "response_type=code" in url
        assert "scope=openid+profile+email" in url
        assert "redirect_uri=https%3A%2F%2Funimonitor.contoso.com" in url


class TestExchange:
    @pytest.mark.asyncio
    async def test_the_code_is_exchanged_with_the_client_secret(self, configured):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["body"] = request.content.decode()
            return httpx.Response(200, json={"access_token": "at", "id_token": "it"})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        tokens = await oidc.exchange_code(oidc.providers()["google"], "code-1", client=client)

        assert tokens["access_token"] == "at"
        assert captured["url"] == "https://oauth2.googleapis.com/token"
        assert "grant_type=authorization_code" in captured["body"]
        assert "client_secret=google-secret" in captured["body"]
        assert "code=code-1" in captured["body"]

    @pytest.mark.asyncio
    async def test_a_rejected_code_is_an_authentication_error(self, configured):
        from unimonitor.exceptions import AuthenticationError

        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(400)))
        with pytest.raises(AuthenticationError):
            await oidc.exchange_code(oidc.providers()["google"], "bad", client=client)

    @pytest.mark.asyncio
    async def test_google_profile_is_normalised(self, configured):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["Authorization"] == "Bearer at"
            return httpx.Response(
                200,
                json={"sub": "1234", "email": "alice@contoso.com", "name": "Alice", "given_name": "Alice", "hd": "contoso.com"},
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        profile = await oidc.fetch_profile(oidc.providers()["google"], {"access_token": "at"}, client=client)

        assert profile["email"] == "alice@contoso.com"
        assert profile["display_name"] == "Alice"
        assert profile["entra_oid"] == "google:1234"
        assert profile["tenant_id"] == "contoso.com"

    @pytest.mark.asyncio
    async def test_microsoft_profile_uses_graph(self, configured, monkeypatch):
        async def _me(access_token: str) -> dict:
            assert access_token == "graph-token"
            return {"id": "oid", "email": "bob@contoso.com", "display_name": "Bob"}

        monkeypatch.setattr("unimonitor.auth.oauth.get_entra_user_info", _me)
        profile = await oidc.fetch_profile(oidc.providers()["microsoft"], {"access_token": "graph-token"})
        assert profile["email"] == "bob@contoso.com"
