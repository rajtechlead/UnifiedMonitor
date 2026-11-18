"""Tests for the capabilities merged from the reference projects.

Covers the HTML report (M365 Sheppard / Zero Trust Assessment), the Zero Trust
pillar view, and the finding triage workflow plus ROI queue (Vigil365 / Sheppard).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from unimonitor.grc.pillars import PILLARS, pillar_for


class TestPillars:
    def test_every_pillar_is_distinct(self) -> None:
        assert len({p.id for p in PILLARS}) == len(PILLARS)

    @pytest.mark.parametrize(
        ("mapping", "expected"),
        [
            ("identity.verify_explicitly", "identity"),
            ("endpoints.threat_protection", "devices"),
            ("apps.least_privilege", "data"),
            ("network.traffic_inspection", "network"),
            ("infrastructure.assume_breach", "infrastructure"),
            ("unknown.value", None),
        ],
    )
    def test_mapping_alias(self, mapping: str, expected: str | None) -> None:
        assert pillar_for(mapping) == expected


class TestHtmlReport:
    def test_report_escapes_findings_and_lists_providers(self, tmp_path: Path) -> None:
        from unimonitor.reporting.html_generator import HtmlReportGenerator

        finding = {
            "id": "f1",
            "external_control_id": "CTRL-ENT-001",
            "title": "<script>alert(1)</script>",
            "severity": "CRITICAL",
            "state": "not_implemented",
            "category": "identity",
            "service": "entra_id",
        }
        run = {"id": "run-1", "security_score": 42, "compliance_score": 50, "risk_score": 60}
        path = HtmlReportGenerator(run=run, findings=[finding], output_dir=str(tmp_path)).generate()

        html = Path(path).read_text(encoding="utf-8")
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html
        assert "Microsoft 365" in html
        assert "CTRL-ENT-001" in html


@pytest.mark.asyncio
async def test_zero_trust_endpoint_reports_all_pillars(client, auth_headers, db_session, tenant) -> None:
    from unimonitor.db.models.finding import Finding

    db_session.add(
        Finding(
            tenant_id=tenant.id,
            external_control_id="CTRL-ENT-001",
            title="MFA",
            description="mfa",
            severity="critical",
            state="implemented",
            category="identity",
            service="entra_id",
            risk_score=0,
        )
    )
    await db_session.flush()

    response = await client.get("/api/v1/dashboard/zero-trust", headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["pillars"]) == len(PILLARS)
    identity = next(p for p in payload["pillars"] if p["id"] == "identity")
    assert identity["controls_total"] > 0
    assert identity["implemented"] >= 1


@pytest.mark.asyncio
async def test_report_download_uses_the_generated_file_map(client, auth_headers, db_session, tenant, tmp_path: Path) -> None:
    import json

    from unimonitor.db.models.report import Report

    generated = tmp_path / "report.html"
    generated.write_text("<html>ok</html>", encoding="utf-8")
    report = Report(
        tenant_id=tenant.id,
        status="completed",
        formats=json.dumps(["html"]),
        file_paths=json.dumps({"html": str(generated)}),
    )
    db_session.add(report)
    await db_session.flush()

    response = await client.get(f"/api/v1/reports/{report.id}/download/html", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    assert "ok" in response.text

    missing = await client.get(f"/api/v1/reports/{report.id}/download/pdf", headers=auth_headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_triage_and_priority_queue(client, auth_headers, db_session, tenant) -> None:
    from unimonitor.db.models.finding import Finding

    finding = Finding(
        tenant_id=tenant.id,
        external_control_id="CTRL-ENT-001",
        title="Require MFA",
        description="mfa",
        severity="critical",
        state="not_implemented",
        category="identity",
        service="entra_id",
        risk_score=10,
    )
    db_session.add(finding)
    await db_session.flush()

    triaged = await client.post(
        f"/api/v1/findings/{finding.id}/triage",
        headers=auth_headers,
        json={"status": "acknowledged", "note": "On it"},
    )
    assert triaged.status_code == 200, triaged.text
    assert triaged.json()["triage_status"] == "acknowledged"

    queue = await client.get("/api/v1/findings/priority", headers=auth_headers)
    assert queue.status_code == 200, queue.text
    items = queue.json()["items"]
    ids = [item["id"] for item in items]
    assert finding.id in ids
    assert all(item["roi"] > 0 for item in items)

    # A resolved finding leaves the queue.
    await client.post(
        f"/api/v1/findings/{finding.id}/triage",
        headers=auth_headers,
        json={"status": "resolved"},
    )
    queue = await client.get("/api/v1/findings/priority", headers=auth_headers)
    assert finding.id not in [item["id"] for item in queue.json()["items"]]
