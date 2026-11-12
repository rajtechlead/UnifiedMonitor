"""FastAPI authentication dependencies."""

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.jwt import validate_access_token
from unimonitor.db import get_async_session
from unimonitor.db.models.user import AppUser, UserRole
from unimonitor.exceptions import AuthenticationError, AuthorisationError, NotFoundError

http_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    session: AsyncSession = Depends(get_async_session),
) -> AppUser:
    """Extract and validate the current authenticated user from the JWT."""
    if not credentials:
        raise AuthenticationError("Missing authorisation header.")

    payload = validate_access_token(credentials.credentials)
    user_id: str = payload.get("sub", "")
    if not user_id:
        raise AuthenticationError("Invalid token payload.")

    user = await session.get(AppUser, user_id)
    if user is None:
        raise AuthenticationError("User not found.")
    if not user.is_active:
        raise AuthenticationError("User account is disabled.")

    return user


async def get_current_active_user(
    current_user: AppUser = Depends(get_current_user),
) -> AppUser:
    return current_user


def require_role(*roles: UserRole):
    """Dependency factory: require the user to have one of the given roles."""
    async def _check(current_user: AppUser = Depends(get_current_user)) -> AppUser:
        if not current_user.has_role(*roles):
            raise AuthorisationError(
                f"Role '{current_user.role}' is not authorised for this action."
            )
        return current_user
    return _check


def require_admin():
    return require_role(UserRole.ADMIN)


def require_analyst():
    return require_role(
        UserRole.ADMIN, UserRole.SECURITY_ANALYST, UserRole.SOC_ANALYST
    )


def require_compliance():
    return require_role(
        UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.AUDITOR
    )
