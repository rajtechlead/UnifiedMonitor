"""OIDC sign-in for Microsoft, Google Workspace and Okta.

Microsoft keeps using MSAL through :mod:`unimonitor.auth.oauth`; this module gives the
other providers the same authorisation-code flow with plain OAuth2/OIDC requests, and
exposes all three through one provider list so the login page does not care which one
a user picks.

Each provider is enabled only when its client id (and, for the confidential clients,
its secret) is configured. The redirect URI is per provider —
``/api/v1/auth/oidc/<provider>/callback`` — and must be registered in the provider's
app registration exactly as returned by :func:`redirect_uri`.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger

logger = get_logger(__name__)

SCOPES = ("openid", "profile", "email")


@dataclass(frozen=True)
class OidcProvider:
    name: str
    label: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.token_url)

    @property
    def confidential(self) -> bool:
        return bool(self.client_secret)


def _definitions() -> dict[str, OidcProvider]:
    settings = get_settings()
    authority = settings.ENTRA_AUTHORITY.rstrip("/")
    entra_tenant = settings.ENTRA_TENANT_ID or "organizations"
    okta_issuer = settings.OKTA_ISSUER.rstrip("/")
    return {
        "microsoft": OidcProvider(
            name="microsoft",
            label="Microsoft",
            client_id=settings.ENTRA_SIGNIN_CLIENT_ID or settings.ENTRA_CLIENT_ID,
            client_secret=settings.ENTRA_CLIENT_SECRET,
            authorize_url=f"{authority}/{entra_tenant}/oauth2/v2.0/authorize",
            token_url=f"{authority}/{entra_tenant}/oauth2/v2.0/token",
            userinfo_url=f"{settings.GRAPH_API_BASE_URL}/{settings.GRAPH_API_VERSION}/me",
        ),
        "google": OidcProvider(
            name="google",
            label="Google Workspace",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            # Public, documented OIDC endpoint — not a credential.
            token_url="https://oauth2.googleapis.com/token",  # noqa: S106
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        ),
        "okta": OidcProvider(
            name="okta",
            label="Okta",
            client_id=settings.OKTA_CLIENT_ID,
            client_secret=settings.OKTA_CLIENT_SECRET,
            authorize_url=f"{okta_issuer}/v1/authorize",
            token_url=f"{okta_issuer}/v1/token",
            userinfo_url=f"{okta_issuer}/v1/userinfo",
        ),
    }


def redirect_uri(provider: str) -> str:
    """The callback registered with the provider, derived from the API's base URL."""
    settings = get_settings()
    base = settings.ENTRA_REDIRECT_URI.rsplit("/auth/", 1)[0]
    return f"{base}/auth/oidc/{provider}/callback"


def providers() -> dict[str, OidcProvider]:
    """Configured providers only, in the configured order."""
    settings = get_settings()
    order = [name.strip().lower() for name in (settings.SSO_PROVIDER_ORDER or "").split(",") if name.strip()]
    catalogue = _definitions()
    return {name: catalogue[name] for name in order if name in catalogue and catalogue[name].configured}


def public_providers() -> list[dict[str, str]]:
    """What the login page needs: the provider's label and where to send the browser."""
    return [
        {"name": provider.name, "label": provider.label, "login_url": f"/api/v1/auth/oidc/{provider.name}/login"} for provider in providers().values()
    ]


def authorize_url(provider: OidcProvider, state: str) -> str:
    query = urlencode(
        {
            "client_id": provider.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri(provider.name),
            "scope": " ".join(SCOPES),
            "state": state,
            "prompt": "select_account",
        }
    )
    return f"{provider.authorize_url}?{query}"


async def exchange_code(provider: OidcProvider, code: str, client: httpx.AsyncClient | None = None) -> dict:
    """Trade the authorisation code for tokens at the provider's token endpoint."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": provider.client_id,
        "redirect_uri": redirect_uri(provider.name),
    }
    if provider.confidential:
        data["client_secret"] = provider.client_secret

    owned = client is None
    http = client or httpx.AsyncClient(timeout=20)
    try:
        response = await http.post(provider.token_url, data=data, headers={"Accept": "application/json"})
        if response.status_code >= 400:
            from unimonitor.exceptions import AuthenticationError

            raise AuthenticationError(f"{provider.name} token exchange failed: HTTP {response.status_code}")
        payload = response.json()
    finally:
        if owned:
            await http.aclose()

    if "access_token" not in payload:
        from unimonitor.exceptions import AuthenticationError

        raise AuthenticationError(f"{provider.name} returned no access token")
    return payload


async def fetch_profile(
    provider: OidcProvider,
    tokens: dict,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Normalise the provider's profile to the shape the user repository stores.

    Microsoft's Graph ``/me`` needs the delegated Graph scope, so its profile goes
    through the existing helper; Google and Okta answer a standard OIDC userinfo
    document.
    """
    if provider.name == "microsoft":
        from unimonitor.auth.oauth import get_entra_user_info

        return await get_entra_user_info(access_token=tokens["access_token"])

    owned = client is None
    http = client or httpx.AsyncClient(timeout=20)
    try:
        response = await http.get(
            provider.userinfo_url,
            headers={"Authorization": f"Bearer {tokens['access_token']}", "Accept": "application/json"},
        )
        if response.status_code >= 400:
            from unimonitor.exceptions import AuthenticationError

            raise AuthenticationError(f"{provider.name} userinfo failed: HTTP {response.status_code}")
        data = response.json()
    finally:
        if owned:
            await http.aclose()

    return {
        "id": data.get("sub", ""),
        "entra_oid": f"{provider.name}:{data.get('sub', '')}"[:36],
        "email": data.get("email") or data.get("preferred_username", ""),
        "display_name": data.get("name", ""),
        "given_name": data.get("given_name", ""),
        "surname": data.get("family_name", ""),
        "tenant_id": data.get("hd") or data.get("org_id"),
    }


__all__ = [
    "OidcProvider",
    "authorize_url",
    "exchange_code",
    "fetch_profile",
    "providers",
    "public_providers",
    "redirect_uri",
]
