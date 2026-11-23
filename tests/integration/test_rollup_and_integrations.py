"""Requirement-level CPCSC, remediation SLA, MSP rollup and outbound connectors."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


def _finding(tenant_id: str, control: str, **overrides) -> object:
    from unimonitor.db.models.finding import Finding

    data = {
        "tenant_id": tenant_id,
        "external_control_id": control,
        "title": f"Seed finding for {control}",
        "description": "seeded",
        "severity": "high",
        "state": "not_implemented",
        "category": "Identity",
        "service": "entra_id",
    }
    data.update(overrides)
    return Finding(**data)


@pytest.mark.asyncio
async def test_cpcsc_requirement_catalogue_covers_all_98(client: AsyncClient, auth_headers: dict) -> None:
    from unimonitor.grc.framework_mappings import CPCSC_LEVEL1, cpcsc_requirements

    responses = await client.get("/api/v1/grc/frameworks/cpcsc/requirements", headers=auth_headers)
    assert responses.status_code == 200, responses.text
    body = responses.json()

    assert body["requirement_count"] == 98
    assert body["level1_count"] == 13
    ids = {row["id"] for row in body["rows"]}
    assert len(ids) == 98
    # Canada's addition and the numbering gaps that come with the NIST Rev 3 base.
    assert "03.14.09" in ids
    assert "03.01.15" not in ids
    assert all(row["controls_total"] > 0 for row in body["rows"])
    assert {row["id"] for row in body["rows"] if row["level"] == 1} == set(CPCSC_LEVEL1)
    assert len(cpcsc_requirements()) == 98

    # Every framework now has a requirement view; a derived one labels itself so it
    # is never mistaken for an official crosswalk.
    other = await client.get("/api/v1/grc/frameworks/iso27001-2022/requirements", headers=auth_headers)
    assert other.status_code == 200
    derived = other.json()
    assert derived["catalogue"] == "derived"
    assert derived["requirement_count"] == len(derived["rows"]) > 0


@pytest.mark.asyncio
async def test_requirement_row_reflects_control_state(client: AsyncClient, auth_headers: dict, db_session, tenant) -> None:
    from unimonitor.grc.framework_mappings import cpcsc_requirement

    requirement = cpcsc_requirement("03.05.03")
    assert requirement is not None
    control_id = requirement["controls"][0]
    db_session.add(_finding(tenant.id, control_id, severity="critical", state="implemented"))
    await db_session.flush()

    response = await client.get("/api/v1/grc/frameworks/cpcsc/requirements", headers=auth_headers)
    rows = {row["id"]: row for row in response.json()["rows"]}
    assert rows["03.05.03"]["implemented"] >= 1
    assert rows["03.05.03"]["status"] in {"partial", "implemented"}


@pytest.mark.asyncio
async def test_evidence_package_is_self_contained_and_hashed(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get("/api/v1/grc/frameworks/cpcsc/evidence-package", headers=auth_headers)
    assert response.status_code == 200, response.text
    package = response.json()

    assert package["framework"]["id"] == "cpcsc"
    assert package["controls_total"] > 0
    assert len(package["digest_sha256"]) == 64
    assert package["digest_algorithm"] == "sha256"
    assert set(package["summary"]) == {
        "implemented",
        "partially_implemented",
        "not_implemented",
        "not_applicable",
        "not_run",
    }

    # No credential material travels with an evidence package.
    def secret_keys(node: object) -> set[str]:
        if isinstance(node, dict):
            found = {str(key).lower() for key in node}
            for value in node.values():
                found |= secret_keys(value)
            return found
        if isinstance(node, list):
            found: set[str] = set()
            for value in node:
                found |= secret_keys(value)
            return found
        return set()

    assert not {key for key in secret_keys(package) if any(word in key for word in ("password", "secret", "token", "api_key"))}


@pytest.mark.asyncio
async def test_trends_report_mttr_and_sla_breaches(client: AsyncClient, auth_headers: dict, db_session, tenant) -> None:
    now = datetime.now(UTC)
    db_session.add_all(
        [
            _finding(
                tenant.id,
                "CTRL-ENT-001",
                severity="critical",
                state="implemented",
                first_detected_at=now - timedelta(days=10),
                resolved_at=now - timedelta(days=9),
            ),
            _finding(
                tenant.id,
                "CTRL-ENT-002",
                severity="high",
                state="implemented",
                first_detected_at=now - timedelta(days=20),
                resolved_at=now - timedelta(days=10),
            ),
            # Open well past the 7-day critical target.
            _finding(tenant.id, "CTRL-ENT-003", severity="critical", first_detected_at=now - timedelta(days=30)),
        ]
    )
    await db_session.flush()

    response = await client.get("/api/v1/dashboard/trends", params={"window_days": 90}, headers=auth_headers)
    assert response.status_code == 200, response.text
    remediation = response.json()["remediation"]
    rows = {row["severity"]: row for row in remediation["mttr"]}
    sla = {row["severity"]: row for row in remediation["open_sla"]}

    assert rows["critical"]["resolved"] == 1
    assert rows["critical"]["mean_hours"] == pytest.approx(24, abs=0.1)
    assert rows["high"]["mean_hours"] == pytest.approx(240, abs=0.1)
    assert sla["critical"]["breached"] == 1
    assert sla["critical"]["sla_hours"] == 168


@pytest.mark.asyncio
async def test_tenant_rollup_compares_tenants(client: AsyncClient, auth_headers: dict, db_session, tenant) -> None:
    db_session.add(_finding(tenant.id, "CTRL-ENT-001", severity="critical"))
    await db_session.flush()

    response = await client.get("/api/v1/tenants/rollup", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["totals"]["tenants"] >= 1
    row = next(row for row in body["tenants"] if row["tenant_id"] == tenant.id)
    assert row["critical"] == 1
    assert row["open_findings"] >= 1
    assert row["coverage_pct"] >= 0
    # "rollup" is registered ahead of /{tenant_id}, so it is never read as a tenant id.
    assert body["tenants"][0]["tenant_id"]


@pytest.mark.asyncio
async def test_integration_connectors_are_listed_and_opt_in(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get("/api/v1/integrations", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    siem = {row["slug"]: row for row in body["siem"]}
    assert {"datadog", "splunk", "elastic", "microsoft_sentinel", "sumologic", "webhook", "syslog"} <= set(siem)
    assert all(row["required_settings"] for row in siem.values())
    # No credentials in a test environment, so nothing may report itself ready.
    assert not any(row["configured"] for row in siem.values())

    # Syncing tickets without a provider is a client error, not a silent no-op.
    sync = await client.post("/api/v1/integrations/ticketing/sync", json={}, headers=auth_headers)
    assert sync.status_code == 400

    send = await client.post("/api/v1/integrations/siem/datadog/send", json={}, headers=auth_headers)
    assert send.status_code == 502
    assert "DATADOG_API_KEY" in send.json()["detail"]
