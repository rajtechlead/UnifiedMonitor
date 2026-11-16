"""Extended collectors + the 58 controls that consume their data keys.

Every test drives a mocked GraphClient with a realistic sample payload, runs the
collector that normalises it, then evaluates the YAML controls against the
resulting data dict — the same path the assessment engine uses.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from unimonitor.graph.collectors import extended
from unimonitor.graph.collectors.snapshot import load_snapshot, merge_snapshot
from unimonitor.grc.control_loader import ControlLoader

VALID_STATES = {"implemented", "partially_implemented", "not_implemented", "not_applicable"}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class FakeGraph:
    """Prefix-routed GraphClient double returning canned payloads."""

    def __init__(self, routes: dict[str, object]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    async def get(self, endpoint: str, params: dict | None = None) -> SimpleNamespace:
        self.calls.append(endpoint)
        for prefix, payload in self.routes.items():
            if endpoint.startswith(prefix):
                return SimpleNamespace(data=payload, success=True)
        return SimpleNamespace(data={}, success=False)


CONTROLS = {c.id: c for c in ControlLoader().load_all()}


def evaluate(control_id: str, data: dict) -> str:
    return CONTROLS[control_id].run_evaluate(data)


# ── sample payloads ────────────────────────────────────────────────────────

INTUNE_ROUTES = {
    "/deviceManagement/intents": {
        "value": [
            {
                "displayName": "Windows Security Baseline",
                "version": "4",
                "templateReference": {"templateDisplayVersion": "4"},
                "assignments": [{"target": {"@odata.type": "#microsoft.graph.allDevicesAssignmentTarget"}}],
            },
            {
                "displayName": "Defender for Endpoint Baseline",
                "assignments": [{"target": {"@odata.type": "#microsoft.graph.groupAssignmentTarget"}}],
            },
            {
                "displayName": "Microsoft Edge Baseline",
                "assignments": [{"target": {"@odata.type": "#microsoft.graph.allDevicesAssignmentTarget"}}],
            },
            {"displayName": "Microsoft 365 Apps Baseline", "assignments": []},
        ]
    },
    "/deviceManagement/managedDeviceOverview": {"managedDeviceCount": 2},
    "/deviceManagement/deviceConfigurations": {
        "value": [
            {"displayName": "LAPS policy"},
            {"displayName": "Credential Guard", "LSA_CredentialGuardEnabled": 1, "LSA_RunAsPPL": 1},
        ]
    },
    "/deviceManagement/configurationPolicies": {"value": [{"name": "App Control for Business"}]},
    "/deviceManagement/detectedApps": {
        "value": [
            {"displayName": "7-Zip", "deviceName": "PC-1"},
            {"displayName": "Chrome", "deviceName": "PC-2"},
        ]
    },
}

SCORE_ROUTES = {
    "/security/secureScoreControlProfiles": {
        "value": [
            {"title": "Ensure Safe Attachments policy is enabled", "controlScore": 2, "maxScore": 2},
            {"title": "Ensure anti-phishing policy with impersonation protection", "controlScore": 1, "maxScore": 1},
            {"title": "Ensure Zero-hour auto purge for malware is enabled", "controlScore": 2, "maxScore": 2},
            {"title": "Ensure attack simulation training is enabled", "controlScore": 0, "maxScore": 1},
            {"title": "Ensure quarantine policies are configured", "controlScore": 1, "maxScore": 1},
            {"title": "Ensure preset security policies are applied", "controlScore": 1, "maxScore": 1},
            {"title": "Ensure user-reported message add-in is deployed", "controlScore": 1, "maxScore": 1},
            {"title": "Ensure automated investigation and response is enabled", "controlScore": 1, "maxScore": 1},
            {"title": "Ensure Defender for Cloud Apps is connected", "controlScore": 1, "maxScore": 1},
            {"title": "Ensure cloud discovery is enabled", "controlScore": 1, "maxScore": 1},
            {"title": "Ensure anomaly detection policies are enabled", "controlScore": 1, "maxScore": 1},
            {"title": "Ensure session controls are configured", "controlScore": 1, "maxScore": 1},
            {"title": "Ensure file policies are configured", "controlScore": 1, "maxScore": 1},
            {"title": "Ensure insider risk policies are enabled", "controlScore": 1, "maxScore": 1},
        ]
    },
}

MDI_ROUTES = {
    "/security/identitySecurities/sensors": {
        "value": [
            {"displayName": "DC01", "status": "Healthy", "usesGmsa": True},
            {"displayName": "DC02", "status": "Healthy", "usesGmsa": True},
        ]
    },
    "/security/identitySecurities/healthIssues": {"value": []},
    "/security/identitySecurities/honeytokenAccounts": {"value": [{"id": "ht1"}]},
    "/security/identitySecurities/sensitiveAccounts": {"value": [{"id": "sa1"}, {"id": "sa2"}]},
    "/security/identitySecurities/settings": {"xdrIntegrationEnabled": True, "meanTimeToAcknowledgeHours": 2},
}

CLOUD_APP_ROUTES = {
    "/oauth2PermissionGrants": {
        "value": [
            {"id": "g1", "clientId": "app-1", "scope": "Mail.Read Files.ReadWrite.All"},
            {"id": "g2", "clientId": "app-2", "scope": "User.Read"},
        ]
    },
}

EDISCOVERY_ROUTES = {
    "/security/cases/ediscoveryCases": {"value": [{"id": "case-1", "displayName": "Matter A", "status": "active"}]},
    "/directoryRoles": {
        "value": [
            {"displayName": "eDiscovery Manager", "members": [{"id": "u1"}, {"id": "u2"}]},
            {"displayName": "Global Reader", "members": [{"id": "u3"}]},
        ]
    },
}

COPILOT_SNAPSHOT = {
    "copilot_studio_agents": [
        {
            "displayName": "HR Agent",
            "environmentName": "Prod",
            "requiresAuthentication": True,
            "sharingScope": "internal",
            "owner": "admin@example.com",
            "daysSinceLastActivity": 5,
        }
    ],
    "power_platform_dlp_policies": [{"displayName": "Copilot Studio DLP", "state": "enabled", "coversCopilotStudio": True}],
    "copilot_studio_connector_usage": [{"connectorName": "sharepoint"}],
    "copilot_studio_approved_connectors": ["sharepoint"],
    "copilot_studio_logging_settings": {"transcriptsEnabled": True, "retentionDays": 365},
    "copilot_studio_knowledge_sources": [{"type": "sharepoint", "isGoverned": True}],
}


@pytest.fixture(scope="module")
def collected() -> dict:
    """Full snapshot as produced by one assessment run."""
    data: dict = {}
    data.update(_run(extended.collect_intune_extended(FakeGraph(INTUNE_ROUTES))))
    office_graph = FakeGraph({**SCORE_ROUTES})
    data.update(_run(extended.collect_defender_office(office_graph)))
    data.update(_run(extended.collect_defender_identity(FakeGraph(MDI_ROUTES))))
    cloud_graph = FakeGraph({**CLOUD_APP_ROUTES, **SCORE_ROUTES})
    data.update(_run(extended.collect_cloud_apps(cloud_graph)))
    data.update(_run(extended.collect_insider_risk(FakeGraph(SCORE_ROUTES))))
    data.update(_run(extended.collect_ediscovery(FakeGraph(EDISCOVERY_ROUTES))))
    data.update(merge_snapshot({}, COPILOT_SNAPSHOT))
    return data


# ── collectors ─────────────────────────────────────────────────────────────


def test_intune_collector_normalises_baselines(collected):
    baselines = collected["intune_security_baselines"]
    assert len(baselines) == 4
    windows = next(b for b in baselines if b["displayName"].startswith("Windows"))
    assert windows["isAssigned"] is True
    assert windows["assignmentTarget"] == "allDevices"
    assert windows["isLatestVersion"] is True
    assert collected["intune_managed_device_count"] == 2
    assert collected["intune_app_inventory_coverage_pct"] == 100.0


def test_defender_office_collector_maps_score_controls(collected):
    assert collected["safe_attachments_policies"][0]["EnableForInternalSenders"] is True
    assert collected["attack_simulation_trainings"][0]["isRecurring"] is False
    assert collected["air_settings"]["isEnabled"] is True


def test_mdi_collector_normalises_sensors(collected):
    assert {s["status"] for s in collected["mdi_sensors"]} == {"Healthy"}
    assert collected["mdi_honeytokens"]
    assert collected["mdi_mean_time_to_acknowledge_hours"] == 2


def test_cloud_apps_collector_flags_privileged_oauth(collected):
    apps = collected["oauth_apps"]
    assert len(apps) == 2
    assert sum(1 for a in apps if a["hasHighPrivilegePermissions"]) == 1


def test_ediscovery_collector_reads_role_members(collected):
    assert collected["ediscovery_cases"][0]["displayName"] == "Matter A"
    assert len(collected["ediscovery_role_groups"][0]["members"]) == 2


# ── controls driven by those keys ──────────────────────────────────────────


def test_intune_controls_evaluate(collected):
    assert evaluate("CTRL-INT-011", collected) == "implemented"
    assert evaluate("CTRL-INT-012", collected) == "implemented"
    assert evaluate("CTRL-INT-013", collected) == "implemented"
    assert evaluate("CTRL-INT-016", collected) == "implemented"
    assert evaluate("CTRL-INT-017", collected) == "implemented"
    assert evaluate("CTRL-INT-018", collected) == "implemented"


def test_application_inventory_controls_evaluate(collected):
    assert evaluate("CTRL-APP-001", collected) == "implemented"
    assert evaluate("CTRL-APP-002", collected) == "implemented"
    assert evaluate("CTRL-APP-003", collected) == "not_applicable"
    assert evaluate("CTRL-APP-006", collected) == "implemented"


def test_defender_office_controls_evaluate(collected):
    assert evaluate("CTRL-DEF-009", collected) == "implemented"
    assert evaluate("CTRL-DEF-010", collected) == "implemented"
    assert evaluate("CTRL-DEF-011", collected) == "partially_implemented"
    assert evaluate("CTRL-DEF-013", collected) == "implemented"
    assert evaluate("CTRL-DEF-014", collected) == "implemented"
    assert evaluate("CTRL-DEF-016", collected) == "implemented"


def test_defender_identity_controls_evaluate(collected):
    assert evaluate("CTRL-DEF-017", collected) == "implemented"
    assert evaluate("CTRL-DEF-018", collected) == "implemented"
    assert evaluate("CTRL-DEF-019", collected) == "implemented"
    assert evaluate("CTRL-DEF-021", collected) == "implemented"
    assert evaluate("CTRL-DEF-023", collected) == "implemented"


def test_cloud_apps_controls_evaluate(collected):
    assert evaluate("CTRL-DEF-024", collected) == "implemented"
    assert evaluate("CTRL-DEF-025", collected) == "implemented"
    assert evaluate("CTRL-DEF-027", collected) == "implemented"
    assert evaluate("CTRL-DEF-028", collected) == "partially_implemented"
    assert evaluate("CTRL-DEF-029", collected) == "not_applicable"


def test_insider_risk_controls_evaluate(collected):
    assert evaluate("CTRL-PUR-006", collected) == "implemented"
    assert evaluate("CTRL-PUR-007", collected) == "implemented"
    assert evaluate("CTRL-PUR-008", collected) == "implemented"
    assert evaluate("CTRL-PUR-010", collected) == "not_applicable"
    assert evaluate("CTRL-PUR-013", collected) == "not_applicable"


def test_ediscovery_controls_evaluate(collected):
    assert evaluate("CTRL-PUR-015", collected) == "implemented"
    assert evaluate("CTRL-PUR-018", collected) == "not_implemented"
    assert evaluate("CTRL-PUR-019", collected) == "partially_implemented"


def test_copilot_studio_controls_evaluate(collected):
    for cid in (
        "CTRL-COP-009",
        "CTRL-COP-010",
        "CTRL-COP-011",
        "CTRL-COP-012",
        "CTRL-COP-013",
        "CTRL-COP-014",
        "CTRL-COP-015",
        "CTRL-COP-016",
    ):
        assert evaluate(cid, collected) == "implemented", cid


# ── every new control is reachable ─────────────────────────────────────────


def _new_control_ids() -> list[str]:
    def is_new(cid: str) -> bool:
        if not cid.startswith("CTRL-"):
            return False
        family = cid.split("-")[1]
        number = int(cid.rsplit("-", 1)[1]) if cid.rsplit("-", 1)[1].isdigit() else 0
        return (
            (family == "INT" and number >= 11)
            or family == "APP"
            or (family == "DEF" and number >= 9)
            or (family == "PUR" and number >= 6)
            or (family == "COP" and number >= 9)
        )

    return sorted(cid for cid in CONTROLS if is_new(cid))


def test_all_new_controls_return_canonical_states(collected):
    ids = _new_control_ids()
    assert len(ids) >= 58
    broken = {cid: evaluate(cid, collected) for cid in ids if evaluate(cid, collected) not in VALID_STATES}
    assert not broken, broken


def test_every_new_control_has_data_path(collected):
    """No new control may fall back to the loader's default evaluator."""
    missing = []
    for cid in _new_control_ids():
        code = CONTROLS[cid]._evaluate_code
        if "return 'not_implemented'" in code and len(code) < 60:
            missing.append(cid)
    assert not missing, missing


# ── snapshot handling ──────────────────────────────────────────────────────


def test_snapshot_never_overrides_live_data():
    merged = merge_snapshot({"intune_security_baselines": [{"displayName": "live"}]}, COPILOT_SNAPSHOT)
    assert merged["intune_security_baselines"][0]["displayName"] == "live"
    assert "copilot_studio_agents" in merged


def test_snapshot_loads_from_file(tmp_path):
    path = tmp_path / "posture.json"
    path.write_text('{"copilot_studio_agents": []}', encoding="utf-8")
    assert load_snapshot(path) == {"copilot_studio_agents": []}


def test_snapshot_missing_file_is_ignored(tmp_path):
    assert load_snapshot(tmp_path / "absent.json") == {}


def test_snapshot_rejects_non_object(tmp_path):
    path = tmp_path / "posture.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_snapshot(path) == {}
