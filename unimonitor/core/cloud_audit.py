"""Recent audit activity from every connected cloud, for the Audit page.

Each platform is read with the credentials the setup wizard already stored. A
platform that fails is logged and skipped: one unreachable cloud must not blank
the audit trail for the others.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

from unimonitor.core.logging import get_logger

logger = get_logger(__name__)

PER_SOURCE_TIMEOUT_SECONDS = 10
MAX_EVENTS = 100


def _event(source: str, action: str, actor: str | None, target: str | None, at: str | None) -> dict[str, Any]:
    return {
        "id": f"{source}:{at}:{action}:{actor}",
        "source": source,
        "action": action or "unknown",
        "actor": actor or "system",
        "target": target or "",
        "created_at": at or datetime.now(UTC).isoformat(),
    }


async def cloud_events(db: Any, tenant_id: str | None = None, limit: int = MAX_EVENTS) -> list[dict[str, Any]]:
    """Audit events from Microsoft 365, AWS, GCP and Google Workspace."""
    from unimonitor.onboarding.service import connected_providers

    providers = await connected_providers(db, tenant_id)
    readers = {
        "microsoft": _microsoft,
        "aws": _aws,
        "gcp": _gcp,
        "google_workspace": _workspace,
    }
    jobs = [asyncio.wait_for(reader(db, limit), PER_SOURCE_TIMEOUT_SECONDS) for name, reader in readers.items() if name in providers]
    if not jobs:
        return []

    results = await asyncio.gather(*jobs, return_exceptions=True)
    events: list[dict[str, Any]] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.warning("Cloud audit source unavailable", error=str(result)[:200])
            continue
        events.extend(result)
    events.sort(key=lambda event: str(event["created_at"]), reverse=True)
    return events[:limit]


async def _microsoft(db: Any, limit: int) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from unimonitor.db.models.tenant import Tenant
    from unimonitor.graph.client import GraphClient

    tenant = (await db.execute(select(Tenant).where(Tenant.is_active).limit(1))).scalar_one_or_none()
    if tenant is None:
        return []
    async with GraphClient(
        tenant_id=tenant.entra_tenant_id,
        client_id=tenant.client_id,
        client_secret=tenant.client_secret,
    ) as client:
        response = await client.get(f"/auditLogs/directoryAudits?$top={limit}")
    if not response.success:
        raise RuntimeError(response.error_message or "Microsoft audit log request failed")

    rows = []
    for row in (response.data or {}).get("value", []) or []:
        initiated = (row.get("initiatedBy") or {}).get("user") or {}
        targets = row.get("targetResources") or [{}]
        rows.append(
            _event(
                "Microsoft 365",
                str(row.get("activityDisplayName") or "Directory audit"),
                initiated.get("userPrincipalName"),
                str((targets[0] or {}).get("displayName") or ""),
                row.get("activityDateTime"),
            )
        )
    return rows


async def _aws(db: Any, limit: int) -> list[dict[str, Any]]:
    import boto3

    from unimonitor.onboarding.service import aws_credentials_for

    credentials = await aws_credentials_for(db)
    if not credentials:
        return []

    def fetch() -> list[dict[str, Any]]:
        client = boto3.Session(**credentials).client("cloudtrail")
        return client.lookup_events(MaxResults=min(limit, 50)).get("Events", [])

    rows = await asyncio.to_thread(fetch)
    events = []
    for row in rows:
        resources = row.get("Resources") or [{}]
        events.append(
            _event(
                "AWS",
                str(row.get("EventName") or "CloudTrail event"),
                row.get("Username"),
                str((resources[0] or {}).get("ResourceName") or ""),
                row["EventTime"].isoformat() if row.get("EventTime") else None,
            )
        )
    return events


async def _gcp(db: Any, limit: int) -> list[dict[str, Any]]:
    from unimonitor.onboarding.service import google_token_for

    token = await google_token_for("gcp", db)
    if not token:
        return []
    body = {
        "filter": 'logName:"cloudaudit.googleapis.com"',
        "pageSize": min(limit, 100),
        "orderBy": "timestamp desc",
    }
    async with httpx.AsyncClient(timeout=PER_SOURCE_TIMEOUT_SECONDS) as client:
        response = await client.post(
            "https://logging.googleapis.com/v2/entries:list",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        entries = response.json().get("entries", [])

    events = []
    for entry in entries:
        payload = entry.get("protoPayload") or {}
        events.append(
            _event(
                "GCP",
                str(payload.get("methodName") or "Audit log entry"),
                (payload.get("authenticationInfo") or {}).get("principalEmail"),
                str((entry.get("resource") or {}).get("type") or ""),
                entry.get("timestamp"),
            )
        )
    return events


async def _workspace(db: Any, limit: int) -> list[dict[str, Any]]:
    from unimonitor.onboarding.service import google_token_for

    token = await google_token_for("google_workspace", db)
    if not token:
        return []
    async with httpx.AsyncClient(timeout=PER_SOURCE_TIMEOUT_SECONDS) as client:
        response = await client.get(
            f"https://admin.googleapis.com/admin/reports/v1/activity/users/all/applications/login?maxResults={min(limit, 100)}",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        items = response.json().get("items", [])

    events = []
    for item in items:
        names = [str((event or {}).get("name") or "") for event in item.get("events", [])]
        events.append(
            _event(
                "Google Workspace",
                ", ".join(name for name in names if name) or "Login activity",
                (item.get("actor") or {}).get("email"),
                "",
                (item.get("id") or {}).get("time"),
            )
        )
    return events
