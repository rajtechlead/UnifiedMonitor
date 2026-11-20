"""Time-boxed finding exceptions and the SIEM export."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


async def _seed_finding(db_session, tenant, **overrides):
    from unimonitor.db.models.finding import Finding

    finding = Finding(
        tenant_id=tenant.id,
        external_control_id=overrides.pop("external_control_id", "CTRL-ENT-001"),
        title=overrides.pop("title", "Require MFA for All Users"),
        description="seeded for the exception/export tests",
        severity=overrides.pop("severity", "high"),
        state=overrides.pop("state", "not_implemented"),
        category="identity",
        service="entra_id",
        **overrides,
    )
    db_session.add(finding)
    await db_session.flush()
    return finding


@pytest.mark.asyncio
async def test_expired_exception_is_released_on_read(client: AsyncClient, auth_headers: dict, db_session, tenant) -> None:
    finding = await _seed_finding(db_session, tenant)

    suppressed = await client.post(
        f"/api/v1/findings/{finding.id}/suppress",
        json={"reason": "compensating control while the app is retired", "expires_in_days": 1},
        headers=auth_headers,
    )
    assert suppressed.status_code == 200, suppressed.text
    assert suppressed.json()["is_suppressed"] is True
    assert suppressed.json()["suppression_expires_at"]

    # Rewind the expiry: the next read must release it without a background job.
    finding.suppression_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.flush()

    listing = await client.get("/api/v1/findings", params={"tenant_id": tenant.id}, headers=auth_headers)
    assert listing.status_code == 200, listing.text
    row = next(item for item in listing.json()["items"] if item["id"] == finding.id)
    assert row["is_suppressed"] is False
    assert row["suppression_reason"] is None
    assert row["suppression_expires_at"] is None


@pytest.mark.asyncio
async def test_siem_export_contains_open_findings(client: AsyncClient, auth_headers: dict, db_session, tenant) -> None:
    await _seed_finding(db_session, tenant, external_control_id="CTRL-ENT-002", title="Block Legacy Authentication Protocols")
    await _seed_finding(db_session, tenant, external_control_id="CTRL-ENT-003", state="implemented", title="Require compliant device")

    cef = await client.get("/api/v1/findings/export/siem", params={"tenant_id": tenant.id}, headers=auth_headers)
    assert cef.status_code == 200, cef.text
    assert "CEF:0|UniMonitor" in cef.text
    assert "CTRL-ENT-002" in cef.text
    assert "CTRL-ENT-003" not in cef.text

    lines = await client.get(
        "/api/v1/findings/export/siem",
        params={"tenant_id": tenant.id, "format": "json"},
        headers=auth_headers,
    )
    assert lines.status_code == 200, lines.text
    payload = [line for line in lines.text.splitlines() if line]
    assert any(item for item in payload if "CTRL-ENT-002" in item)
    assert all("CTRL-ENT-003" not in item for item in payload)
