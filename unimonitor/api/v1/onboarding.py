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
from unimonitor.onboarding.certificates import ClientCertificate
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
    # Certificate is the default; a client secret stays available for tenants whose
    # policy blocks certificate credentials.
    auth_method: str = "certificate"
    certificate_validity_days: int | None = None


class RotateCertificateRequest(BaseModel):
    validity_days: int | None = None


class GoogleServiceAccountRequest(BaseModel):
    project_id: str = ""
    admin_email: str = ""
    customer_id: str = "my_customer"
    credentials_json: str = ""
    access_token: str = ""
    providers: list[str] = Field(default_factory=list)


def _certificate_payload(certificate: ClientCertificate | None) -> dict[str, Any] | None:
    if certificate is None:
        return None
    return {
        "thumbprint": certificate.thumbprint,
        "not_after": certificate.not_after_iso,
        "files": certificate.files(),
    }


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

        result = await m365.provision_app(
            poll["access_token"],
            display_name=body.display_name,
            auth_method=body.auth_method,
            certificate_validity_days=body.certificate_validity_days,
        )
        tenant = await service.first_tenant(db)
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenant exists yet.")

        config: dict[str, Any] = {
            "client_id": result.client_id,
            "auth_method": result.auth_method,
            "granted_permissions": result.granted,
            "app_object_id": result.app_object_id,
        }
        secrets: dict[str, str] = {}
        if result.auth_method == "certificate" and result.certificate is not None:
            config["certificate_thumbprint"] = result.certificate.thumbprint
            config["certificate_expires_at"] = result.certificate.not_after_iso
            secrets = {
                "certificate_pem": result.certificate.certificate_pem,
                "private_key_pem": result.certificate.private_key_pem,
            }
        else:
            secrets = {"client_secret": result.client_secret}

        # Until the certificate is in Entra the connection is not usable, so it does
        # not count as configured and the wizard cannot finish on it.
        row = await service.upsert_connection(
            db,
            tenant_id=tenant.id,
            provider="microsoft",
            account=result.tenant_id,
            display_name=result.tenant_name or body.display_name,
            config=config,
            secrets=secrets,
            status="connected" if result.certificate_uploaded or result.auth_method == "client_secret" else "pending_certificate_upload",
        )
        return {
            "status": row.status,
            "connection": service.connection_dict(row),
            "granted": result.granted,
            "warnings": result.warnings,
            "auth_method": result.auth_method,
            "certificate": _certificate_payload(result.certificate),
            "certificate_uploaded": result.certificate_uploaded,
            "certificate_error": result.certificate_error,
            "manual_steps": result.manual_steps,
        }
    except m365.M365Error as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/microsoft/verify")
async def microsoft_verify(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_setup_admin),
) -> dict:
    """Re-check the stored Microsoft connection, e.g. after a manual certificate upload."""
    try:
        row = await service.verify_microsoft_connection(db)
    except (m365.M365Error, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "connected", "connection": service.connection_dict(row)}


@router.post("/microsoft/certificate/rotate")
async def microsoft_rotate_certificate(
    body: RotateCertificateRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_setup_admin),
) -> dict:
    """Replace the stored certificate with a freshly generated one."""
    try:
        row = await service.rotate_microsoft_certificate(db, validity_days=(body.validity_days if body else None))
    except (m365.M365Error, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    config = service.connection_dict(row)["config"]
    return {
        "status": "connected",
        "connection": service.connection_dict(row),
        "certificate": {
            "thumbprint": config.get("certificate_thumbprint", ""),
            "not_after": config.get("certificate_expires_at", ""),
        },
    }


@router.post("/connections/google-service-account")
async def connect_google_service_account(
    body: GoogleServiceAccountRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_setup_admin),
) -> dict:
    """Connect Google Cloud and Workspace with one shared service account."""
    try:
        rows = await service.connect_google_service_account(
            db,
            project_id=body.project_id.strip(),
            admin_email=body.admin_email.strip(),
            customer_id=body.customer_id.strip(),
            credentials_json=body.credentials_json.strip(),
            access_token=body.access_token.strip(),
            providers=body.providers,
        )
    except (CloudError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "connected", "connections": [service.connection_dict(row) for row in rows]}


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
