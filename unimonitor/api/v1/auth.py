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
    token_type: str = "bearer"
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


@router.post("/login", response_model=TokenResponse)
async def login_local(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Local username/password login (OAuth2 password flow).

    Authenticates against the local `app_users` table using bcrypt.
    For Entra ID SSO, use GET /login to start the OAuth2 redirect flow.
    """
    import bcrypt as _bcrypt
    from sqlalchemy import select

    from unimonitor.db.models.user import AppUser

    settings = get_settings()

    result = await db.execute(
        select(AppUser).where(AppUser.email == form_data.username)
    )
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


@router.get("/login")
async def login(
    request: Request,
    redirect_after: str = Query(default="/", alias="redirect"),
) -> RedirectResponse:
    """Redirect to Entra ID OAuth2 authorization endpoint."""
    get_settings()
    state = secrets.token_urlsafe(32)

    # Store state + redirect destination in cache (5 min TTL)
    await cache_set(f"oauth_state:{state}", {"redirect": redirect_after}, ttl=300)

    authorize_url = build_authorize_url(state=state)
    logger.info("oauth_login_initiated", state=state[:8])
    return RedirectResponse(url=authorize_url, status_code=status.HTTP_302_FOUND)


@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
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

    settings = get_settings()
    try:
        token_data = await exchange_code_for_token(code=code)
    except Exception as exc:
        logger.error("token_exchange_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange authorization code for token",
        )

    # Fetch user info from Graph /me
    try:
        user_info = await get_entra_user_info(access_token=token_data["access_token"])
    except Exception as exc:
        logger.error("user_info_fetch_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve user information",
        )

    # Upsert user in DB
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.repositories.tenant_repo import UserRepository

    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        db_user = await user_repo.upsert_from_entra(user_info)

    # Issue our own JWTs
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

    # Redirect to frontend with tokens in URL fragment or return JSON
    redirect_to = state_data.get("redirect", "/")
    if redirect_to.startswith("/") and not redirect_to.startswith("//"):
        frontend_url = settings.UNIMONITOR_CORS_ORIGINS[0] if settings.UNIMONITOR_CORS_ORIGINS else ""
        if frontend_url:
            return RedirectResponse(
                url=f"{frontend_url}{redirect_to}#access_token={access_token}&refresh_token={refresh_token}",
                status_code=status.HTTP_302_FOUND,
            )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a refresh token for a new access token."""
    settings = get_settings()
    try:
        payload = decode_refresh_token(body.refresh_token)
    except Exception:
        raise HTTPException(
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
        except Exception:
            pass
    logger.info("user_logged_out", user_id=current_user.id)


@router.get("/me", response_model=UserProfile)
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
