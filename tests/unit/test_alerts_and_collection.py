"""Tests for alert policies, the audit hash chain, search and collection APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest


def _finding(tenant_id: str, **overrides):
    from unimonitor.db.models.finding import Finding

    values = {
        "tenant_id": tenant_id,
        "external_control_id": "CTRL-ENT-001",
        "title": "Require MFA for all users",
        "description": "mfa",
        "severity": "critical",
        "state": "not_implemented",
        "category": "identity",
        "service": "entra_id",
        "risk_score": 10,
    }
    values.update(overrides)
    return Finding(**values)


@pytest.mark.asyncio
async def test_alert_policy_triggers_and_workflow(client, auth_headers, db_session, tenant) -> None:
    db_session.add(_finding(tenant.id))
    await db_session.flush()

    created = await client.post(
        "/api/v1/alerts/policies/from-template",
        headers=auth_headers,
        json={"template_key": "critical-findings"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["metric"] == "critical_findings"

    evaluated = await client.post("/api/v1/alerts/evaluate", headers=auth_headers)
    assert evaluated.status_code == 200, evaluated.text
    assert evaluated.json()["raised"] == 1

    listing = await client.get("/api/v1/alerts", headers=auth_headers, params={"status": "open"})
    assert listing.status_code == 200, listing.text
    alert = listing.json()["items"][0]
    assert alert["metric_value"] >= 1

    acked = await client.post(
        f"/api/v1/alerts/{alert['id']}/status",
        headers=auth_headers,
        json={"status": "acknowledged", "note": "Investigating"},
    )
    assert acked.status_code == 200, acked.text
    assert acked.json()["status"] == "acknowledged"
    assert acked.json()["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_policy_metric_counts_only_unresolved_findings(db_session, tenant) -> None:
    from unimonitor.alerts.engine import metric_value

    db_session.add_all(
        [
            _finding(tenant.id, external_control_id="C-1", severity="critical"),
            _finding(tenant.id, external_control_id="C-2", severity="critical", state="implemented"),
            _finding(tenant.id, external_control_id="C-3", severity="high", is_suppressed=True),
        ]
    )
    await db_session.flush()

    assert await metric_value(db_session, tenant.id, "critical_findings", 24) == 1
    assert await metric_value(db_session, tenant.id, "high_findings", 24) == 0


@pytest.mark.asyncio
async def test_audit_chain_detects_tampering(db_session) -> None:
    from sqlalchemy import select

    from unimonitor.core.audit import verify_chain, write_audit
    from unimonitor.db.models.audit_log import AuditLog

    await write_audit(db_session, action="test.one", payload={"n": 1})
    second = await write_audit(db_session, action="test.two", payload={"n": 2})

    result = await verify_chain(db_session)
    assert result["valid"] is True
    assert result["checked"] >= 2

    second.payload = '{"n": 99}'
    await db_session.flush()

    row = (await db_session.execute(select(AuditLog).where(AuditLog.id == second.id))).scalar_one()
    tampered = await verify_chain(db_session)
    assert tampered["valid"] is False
    assert tampered["broken_at"] == row.id


@pytest.mark.asyncio
async def test_global_search_finds_findings_alerts_and_controls(client, auth_headers, db_session, tenant) -> None:
    db_session.add(_finding(tenant.id))
    await db_session.flush()

    response = await client.get("/api/v1/search", headers=auth_headers, params={"q": "MFA"})
    assert response.status_code == 200, response.text
    kinds = {hit["kind"] for hit in response.json()["hits"]}
    assert "finding" in kinds


@pytest.mark.asyncio
async def test_collection_schedule_reports_interval(client, auth_headers, tenant) -> None:
    response = await client.get("/api/v1/monitoring/schedule", headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["interval_minutes"] >= 1
    assert payload["collectors"] > 0
    assert "next_run" in payload


@pytest.mark.asyncio
async def test_licensing_maps_seats(client, auth_headers, tenant, monkeypatch) -> None:
    from unimonitor.api.v1 import monitoring

    monkeypatch.setattr(
        monitoring,
        "_graph_json",
        AsyncMock(
            return_value={
                "value": [
                    {
                        "skuId": "sku-1",
                        "skuPartNumber": "ENTERPRISEPACK",
                        "capabilityStatus": "Enabled",
                        "consumedUnits": 10,
                        "prepaidUnits": {"enabled": 25},
                    },
                    {
                        "skuId": "sku-2",
                        "skuPartNumber": "IDLE_SKU",
                        "capabilityStatus": "Enabled",
                        "consumedUnits": 0,
                        "prepaidUnits": {"enabled": 5},
                    },
                ]
            }
        ),
    )

    response = await client.get("/api/v1/monitoring/licensing", headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total_seats"] == 30
    assert payload["available_seats"] == 20
    assert payload["unused_skus"] == 1
    statuses = {sku["sku_part_number"]: sku["status"] for sku in payload["skus"]}
    assert statuses["IDLE_SKU"] == "unused"


@pytest.mark.asyncio
async def test_service_health_reports_issues(client, auth_headers, tenant, monkeypatch) -> None:
    from unimonitor.api.v1 import monitoring

    async def fake_graph(_db, _tenant, endpoint, permission=None):
        if "healthOverviews" in endpoint:
            return {"value": [{"service": "Exchange Online", "status": "serviceDegradation"}]}
        return {
            "value": [
                {
                    "id": "EX1",
                    "title": "Mail delay",
                    "severity": "advisory",
                    "status": "serviceDegradation",
                    "isResolved": False,
                    "service": "Exchange Online",
                }
            ]
        }

    monkeypatch.setattr(monitoring, "_graph_json", fake_graph)

    response = await client.get("/api/v1/monitoring/service-health", headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["degraded_services"] == 1
    assert payload["active_issues"][0]["title"] == "Mail delay"


@pytest.mark.asyncio
async def test_single_collector_rejects_unknown_name(client, auth_headers, tenant) -> None:
    response = await client.post("/api/v1/monitoring/collectors/not-a-collector/run", headers=auth_headers)
    assert response.status_code == 400


def test_audit_entry_digest_is_stable() -> None:
    from unimonitor.core.audit import entry_digest

    created = datetime(2026, 1, 1, tzinfo=UTC)
    kwargs = {
        "prev_hash": "0" * 64,
        "tenant_id": "t1",
        "user_id": "u1",
        "action": "finding.triaged",
        "resource_type": "finding",
        "resource_id": "f1",
        "payload": '{"a": 1}',
        "created_at": created,
    }
    first = entry_digest(**kwargs)
    assert entry_digest(**kwargs) == first
    assert entry_digest(**{**kwargs, "action": "other"}) != entry_digest(**kwargs)
