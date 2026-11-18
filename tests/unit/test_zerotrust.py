"""Zero Trust assessment: export normalisation, cloud checks, API and packaging."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from unimonitor.zerotrust.normalise import normalise_checks, pillar_for_text, summarise

ROOT = Path(__file__).resolve().parents[2]


# ── Normalisation ────────────────────────────────────────────────────────────


def test_normalises_microsoft_export_rows() -> None:
    payload = [
        {
            "TestId": 21770,
            "Title": "Conditional Access policies require MFA for admins",
            "Pillar": "Identity",
            "Risk": "High",
            "Result": "Failed",
            "Remediation": "Create a policy that requires MFA.\nScope it to admin roles.",
        },
        {
            "TestId": 21874,
            "Title": "Guest access is limited to approved tenants",
            "Risk": "Medium",
            "Status": "Passed",
            "Remediation": [{"action": "Restrict cross-tenant access"}],
        },
    ]

    checks = normalise_checks(payload)

    assert [check["check_id"] for check in checks] == ["21770", "21874"]
    assert checks[0]["status"] == "fail"
    assert checks[1]["status"] == "pass"
    assert checks[0]["pillar"] == "identity"
    assert checks[0]["severity"] == "high"
    assert checks[0]["remediation"] == ["Create a policy that requires MFA.", "Scope it to admin roles."]
    assert checks[1]["remediation"] == ["Restrict cross-tenant access"]


def test_normalises_pillar_sections_of_a_report() -> None:
    payload = {
        "TenantId": "contoso",
        "Identity": {
            "Tests": [
                {"Id": "ID-1", "Name": "Block legacy authentication", "Result": "Passed", "RiskLevel": "Low"},
            ]
        },
        "Devices": {
            "Tests": [
                {"Id": "DEV-1", "Name": "Device compliance required", "Result": "Failed", "RiskLevel": "High"},
            ]
        },
    }

    checks = {check["check_id"]: check for check in normalise_checks(payload)}

    assert checks["ID-1"]["pillar"] == "identity"
    assert checks["DEV-1"]["pillar"] == "devices"
    assert checks["DEV-1"]["status"] == "fail"


def test_report_keyed_by_test_id_is_read() -> None:
    payload = {"21770": {"Title": "MFA for admins", "Result": True}, "21771": {"Title": "Legacy auth blocked", "Result": False}}
    checks = {check["check_id"]: check for check in normalise_checks(payload)}
    assert checks["21770"]["status"] == "pass"
    assert checks["21771"]["status"] == "fail"


def test_unknown_result_does_not_become_a_pass() -> None:
    checks = normalise_checks([{"TestId": "X", "Title": "Something", "Result": "???"}])
    assert checks[0]["status"] == "not_run"


def test_pillar_inferred_from_title() -> None:
    assert pillar_for_text("Firewall rule exposes management ports") == "network"
    assert pillar_for_text("Sensitivity labels applied to documents") == "data"
    assert pillar_for_text("Copilot data access restricted") == "ai"


def test_summary_scores_exclude_unexecuted_tests_and_weight_warnings() -> None:
    checks = [
        {"check_id": "1", "pillar": "identity", "status": "pass"},
        {"check_id": "2", "pillar": "identity", "status": "warn"},
        {"check_id": "3", "pillar": "identity", "status": "fail"},
        {"check_id": "4", "pillar": "identity", "status": "not_run"},
        {"check_id": "5", "pillar": "identity", "status": "not_applicable"},
    ]

    summary = summarise(checks)

    assert summary["total"] == 5
    assert summary["not_run"] == 1
    # pass + half a warning out of three executed checks
    assert summary["score"] == 50.0
    identity = next(pillar for pillar in summary["pillars"] if pillar["id"] == "identity")
    assert identity["total"] == 5


# ── Control catalogue ────────────────────────────────────────────────────────


@pytest.mark.parametrize("platform", ["aws", "gcp", "google_workspace"])
def test_cloud_controls_carry_remediation(platform: str) -> None:
    data = yaml.safe_load((ROOT / "controls" / platform / "security_controls.yaml").read_text())
    controls = data["controls"]
    assert controls
    for control in controls:
        remediation = control.get("remediation") or {}
        assert remediation.get("summary"), f"{control['id']} has no remediation summary"
        assert len(remediation.get("steps") or []) >= 2, f"{control['id']} needs remediation steps"
        # Cloud controls must land in a Zero Trust pillar, not just the small pillar page.
        assert (control.get("compliance_mapping") or {}).get("zero_trust"), f"{control['id']} has no zero_trust mapping"


def test_control_loader_reads_remediation() -> None:
    from unimonitor.grc.control_loader import ControlLoader

    controls = {control.id: control for control in ControlLoader().load_all()}
    aws = controls["CTRL-AWS-001"]
    assert "MFA" in aws.remediation_summary
    assert any("root user" in step for step in aws.remediation_steps)


# ── Cloud evaluation and API ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cloud_checks_use_findings_and_remediation(client, auth_headers, db_session, tenant) -> None:
    from unimonitor.db.models.finding import Finding

    db_session.add(
        Finding(
            tenant_id=tenant.id,
            external_control_id="CTRL-AWS-001",
            title="Root Account MFA Enabled",
            description="root mfa",
            severity="critical",
            state="not_implemented",
            category="cloud_security",
            service="aws",
        )
    )
    await db_session.flush()

    response = await client.post("/api/v1/zerotrust/run", json={"platform": "aws"}, headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run"]["source"] == "aws"
    by_id = {check["check_id"]: check for check in body["checks"]}
    assert by_id["CTRL-AWS-001"]["status"] == "fail"
    assert by_id["CTRL-AWS-001"]["remediation"]
    # A control with no finding is not scored as passing.
    assert by_id["CTRL-AWS-002"]["status"] == "not_run"


@pytest.mark.asyncio
async def test_import_and_read_back_a_report(client, auth_headers) -> None:
    payload = {
        "tests": [
            {"TestId": 1, "Title": "MFA enforced", "Pillar": "Identity", "Risk": "High", "Result": "Passed"},
            {
                "TestId": 2,
                "Title": "Legacy auth blocked",
                "Pillar": "Identity",
                "Risk": "High",
                "Result": "Failed",
                "Remediation": "Disable legacy protocols.",
            },
        ]
    }

    imported = await client.post("/api/v1/zerotrust/import", json={"source": "microsoft", "payload": payload}, headers=auth_headers)
    assert imported.status_code == 200, imported.text
    assert imported.json()["run"]["total"] == 2
    assert imported.json()["run"]["score"] == 50.0

    summary = await client.get("/api/v1/zerotrust/summary", headers=auth_headers)
    assert summary.status_code == 200
    microsoft = next(p for p in summary.json()["platforms"] if p["source"] == "microsoft")
    assert microsoft["has_run"] is True
    assert microsoft["failed"] == 1

    checks = await client.get("/api/v1/zerotrust/checks", headers=auth_headers, params={"source": "microsoft", "status": "fail"})
    assert checks.status_code == 200
    assert [check["check_id"] for check in checks.json()] == ["2"]


@pytest.mark.asyncio
async def test_import_rejects_payload_without_checks(client, auth_headers) -> None:
    response = await client.post("/api/v1/zerotrust/import", json={"source": "microsoft", "payload": {"nothing": "here"}}, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_summary_without_any_run_lists_all_platforms(client, auth_headers) -> None:
    response = await client.get("/api/v1/zerotrust/summary", headers=auth_headers)
    assert response.status_code == 200
    platforms = response.json()["platforms"]
    assert {platform["source"] for platform in platforms} == {"microsoft", "aws", "gcp", "google_workspace"}
    assert all(platform["has_run"] is False for platform in platforms)


@pytest.mark.asyncio
async def test_script_endpoint_serves_the_runner(client, auth_headers) -> None:
    response = await client.get("/api/v1/zerotrust/script", headers=auth_headers)
    assert response.status_code == 200
    assert "Invoke-ZtAssessment" in response.text
    assert "zerotrust/import" in response.text


# ── Packaging ───────────────────────────────────────────────────────────────


def test_runner_script_is_bundled_with_the_windows_build() -> None:
    spec = (ROOT / "deploy" / "windows" / "unimonitor.spec").read_text()
    assert "scripts" in spec
    assert (ROOT / "scripts" / "zerotrust" / "Invoke-UniMonitorZeroTrust.ps1").exists()


def test_installer_workflow_parses_the_runner() -> None:
    workflow = (ROOT / ".github" / "workflows" / "windows-installer.yml").read_text()
    assert "Invoke-UniMonitorZeroTrust.ps1" in workflow
