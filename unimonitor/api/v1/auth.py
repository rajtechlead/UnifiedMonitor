"""Authentication endpoints — Entra ID OAuth2 + JWT."""

from __future__ import annotations

import secrets
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import get_current_user
from unimonitor.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from unimonitor.auth.oauth import (
    build_authorize_url,
    exchange_code_for_token,
    get_entra_user_info,
)
from unimonitor.config import get_settings
from unimonitor.core.cache import cache_get, cache_set
from unimonitor.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    tenant_id: str | None = None
    is_active: bool = True


@router.post("/login")
async def login_local(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Local username/password login (OAuth2 password flow).

    Authenticates against the local `app_users` table using bcrypt.
    For Entra ID SSO, use GET /login to start the OAuth2 redirect flow.
    """
    import bcrypt as _bcrypt
    from sqlalchemy import select

    from unimonitor.db.models.user import AppUser

    settings = get_settings()

    result = await db.execute(select(AppUser).where(AppUser.email == form_data.username))
    db_user = result.scalar_one_or_none()

    if not db_user or not db_user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    pw_bytes = form_data.password.encode("utf-8")[:72]
    if not _bcrypt.checkpw(pw_bytes, db_user.hashed_password.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )

    access_token = create_access_token(
        subject=db_user.id,
        tenant_id=db_user.tenant_id,
        role=db_user.role,
    )
    refresh_token = create_refresh_token(subject=db_user.id, tenant_id=db_user.tenant_id)
    logger.info("local_login_success", user_id=db_user.id, email=db_user.email)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/sso")
async def sso_status(db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    """Whether "Sign in with Microsoft" can work on this install.

    The setup wizard stores the Entra app in the database and the vault, not in
    .env, so the connected app — not the settings singleton — decides this.
    """
    from unimonitor.onboarding.service import microsoft_app

    app = await microsoft_app(db)
    settings = get_settings()
    return {
        "enabled": bool(app.get("configured") and settings.ENTRA_REDIRECT_URI),
        "provider": "microsoft",
        "source": app.get("source"),
        "reason": None if app.get("configured") else "Connect Microsoft 365 under Settings → Platform connections.",
    }


@router.get("/login")
async def login(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redirect_after: Annotated[str, Query(alias="redirect")] = "/",
) -> RedirectResponse:
    """Redirect to Entra ID OAuth2 authorization endpoint."""
    from unimonitor.onboarding.service import microsoft_app

    app = await microsoft_app(db)
    state = secrets.token_urlsafe(32)

    # Store state + redirect destination in cache (5 min TTL)
    await cache_set(f"oauth_state:{state}", {"redirect": redirect_after}, ttl=300)

    try:
        authorize_url = build_authorize_url(
            state=state,
            client_id=app["client_id"],
            tenant_id=app["directory"],
            client_secret=app.get("client_secret") or None,
            certificate_pem=app.get("certificate_pem") or None,
            private_key_pem=app.get("private_key_pem") or None,
        )
    except Exception as exc:  # bad app id / authority: tell the page, don't 500
        logger.warning("oauth_login_unavailable", error=str(exc))
        return RedirectResponse(url="/login?error=sso_unavailable", status_code=status.HTTP_303_SEE_OTHER)

    logger.info("oauth_login_initiated", state=state[:8], source=app.get("source"))
    return RedirectResponse(url=authorize_url, status_code=status.HTTP_302_FOUND)


@router.get("/callback")
async def oauth_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    code: Annotated[str, Query(...)],
    state: Annotated[str, Query(...)],
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
) -> Response:
    """Handle Entra ID OAuth callback, issue JWT tokens."""
    if error:
        logger.warning("oauth_callback_error", error=error, description=error_description)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth error: {error_description or error}",
        )

    # Validate state
    state_data = await cache_get(f"oauth_state:{state}")
    if not state_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state parameter",
        )

    from unimonitor.onboarding.service import microsoft_app

    app = await microsoft_app(db)
    try:
        token_data = await exchange_code_for_token(
            code=code,
            client_id=app.get("client_id"),
            tenant_id=app.get("directory"),
            client_secret=app.get("client_secret") or None,
            certificate_pem=app.get("certificate_pem") or None,
            private_key_pem=app.get("private_key_pem") or None,
        )
    except Exception as exc:
        logger.error("token_exchange_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange authorization code for token",
        ) from exc

    # Fetch user info from Graph /me
    try:
        user_info = await get_entra_user_info(access_token=token_data["access_token"])
    except Exception as exc:
        logger.error("user_info_fetch_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve user information",
        ) from exc

    return await complete_sign_in(user_info, state_data.get("redirect", "/"))


async def complete_sign_in(user_info: dict, redirect_after: str) -> RedirectResponse:
    """Create or update the local account and hand the browser its tokens.

    Shared by the Microsoft MSAL callback and the generic OIDC callback so both
    providers provision users identically.
    """
    settings = get_settings()

    from unimonitor.db.base import async_session_factory
    from unimonitor.db.repositories.tenant_repo import UserRepository

    try:
        async with async_session_factory() as session:
            user_repo = UserRepository(session)
            db_user = await user_repo.upsert_from_entra(user_info)
            await session.commit()
    except Exception as exc:
        from unimonitor.exceptions import AuthenticationError

        if isinstance(exc, AuthenticationError):
            logger.warning("sso_sign_in_rejected", error=str(exc))
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        raise

    access_token = create_access_token(
        subject=db_user.id,
        tenant_id=getattr(db_user, "tenant_id", ""),
        role=getattr(db_user, "role", "viewer"),
        extra={"email": getattr(db_user, "email", ""), "display_name": getattr(db_user, "full_name", "")},
    )
    refresh_token = create_refresh_token(
        subject=db_user.id,
        tenant_id=getattr(db_user, "tenant_id", ""),
    )
    logger.info("user_authenticated", user_id=db_user.id, email=db_user.email)

    redirect_to = redirect_after if (redirect_after or "").startswith("/") and not redirect_after.startswith("//") else "/"
    frontend_url = settings.UNIMONITOR_FRONTEND_URL.rstrip("/")
    return RedirectResponse(
        url=f"{frontend_url}{redirect_to}#access_token={access_token}&refresh_token={refresh_token}",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/refresh")
async def refresh_token(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Exchange a refresh token for a new access token."""
    settings = get_settings()
    try:
        payload = decode_refresh_token(body.refresh_token)
    except Exception:
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    # Load user from DB to get current role
    from sqlalchemy import select

    from unimonitor.db.models.user import AppUser

    result = await db.execute(select(AppUser).where(AppUser.id == user_id))
    db_user = result.scalar_one_or_none()

    if not db_user or not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    new_access = create_access_token(
        subject=db_user.id,
        tenant_id=db_user.tenant_id,
        role=db_user.role,
        extra={"email": db_user.email, "display_name": getattr(db_user, "full_name", "")},
    )
    new_refresh = create_refresh_token(subject=db_user.id, tenant_id=db_user.tenant_id)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))],
    current_user: Annotated[Any, Depends(get_current_user)],
) -> None:
    """Invalidate the current session (blacklist JTI in cache)."""
    # Extract JTI from raw JWT payload (not stored on AppUser ORM object)
    if credentials:
        from unimonitor.auth.jwt import validate_access_token

        try:
            payload = validate_access_token(credentials.credentials)
            jti = payload.get("jti")
            if jti:
                exp = payload.get("exp", 0)
                import time

                ttl = max(int(exp - time.time()), 1)
                await cache_set(f"token_blacklist:{jti}", True, ttl=ttl)
        except Exception:  # noqa: S110
            pass
    logger.info("user_logged_out", user_id=current_user.id)


