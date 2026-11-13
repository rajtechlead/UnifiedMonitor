"""Entra ID OAuth2 / MSAL authentication."""

from __future__ import annotations

import msal

from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger

logger = get_logger(__name__)

# Microsoft Graph scopes required by UniMonitor
GRAPH_SCOPES = [
    "https://graph.microsoft.com/.default",
]

# Interactive / delegated scopes for the web UI
DELEGATED_SCOPES = [
    "openid",
    "profile",
    "email",
    "offline_access",
    "User.Read",
    "Organization.Read.All",
]


def get_msal_app(tenant_id: str | None = None) -> msal.ConfidentialClientApplication:
    """Create an MSAL confidential client application."""
    settings = get_settings()
    authority = f"{settings.ENTRA_AUTHORITY}/{tenant_id or settings.ENTRA_TENANT_ID}"
    return msal.ConfidentialClientApplication(
        client_id=settings.ENTRA_CLIENT_ID,
        client_credential=settings.ENTRA_CLIENT_SECRET,
        authority=authority,
    )


def get_msal_app_for_tenant(
    client_id: str,
    client_secret: str,
    tenant_id: str,
) -> msal.ConfidentialClientApplication:
    """Create an MSAL app with per-tenant credentials."""
    settings = get_settings()
    authority = f"{settings.ENTRA_AUTHORITY}/{tenant_id}"
    return msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority,
    )


async def acquire_token_for_client(
    tenant_id: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> str:
    """Acquire an application token (client credentials flow) for Graph API."""
    get_settings()
    if client_id and client_secret and tenant_id:
        app = get_msal_app_for_tenant(client_id, client_secret, tenant_id)
    else:
        app = get_msal_app(tenant_id)

    result = app.acquire_token_silent(GRAPH_SCOPES, account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=GRAPH_SCOPES)

    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "Unknown"))
        logger.error("MSAL token acquisition failed", error=error, tenant_id=tenant_id)
        from unimonitor.exceptions import AuthenticationError

        raise AuthenticationError(f"Failed to acquire Graph token: {error}")

    return result["access_token"]


def get_auth_code_url(state: str, nonce: str) -> str:
    """Generate the Entra ID authorisation URL for the web login flow."""
    settings = get_settings()
    app = get_msal_app()
    return app.get_authorization_request_url(
        scopes=DELEGATED_SCOPES,
        state=state,
        nonce=nonce,
        redirect_uri=settings.ENTRA_REDIRECT_URI,
    )


def build_authorize_url(state: str) -> str:
    """Generate the Entra ID authorisation URL (alias for auth routes)."""
    settings = get_settings()
    app = get_msal_app()
    return app.get_authorization_request_url(
        scopes=DELEGATED_SCOPES,
        state=state,
        redirect_uri=settings.ENTRA_REDIRECT_URI,
    )


async def exchange_code_for_token(code: str) -> dict:
    """Exchange the auth code for tokens (delegated flow, async wrapper)."""
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _exchange_code_for_token_sync, code)


def _exchange_code_for_token_sync(code: str) -> dict:
    """Synchronous implementation of code exchange."""
    settings = get_settings()
    app = get_msal_app()
    result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=DELEGATED_SCOPES,
        redirect_uri=settings.ENTRA_REDIRECT_URI,
    )
    if "error" in result:
        from unimonitor.exceptions import AuthenticationError

        raise AuthenticationError(f"Token exchange failed: {result.get('error_description', result['error'])}")
    return result


async def get_entra_user_info(access_token: str) -> dict:
    """Fetch the signed-in user's profile from Microsoft Graph /me endpoint."""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "id": data.get("id", ""),
            "email": data.get("mail") or data.get("userPrincipalName", ""),
            "display_name": data.get("displayName", ""),
            "given_name": data.get("givenName", ""),
            "surname": data.get("surname", ""),
            "job_title": data.get("jobTitle"),
            "tenant_id": data.get("tenantId"),
            "entra_oid": data.get("id", ""),
        }
