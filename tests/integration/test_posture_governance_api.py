"""Posture API, control-level trends, branding and the scorecard download."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_posture_analysis_without_snapshot_is_404(client: AsyncClient, auth_headers: dict, monkeypatch) -> None:
    monkeypatch.setattr("unimonitor.api.v1.posture.load_snapshot", lambda: {})
    # The automatic inventory is the other source; this test is about neither existing.
    monkeypatch.setattr("unimonitor.posture.assemble.load_inventory", lambda tenant_id="": None)
    response = await client.get("/api/v1/posture/analysis", headers=auth_headers)
    assert response.status_code == 404
    assert "UNIMONITOR_POSTURE_SNAPSHOT" in response.json()["detail"]


async def test_posture_analysis_reads_only_the_callers_inventory(client: AsyncClient, tenant, auth_headers: dict, monkeypatch, tmp_path) -> None:
    from unimonitor.config import get_settings
    from unimonitor.posture.assemble import write_inventory

    monkeypatch.setattr(get_settings(), "POSTURE_AUTO_INVENTORY_PATH", str(tmp_path))
    monkeypatch.setattr(get_settings(), "POSTURE_AUTO_INVENTORY", True)
    monkeypatch.setattr("unimonitor.api.v1.posture.load_snapshot", lambda: {})
    write_inventory({"resources": [{"type": "storage", "provider": "aws", "id": "own-1"}], "edges": []}, tenant.id)
    write_inventory(
        {
            "resources": [
                {"type": "storage", "provider": "aws", "id": "other-1"},
                {"type": "storage", "provider": "aws", "id": "other-2"},
            ],
            "edges": [],
        },
        "other-tenant-id-000000000002",
    )

    response = await client.get("/api/v1/posture/analysis", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "collected"
    assert body["resources"] == 1, "another tenant's inventory must not be analysed"


async def test_posture_analysis_does_not_fall_back_to_another_tenants_inventory(
    client: AsyncClient, auth_headers: dict, monkeypatch, tmp_path
) -> None:
    from unimonitor.config import get_settings
    from unimonitor.posture.assemble import write_inventory

    monkeypatch.setattr(get_settings(), "POSTURE_AUTO_INVENTORY_PATH", str(tmp_path))
    monkeypatch.setattr(get_settings(), "POSTURE_AUTO_INVENTORY", True)
    monkeypatch.setattr("unimonitor.api.v1.posture.load_snapshot", lambda: {})
    write_inventory(
        {"resources": [{"type": "storage", "provider": "aws", "id": "other-1"}], "edges": []},
        "other-tenant-id-000000000002",
    )

    response = await client.get("/api/v1/posture/analysis", headers=auth_headers)
    assert response.status_code == 404
    assert "this tenant" in response.json()["detail"]


async def test_posture_analyze_accepts_a_posted_inventory(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/api/v1/posture/analyze",
        headers=auth_headers,
        json={
            "platform": "aws",
            "snapshot": {"s3_buckets": [{"name": "bucket-a", "public": True, "contains_pii": True}]},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["total"] > 0
    assert body["benchmarks"][0]["platform"] == "aws"
    assert body["engines"]["dspm"]["findings"]


async def test_posture_rejects_unknown_platform_shape(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/api/v1/posture/analyze",
        headers=auth_headers,
        json={"platform": 7, "snapshot": {}},
    )
    assert response.status_code == 400


async def test_control_trend_series_from_snapshots(client: AsyncClient, auth_headers: dict, db_session, tenant) -> None:
    from unimonitor.db.models.control_snapshot import ControlSnapshot

    db_session.add_all(
        [
            ControlSnapshot(
                tenant_id=tenant.id,
                control_id="CTRL-TREND",
                external_control_id="TREND-1",
                severity="high",
                state=state,
            )
            for state in ("not_implemented", "implemented")
        ]
    )
    await db_session.flush()

    listing = await client.get("/api/v1/grc/controls/trend", params={"tenant_id": tenant.id}, headers=auth_headers)
    assert listing.status_code == 200, listing.text
    item = next(row for row in listing.json()["items"] if row["control_id"] == "CTRL-TREND")
    assert item["observations"] == 2
    assert item["transitions"] == 1
    assert item["current_state"] == "implemented"

    single = await client.get("/api/v1/grc/controls/CTRL-TREND/trend", params={"tenant_id": tenant.id}, headers=auth_headers)
    assert single.status_code == 200
    assert single.json()["control_id"] == "CTRL-TREND"


async def test_control_trend_missing_control_is_404(client: AsyncClient, auth_headers: dict, tenant) -> None:
    response = await client.get(
        f"/api/v1/grc/controls/does-not-exist/trend?tenant_id={tenant.id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_branding_defaults_then_updates(client: AsyncClient, auth_headers: dict, tenant) -> None:
    default = await client.get("/api/v1/settings/branding", headers=auth_headers)
    assert default.status_code == 200
    assert default.json()["portal_name"] == "UniMonitor"

    update = await client.put(
        "/api/v1/settings/branding",
        headers=auth_headers,
        json={
            "portal_name": "Acme SOC",
            "accent_colour": "#112233",
            "logo_url": "/static/logo.svg",
            "support_email": "soc@acme.test",
        },
    )
    assert update.status_code == 200, update.text

    read_back = await client.get("/api/v1/settings/branding", headers=auth_headers)
    assert read_back.json()["portal_name"] == "Acme SOC"
    assert read_back.json()["accent_colour"] == "#112233"


@pytest.mark.parametrize(
    "payload",
    [
        {"portal_name": "x", "accent_colour": "#112233", "logo_url": "javascript:alert(1)"},
        {"portal_name": "x", "accent_colour": "blue"},
        {"portal_name": "x", "accent_colour": "#112233", "support_email": "not an email"},
    ],
)
async def test_branding_rejects_unsafe_values(client: AsyncClient, auth_headers: dict, payload: dict) -> None:
    response = await client.put("/api/v1/settings/branding", headers=auth_headers, json=payload)
    assert response.status_code == 422


async def test_scorecard_csv_download(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get("/api/v1/reports/scorecard", params={"fmt": "csv"}, headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in response.headers["content-disposition"]
    assert "external_control_id" in response.text


async def test_scorecard_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/reports/scorecard", params={"fmt": "csv"})
    assert response.status_code == 401


async def test_control_snapshot_retention_prunes_only_past_the_window(db_session, tenant) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from unimonitor.db.models.control_snapshot import ControlSnapshot
    from unimonitor.db.models.tenant import Tenant
    from unimonitor.grc.control_trends import prune_control_snapshots

    other = Tenant(tenant_id="other-entra-tenant", name="other")
    db_session.add(other)
    await db_session.flush()

    now = datetime.now(UTC)
    db_session.add_all(
        [
            ControlSnapshot(tenant_id=tenant.id, control_id="OLD", state="implemented", checked_at=now - timedelta(days=60)),
            ControlSnapshot(tenant_id=tenant.id, control_id="NEW", state="implemented", checked_at=now - timedelta(days=1)),
            ControlSnapshot(tenant_id=other.id, control_id="OTHER-OLD", state="implemented", checked_at=now - timedelta(days=60)),
        ]
    )
    await db_session.flush()

    removed = await prune_control_snapshots(db_session, tenant.id, 30)
    await db_session.flush()

    remaining = set(
        (await db_session.execute(select(ControlSnapshot.control_id).where(ControlSnapshot.tenant_id.in_([tenant.id, other.id])))).scalars()
    )
    assert removed == 1
    assert remaining == {"NEW", "OTHER-OLD"}, "the other tenant's history must not be pruned"


async def test_control_snapshot_retention_zero_keeps_everything(db_session, tenant) -> None:
    from datetime import UTC, datetime, timedelta

    from unimonitor.db.models.control_snapshot import ControlSnapshot
    from unimonitor.grc.control_trends import prune_control_snapshots

    db_session.add(
        ControlSnapshot(tenant_id=tenant.id, control_id="ANCIENT", state="implemented", checked_at=datetime.now(UTC) - timedelta(days=3650))
    )
    await db_session.flush()

    assert await prune_control_snapshots(db_session, tenant.id, 0) == 0
