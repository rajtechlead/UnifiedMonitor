"""First-run setup API: admin bootstrap, platform selection and connection.

Creating the first administrator closes the unauthenticated window, so a fresh
install cannot be claimed by whoever reaches the port first. After that, only an
admin token can connect, change or remove a platform.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.jwt import create_access_token, create_refresh_token, validate_access_token
from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger
from unimonitor.db.models.user import AppUser
from unimonitor.db.session import get_db
from unimonitor.onboarding import m365, service
from unimonitor.onboarding.clouds import CloudError

logger = get_logger(__name__)
router = APIRouter()

http_bearer = HTTPBearer(auto_error=False)


async def require_setup_admin(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> None:
    """Allow the request while no administrator exists; require an admin token after."""
    if not await service.has_admin(db):
        return
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in as an administrator to change connections.",
        )
    payload = validate_access_token(credentials.credentials)
    user = await db.get(AppUser, payload.get("sub", ""))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")


class FirstAdmin(BaseModel):
    email: str
    password: str = Field(min_length=12)
    organisation: str = ""


class CompleteRequest(BaseModel):
    device_code: str
    display_name: str = "UniMonitor"


@router.get("/status")
async def setup_status(db: AsyncSession = Depends(get_db)) -> dict:
    """Setup progress: drives the first-run redirect and the connection list."""
    return await service.get_status(db)


@router.post("/admin")
async def create_admin(body: FirstAdmin, db: AsyncSession = Depends(get_db)) -> dict:
    """Create the first local administrator and return a session token."""
    if await service.has_admin(db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An administrator already exists.")
    try:
        user = await service.create_first_admin(db, body.email, body.password, body.organisation)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    settings = get_settings()
    return {
        "access_token": create_access_token(subject=user.id, tenant_id=user.tenant_id, role=user.role),
        "refresh_token": create_refresh_token(subject=user.id, tenant_id=user.tenant_id),
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {"email": user.email, "role": user.role},
    }


@router.post("/microsoft/device-code")
async def microsoft_device_code(_: None = Depends(require_setup_admin)) -> dict:
    """Start the one-click Microsoft 365 connection."""
    try:
        code = await m365.start_device_flow()
    except m365.M365Error as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {
        "device_code": code.device_code,
        "user_code": code.user_code,
        "verification_uri": code.verification_uri,
        "expires_in": code.expires_in,
        "interval": code.interval,
        "message": code.message,
    }


@router.post("/microsoft/complete")
async def microsoft_complete(
    body: CompleteRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_setup_admin),
) -> dict:
    """Poll the device-code sign-in once; on success create the app and store it."""
    try:
        poll = await m365.poll_device_flow(body.device_code)
        if poll["status"] != "ok":
            return {"status": poll["status"]}

        result = await m365.provision_app(poll["access_token"], display_name=body.display_name)
        tenant = await service.first_tenant(db)
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenant exists yet.")
        row = await service.upsert_connection(
            db,
            tenant_id=tenant.id,
            provider="microsoft",
            account=result.tenant_id,
            display_name=result.tenant_name or body.display_name,
            config={"client_id": result.client_id, "granted_permissions": result.granted},
            secrets={"client_secret": result.client_secret},
        )
        return {
            "status": "connected",
            "connection": service.connection_dict(row),
            "granted": result.granted,
            "warnings": result.warnings,
        }
    except m365.M365Error as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/connections/{provider}")
async def connect(
    provider: str,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_setup_admin),
) -> dict:
    """Validate and store one platform's credentials."""
    try:
        row = await service.connect_platform(db, provider, payload)
    except (CloudError, m365.M365Error, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "connected", "connection": service.connection_dict(row)}


@router.delete("/connections/{provider}")
async def remove_connection(
    provider: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_setup_admin),
) -> dict:
    if not await service.delete_connection(db, provider):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No {provider} connection.")
    return {"status": "disconnected", "provider": provider}
