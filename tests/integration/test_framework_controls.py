"""Framework control drill-down: state and evidence per mapped control."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_framework_controls_report_state_and_evidence(client: AsyncClient, auth_headers: dict, db_session, tenant) -> None:
    from unimonitor.db.models.finding import Finding
    from unimonitor.grc.control_loader import ControlLoader

    control = next(item for item in ControlLoader().load_all() if {"iso27001-2022", "iso27001_2022"} & set(item.compliance_mapping))
    db_session.add(
        Finding(
            tenant_id=tenant.id,
            external_control_id=control.id,
            title=control.title,
            description="seeded for the framework drill-down",
            severity="high",
            state="implemented",
            category=control.category,
            service=control.service,
        )
    )
    await db_session.flush()

    response = await client.get("/api/v1/grc/frameworks/iso27001-2022/controls", headers=auth_headers)
    assert response.status_code == 200, response.text
    rows = {row["external_id"]: row for row in response.json()}

    assert rows[control.id]["state"] == "implemented"
    assert rows[control.id]["finding_id"]
    assert "remediation" in rows[control.id]
    # A mapped control with no collection yet is "not_run", never an assumed pass.
    assert any(row["state"] == "not_run" for row in rows.values())


@pytest.mark.asyncio
async def test_unknown_framework_is_404(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get("/api/v1/grc/frameworks/not-a-framework/controls", headers=auth_headers)
    assert response.status_code == 404