@router.get("/me")
async def get_me(
    current_user: Annotated[Any, Depends(get_current_user)],
) -> UserProfile:
    """Return the authenticated user's profile."""
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.full_name,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        is_active=current_user.is_active,
    )


@router.get("/sso/providers")
async def sso_providers() -> list[dict[str, str]]:
    """Every configured sign-in provider, for the login page.

    Microsoft is included when the setup wizard's Entra app is present; Google and
    Okta appear once their client id and secret are configured.
    """
    from unimonitor.auth.oidc import public_providers

    return public_providers()


@router.get("/oidc/{provider}/login")
async def oidc_login(
    provider: str,
    redirect_after: Annotated[str, Query(alias="redirect")] = "/",
) -> RedirectResponse:
    """Start a generic OIDC sign-in (Microsoft, Google Workspace or Okta)."""
    from unimonitor.auth.oidc import authorize_url, providers

    catalogue = providers()
    selected = catalogue.get(provider.lower())
    if selected is None:
        return RedirectResponse(url="/login?error=sso_unavailable", status_code=status.HTTP_303_SEE_OTHER)

    state = secrets.token_urlsafe(32)
    await cache_set(f"oauth_state:{state}", {"redirect": redirect_after, "provider": selected.name}, ttl=300)
    logger.info("oidc_login_initiated", provider=selected.name)
    return RedirectResponse(url=authorize_url(selected, state), status_code=status.HTTP_302_FOUND)


@router.get("/oidc/{provider}/callback")
async def oidc_callback(
    provider: str,
    code: Annotated[str, Query(...)],
    state: Annotated[str, Query(...)],
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
) -> Response:
    """Finish a generic OIDC sign-in and issue this application's tokens."""
    if error:
        logger.warning("oidc_callback_error", provider=provider, error=error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth error: {error_description or error}",
        )

    state_data = await cache_get(f"oauth_state:{state}")
    if not state_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OAuth state parameter")
    if state_data.get("provider") not in (None, provider.lower()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state does not match the provider")

    from unimonitor.auth.oidc import exchange_code, fetch_profile, providers

    selected = providers().get(provider.lower())
    if selected is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sign-in provider is not configured")

    try:
        tokens = await exchange_code(selected, code)
        user_info = await fetch_profile(selected, tokens)
    except Exception as exc:
        from unimonitor.exceptions import AuthenticationError

        if isinstance(exc, AuthenticationError):
            logger.error("oidc_failed", provider=selected.name, error=str(exc))
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        logger.error("oidc_failed", provider=selected.name, error=str(exc))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to complete sign-in") from exc

    return await complete_sign_in(user_info, state_data.get("redirect", "/"))
