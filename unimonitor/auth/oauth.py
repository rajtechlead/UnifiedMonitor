"""Entra ID OAuth2 / MSAL authentication."""

from __future__ import annotations

import asyncio

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


def client_credential() -> str | dict[str, str]:
    """The configured credential: a certificate when there is one, else the secret."""
    settings = get_settings()
    if settings.ENTRA_CLIENT_PRIVATE_KEY and settings.ENTRA_CLIENT_CERTIFICATE:
        from unimonitor.onboarding.certificates import certificate_credential

        return certificate_credential(settings.ENTRA_CLIENT_PRIVATE_KEY, settings.ENTRA_CLIENT_CERTIFICATE)
    return settings.ENTRA_CLIENT_SECRET


def get_msal_app(tenant_id: str | None = None) -> msal.ConfidentialClientApplication:
    """Create an MSAL confidential client application."""
    settings = get_settings()
    authority = f"{settings.ENTRA_AUTHORITY}/{tenant_id or settings.ENTRA_TENANT_ID}"
    return msal.ConfidentialClientApplication(
        client_id=settings.ENTRA_CLIENT_ID,
        client_credential=client_credential(),
        authority=authority,
    )


def client_credential_for(
    client_secret: str | None = None,
    certificate_pem: str | None = None,
    private_key_pem: str | None = None,
) -> str | dict[str, str]:
    """An explicit credential: the certificate when there is one, else the secret."""
    if certificate_pem and private_key_pem:
        from unimonitor.onboarding.certificates import certificate_credential

        return certificate_credential(private_key_pem, certificate_pem)
    return client_secret or ""


def get_msal_app_for_tenant(
    client_id: str,
    client_secret: str,
    tenant_id: str,
    certificate_pem: str = "",
    private_key_pem: str = "",
) -> msal.ConfidentialClientApplication:
    """Create an MSAL app with per-tenant credentials.

    Certificate credentials are supported because the setup wizard now defaults to
    them; a client secret is only used when no certificate pair is supplied.
    """
    settings = get_settings()
    authority = f"{settings.ENTRA_AUTHORITY}/{tenant_id}"
    return msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_credential_for(client_secret, certificate_pem, private_key_pem),
        authority=authority,
    )


async def acquire_token_for_client(
    tenant_id: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    certificate_pem: str | None = None,
    private_key_pem: str | None = None,
) -> str:
    """Acquire an application token (client credentials flow) for Graph API.

    MSAL is a blocking HTTP client, so the call runs on a worker thread and the
    coroutine contract callers already await is unchanged.
    """
    return await asyncio.to_thread(
        _acquire_token_for_client_sync,
        tenant_id,
        client_id,
        client_secret,
        certificate_pem,
        private_key_pem,
    )


def _acquire_token_for_client_sync(
    tenant_id: str | None,
    client_id: str | None,
    client_secret: str | None,
    certificate_pem: str | None = None,
    private_key_pem: str | None = None,
) -> str:
    """Blocking client-credentials flow, off the event loop."""
    get_settings()
    has_certificate = bool(certificate_pem and private_key_pem)
    if client_id and tenant_id and (client_secret or has_certificate):
        app = get_msal_app_for_tenant(
            client_id,
            client_secret or "",
            tenant_id,
            certificate_pem=certificate_pem or "",
            private_key_pem=private_key_pem or "",
        )
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


def build_authorize_url(
    state: str,
    *,
    client_id: str | None = None,
    tenant_id: str | None = None,
    client_secret: str | None = None,
    certificate_pem: str | None = None,
    private_key_pem: str | None = None,
) -> str:
    """Generate the Entra ID authorisation URL for the connected app.

    Explicit credentials matter on a fresh install: the wizard writes the app to the
    database and the vault, so ``settings`` may still be empty for the first minutes
    after setup unless the caller passes what it resolved.
    """
    settings = get_settings()
    if client_id and tenant_id:
        app = get_msal_app_for_tenant(
            client_id,
            client_secret or "",
            tenant_id,
            certificate_pem=certificate_pem or "",
            private_key_pem=private_key_pem or "",
        )
    else:
        app = get_msal_app(tenant_id)
    return app.get_authorization_request_url(
        scopes=DELEGATED_SCOPES,
        state=state,
        redirect_uri=settings.ENTRA_REDIRECT_URI,
    )


async def exchange_code_for_token(
    code: str,
    *,
    client_id: str | None = None,
    tenant_id: str | None = None,
    client_secret: str | None = None,
    certificate_pem: str | None = None,
    private_key_pem: str | None = None,
) -> dict:
    """Exchange the auth code for tokens (delegated flow, async wrapper)."""
    return await asyncio.to_thread(
        _exchange_code_for_token_sync,
        code,
        client_id,
        tenant_id,
        client_secret,
        certificate_pem,
        private_key_pem,
    )


def _exchange_code_for_token_sync(
    code: str,
    client_id: str | None = None,
    tenant_id: str | None = None,
    client_secret: str | None = None,
    certificate_pem: str | None = None,
    private_key_pem: str | None = None,
) -> dict:
    """Synchronous implementation of code exchange."""
    settings = get_settings()
    if client_id and tenant_id:
        app = get_msal_app_for_tenant(
            client_id,
            client_secret or "",
            tenant_id,
            certificate_pem=certificate_pem or "",
            private_key_pem=private_key_pem or "",
        )
    else:
        app = get_msal_app(tenant_id)
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
