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

# A Graph client-credentials token plus the audit query regularly takes longer than
# ten seconds; the old limit timed out and reported the empty string of the timeout.
PER_SOURCE_TIMEOUT_SECONDS = 30
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


async def cloud_events(
    db: Any, tenant_id: str | None = None, limit: int = MAX_EVENTS, failures: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """Audit events from Microsoft 365, AWS, GCP and Google Workspace.

    ``failures`` is filled with ``{source: reason}`` when a connected platform could not
    be read (usually a missing read permission), so the page can say which platform is
    silent instead of implying nothing happened.
    """
    from unimonitor.onboarding.service import connected_providers

    providers = await connected_providers(db, tenant_id)
    readers = {
        "microsoft": _microsoft,
        "aws": _aws,
        "gcp": _gcp,
        "google_workspace": _workspace,
    }
    selected = [(name, reader) for name, reader in readers.items() if name in providers]
    if not selected:
        return []

    results = await asyncio.gather(
        *[asyncio.wait_for(reader(db, limit, tenant_id), PER_SOURCE_TIMEOUT_SECONDS) for _, reader in selected],
        return_exceptions=True,
    )
    events: list[dict[str, Any]] = []
    for (name, _reader), result in zip(selected, results, strict=True):
        if isinstance(result, BaseException):
            if isinstance(result, TimeoutError):
                reason = f"timed out after {PER_SOURCE_TIMEOUT_SECONDS}s"
            else:
                reason = (str(result).strip() or result.__class__.__name__)[:200]
            logger.warning("Cloud audit source unavailable", source=name, error=reason)
            if failures is not None:
                failures[name] = reason
            continue
        events.extend(result)
    events.sort(key=lambda event: str(event["created_at"]), reverse=True)
    return events[:limit]


async def _microsoft(db: Any, limit: int, tenant_id: str | None = None) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from unimonitor.db.models.tenant import Tenant
    from unimonitor.exceptions import GraphPermissionError
    from unimonitor.graph.client import GraphClient
    from unimonitor.onboarding.service import microsoft_app

    stmt = select(Tenant).where(Tenant.is_active)
    if tenant_id:
        stmt = stmt.where(Tenant.id == tenant_id)
    tenant = (await db.execute(stmt.limit(1))).scalar_one_or_none()
    if tenant is None:
        return []
    app = await microsoft_app(db, tenant.id)
    if not app.get("configured"):
        return []
    async with GraphClient(
        tenant_id=app["directory"] or tenant.entra_tenant_id,
        client_id=app["client_id"],
        client_secret=app.get("client_secret") or None,
        certificate_pem=app.get("certificate_pem") or None,
        private_key_pem=app.get("private_key_pem") or None,
    ) as client:
        try:
            response = await client.get(f"/auditLogs/directoryAudits?$top={min(limit, 50)}&$orderby=activityDateTime desc")
        except GraphPermissionError as exc:
            # The exception's own text only names the endpoint; Graph's response body
            # says which permission is missing, so surface that instead of a blank.
            detail = str(getattr(exc, "detail", "") or "").strip()
            raise RuntimeError(f"Graph refused the audit log (403){': ' + detail[:300] if detail else ''}") from exc
    if not response.success:
        raise RuntimeError(response.error_message or "Microsoft audit log request failed")
    if not isinstance(response.data, list):
        raise RuntimeError("Microsoft returned an unexpected audit payload")

    payload: dict[str, Any] = response.data if isinstance(response.data, dict) else {}
    rows = []
    for row in payload.get("value", []) or []:
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


async def _aws(db: Any, limit: int, tenant_id: str | None = None) -> list[dict[str, Any]]:
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


async def _gcp(db: Any, limit: int, tenant_id: str | None = None) -> list[dict[str, Any]]:
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


WORKSPACE_APPLICATIONS = ("login", "admin", "drive", "token", "mobile")


async def _workspace(db: Any, limit: int, tenant_id: str | None = None) -> list[dict[str, Any]]:
    """Workspace audit activity across sign-in, admin, Drive, OAuth token and mobile."""
    from unimonitor.onboarding.service import google_token_for

    token = await google_token_for("google_workspace", db)
    if not token:
        return []

    per_application = max(1, min(limit, 100) // len(WORKSPACE_APPLICATIONS))
    events: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=PER_SOURCE_TIMEOUT_SECONDS) as client:
        for application in WORKSPACE_APPLICATIONS:
            response = await client.get(
                f"https://admin.googleapis.com/admin/reports/v1/activity/users/all/applications/{application}?maxResults={per_application}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code >= 400:
                # One application the reseller/admin has not enabled must not hide the rest.
                logger.warning("Workspace audit application unavailable", application=application, status=response.status_code)
                continue
            for item in response.json().get("items", []) or []:
                names = [str((event or {}).get("name") or "") for event in item.get("events", [])]
                events.append(
                    _event(
                        "Google Workspace",
                        ", ".join(name for name in names if name) or f"{application} activity",
                        (item.get("actor") or {}).get("email"),
                        application,
                        (item.get("id") or {}).get("time"),
                    )
                )
    return events
