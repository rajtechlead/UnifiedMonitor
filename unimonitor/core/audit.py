"""Tamper-evident audit writes.

Each entry hashes the previous entry's hash together with its own content, so
modifying or deleting an old row breaks the chain from that point on. The chain
is global (not per tenant) so one writer per row is enough; callers pass the
tenant they acted on.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.db.models.audit_log import AuditLog

GENESIS_HASH = "0" * 64


def _canonical_time(value: datetime) -> str:
    """UTC ISO timestamp; SQLite returns naive datetimes after a round-trip."""
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC).isoformat()


def entry_digest(
    *,
    prev_hash: str,
    tenant_id: str | None,
    user_id: str | None,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    payload: str | None,
    created_at: datetime,
) -> str:
    """Stable hash of one entry, including the previous row's hash."""
    canonical = json.dumps(
        {
            "prev": prev_hash,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "payload": payload,
            "created_at": _canonical_time(created_at),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def write_audit(
    db: AsyncSession,
    *,
    action: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    payload: dict[str, Any] | str | None = None,
) -> AuditLog:
    """Append one audit entry and link it to the previous hash."""
    previous = (await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1))).scalar_one_or_none()
    prev_hash = (previous.entry_hash if previous else None) or GENESIS_HASH

    if isinstance(payload, dict):
        payload_text: str | None = json.dumps(payload, sort_keys=True, default=str)
    else:
        payload_text = payload
    created_at = datetime.now(UTC)

    entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload_text,
        prev_hash=prev_hash,
        created_at=created_at,
    )
    entry.entry_hash = entry_digest(
        prev_hash=prev_hash,
        tenant_id=entry.tenant_id,
        user_id=entry.user_id,
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        payload=entry.payload,
        created_at=created_at,
    )
    db.add(entry)
    await db.flush()
    return entry


async def verify_chain(db: AsyncSession, limit: int | None = None) -> dict[str, Any]:
    """Recompute the chain and report the first break, if any.

    Rows written before the chain existed have no ``entry_hash``; they are
    counted as legacy and skipped rather than reported as tampering.
    """
    stmt = select(AuditLog).order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
    if limit:
        stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    checked = 0
    legacy = 0
    expected_prev: str | None = None
    for row in rows:
        if not row.entry_hash:
            legacy += 1
            expected_prev = None  # next hashed row found its predecessor by its own prev_hash
            continue
        recomputed = entry_digest(
            prev_hash=row.prev_hash or GENESIS_HASH,
            tenant_id=row.tenant_id,
            user_id=row.user_id,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            payload=row.payload,
            created_at=row.created_at,
        )
        if recomputed != row.entry_hash:
            return {
                "valid": False,
                "checked": checked,
                "legacy": legacy,
                "broken_at": row.id,
                "broken_action": row.action,
                "reason": "entry hash does not match its content",
            }
        if expected_prev is not None and row.prev_hash != expected_prev:
            return {
                "valid": False,
                "checked": checked,
                "legacy": legacy,
                "broken_at": row.id,
                "broken_action": row.action,
                "reason": "previous hash does not match the preceding entry",
            }
        expected_prev = row.entry_hash
        checked += 1

    return {"valid": True, "checked": checked, "legacy": legacy, "broken_at": None, "reason": None}
