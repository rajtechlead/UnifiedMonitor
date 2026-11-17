"""Google access tokens minted from a service-account key.

Google Cloud and Google Workspace are read over REST by the collectors, which need an
OAuth access token. Rather than asking the administrator to paste a token that expires
within the hour, the wizard stores the service-account key and this module mints a
token when one is needed. Google Workspace additionally requires domain-wide
delegation, so the key's client is impersonated against an administrator account.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt

from unimonitor.core.logging import get_logger

logger = get_logger(__name__)

GOOGLE_OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"

GCP_SCOPES = "https://www.googleapis.com/auth/cloud-platform.read-only"
WORKSPACE_SCOPES = " ".join(
    [
        "https://www.googleapis.com/auth/admin.directory.user.readonly",
        "https://www.googleapis.com/auth/admin.directory.rolemanagement.readonly",
        "https://www.googleapis.com/auth/admin.directory.device.mobile.readonly",
        "https://www.googleapis.com/auth/admin.directory.customer.readonly",
        "https://www.googleapis.com/auth/admin.reports.audit.readonly",
    ]
)


class GoogleAuthError(RuntimeError):
    """The service-account key could not be used to obtain a token."""


@dataclass
class _CachedToken:
    token: str
    expires_at: float


_cache: dict[str, _CachedToken] = {}


def _parse_key(credentials_json: str) -> dict[str, Any]:
    try:
        key = json.loads(credentials_json)
    except json.JSONDecodeError as exc:
        raise GoogleAuthError("That does not look like a service-account JSON key.") from exc
    if not key.get("client_email") or not key.get("private_key"):
        raise GoogleAuthError("The service-account key is missing client_email or private_key.")
    return key


async def mint_access_token(
    credentials_json: str,
    scopes: str,
    *,
    subject: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Exchange a service-account key for an access token (JWT bearer grant)."""
    key = _parse_key(credentials_json)
    cache_key = f"{key['client_email']}|{scopes}|{subject or ''}"
    cached = _cache.get(cache_key)
    if cached and cached.expires_at > time.time() + 60:
        return cached.token

    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": key["client_email"],
        "scope": scopes,
        "aud": GOOGLE_OAUTH_ENDPOINT,
        "iat": now,
        "exp": now + 3600,
    }
    if subject:
        claims["sub"] = subject
    try:
        assertion = jwt.encode(claims, key["private_key"], algorithm="RS256")
    except Exception as exc:  # noqa: BLE001 — any key problem is the same message to the user
        raise GoogleAuthError(f"Could not sign the Google token request: {exc}") from exc

    owned = client is None
    http = client or httpx.AsyncClient(timeout=30)
    try:
        resp = await http.post(
            GOOGLE_OAUTH_ENDPOINT,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
        )
        data = resp.json() if resp.content else {}
        token = data.get("access_token")
        if not token:
            raise GoogleAuthError(data.get("error_description", "Google rejected the service-account key."))
        _cache[cache_key] = _CachedToken(token=token, expires_at=time.time() + int(data.get("expires_in", 3600)))
        return token
    finally:
        if owned:
            await http.aclose()


def reset_cache() -> None:
    """Drop cached tokens (tests, and after a connection is replaced)."""
    _cache.clear()
