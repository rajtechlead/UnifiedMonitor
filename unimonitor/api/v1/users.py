"""User management — roles and access, managed in the app like Vigil365.

Identity comes from Microsoft sign-in (or a local password); the role is stored
here, so role management needs no Entra app roles or Graph write permission.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.auth.dependencies import require_role
from unimonitor.core.audit import write_audit
from unimonitor.db.models.user import AppUser
from unimonitor.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter()

USER_NOT_FOUND = "User not found"

Role = Literal["admin", "analyst", "auditor", "viewer"]


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    has_password: bool = False
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: str
    full_name: str = ""
    role: Role = "viewer"
    password: str | None = None


class RoleUpdate(BaseModel):
    role: Role


class ActiveUpdate(BaseModel):
    is_active: bool


def _response(user: AppUser) -> UserResponse:
    item = UserResponse.model_validate(user)
    item.has_password = bool(user.hashed_password)
    return item


async def _active_admins(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(AppUser).where(AppUser.role == "admin", AppUser.is_active.is_(True))) or 0


@router.get("")
async def list_users(
    current_user: Annotated[Any, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserResponse]:
    """Every user of this install, oldest first."""
    users = (await db.execute(select(AppUser).order_by(AppUser.created_at))).scalars().all()
    return [_response(user) for user in users]


@router.post("", status_code=status.HTTP_201_CREATED, responses={400: {"description": "Bad request"}, 409: {"description": "Conflict"}})
async def create_user(
    body: UserCreate,
    current_user: Annotated[Any, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Add a user. Without a password they sign in with Microsoft."""
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    exists = (await db.execute(select(AppUser).where(AppUser.email == email))).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail=f"{email} already exists.")

    hashed_password = None
    if body.password:
        if len(body.password) < 12:
            raise HTTPException(status_code=400, detail="Use a password of at least 12 characters.")
        import bcrypt

        hashed_password = bcrypt.hashpw(body.password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")

    user = AppUser(
        tenant_id=current_user.tenant_id,
        email=email,
        full_name=body.full_name.strip(),
        role=body.role,
        is_active=True,
        hashed_password=hashed_password,
    )
    db.add(user)
    await db.flush()
    await write_audit(
        db,
        action="user.created",
        tenant_id=user.tenant_id,
        user_id=current_user.id,
        resource_type="user",
        resource_id=user.id,
        payload={"email": user.email, "role": user.role},
    )
    await db.commit()
    logger.info("user_created", email=user.email, role=user.role, by=current_user.email)
    return _response(user)


@router.put("/{user_id}/role", responses={404: {"description": "Not found"}, 409: {"description": "Conflict"}})
async def update_role(
    user_id: str,
    body: RoleUpdate,
    current_user: Annotated[Any, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Change a user's role, refusing to remove the last active administrator."""
    user = await db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)
    if user.role == "admin" and body.role != "admin" and await _active_admins(db) <= 1:
        raise HTTPException(status_code=409, detail="The last active administrator cannot be demoted.")

    user.role = body.role
    await db.flush()
    await write_audit(
        db,
        action="user.role_changed",
        tenant_id=user.tenant_id,
        user_id=current_user.id,
        resource_type="user",
        resource_id=user.id,
        payload={"email": user.email, "role": user.role},
    )
    await db.commit()
    return _response(user)


@router.put("/{user_id}", responses={404: {"description": "Not found"}, 409: {"description": "Conflict"}})
async def update_user(
    user_id: str,
    body: ActiveUpdate,
    current_user: Annotated[Any, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Enable or disable sign-in for a user."""
    user = await db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)
    if user.id == current_user.id and not body.is_active:
        raise HTTPException(status_code=409, detail="You cannot disable your own account.")
    if user.role == "admin" and not body.is_active and await _active_admins(db) <= 1:
        raise HTTPException(status_code=409, detail="The last active administrator cannot be disabled.")

    user.is_active = body.is_active
    await db.flush()
    await write_audit(
        db,
        action="user.updated",
        tenant_id=user.tenant_id,
        user_id=current_user.id,
        resource_type="user",
        resource_id=user.id,
        payload={"email": user.email, "is_active": user.is_active},
    )
    await db.commit()
    return _response(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, responses={404: {"description": "Not found"}, 409: {"description": "Conflict"}})
async def delete_user(
    user_id: str,
    current_user: Annotated[Any, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Remove access. The person's Microsoft 365 account is untouched."""
    user = await db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)
    if user.id == current_user.id:
        raise HTTPException(status_code=409, detail="You cannot remove your own account.")
    if user.role == "admin" and await _active_admins(db) <= 1:
        raise HTTPException(status_code=409, detail="The last active administrator cannot be removed.")

    await write_audit(
        db,
        action="user.deleted",
        tenant_id=user.tenant_id,
        user_id=current_user.id,
        resource_type="user",
        resource_id=user.id,
        payload={"email": user.email},
    )
    await db.delete(user)
    await db.commit()
