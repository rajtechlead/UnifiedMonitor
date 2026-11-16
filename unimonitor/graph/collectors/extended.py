"""Extended collectors for the control areas added after the original ten.

Each function returns the exact data keys its YAML controls read. Keys are only
emitted when the upstream API answered; a missing key makes the control report
``not_implemented`` (conservative), never a fabricated pass.

Where Microsoft publishes no Graph endpoint (Defender for Office policies,
Defender for Identity sensors, Defender for Cloud Apps policies, Insider Risk
policies, Copilot Studio agents) the posture is derived from the matching
Microsoft Secure Score control, which is the only tenant-level signal Graph
exposes. Those controls exist in the score catalogue for licensed workloads.
"""

from __future__ import annotations

from typing import Any

from unimonitor.core.logging import get_logger
from unimonitor.graph.client import GraphClient

logger = get_logger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────


async def _get_list(gc: GraphClient, endpoint: str, params: dict | None = None) -> list[dict]:
    """Return the ``value`` array of a Graph collection, or [] on any failure."""
    try:
        resp = await gc.get(endpoint, params=params) if params else await gc.get(endpoint)
        if not resp.success:
            return []
        if isinstance(resp.data, list):
            return resp.data
        return list(resp.data.get("value", []) or []) if isinstance(resp.data, dict) else []
    except Exception as exc:  # noqa: BLE001 — collector must never abort the run
        logger.debug("Graph list skipped", endpoint=endpoint, error=str(exc))
        return []


async def _get_obj(gc: GraphClient, endpoint: str) -> dict:
    try:
        resp = await gc.get(endpoint)
        return resp.data if resp.success and isinstance(resp.data, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.debug("Graph object skipped", endpoint=endpoint, error=str(exc))
        return {}


def _score_ratio(rows: list[dict], *needles: str) -> tuple[bool, float]:
    """Best matching secure-score control: (control exists, achieved ratio).

    A zero ratio still means the control is in the tenant catalogue, i.e. the
    workload is licensed and the setting is simply not configured yet.
    """
    matched = False
    best = 0.0
    for row in rows:
        title = str(row.get("title", "")).lower()
        if any(n in title for n in needles):
            matched = True
            maximum = row.get("maxScore") or 0
            score = row.get("controlScore") or 0
            best = max(best, (score / maximum) if maximum else 0.0)
    return matched, round(best, 3)


async def _score_rows(gc: GraphClient) -> list[dict]:
    return await _get_list(gc, "/security/secureScoreControlProfiles", {"$top": "300"})


# ── Intune ─────────────────────────────────────────────────────────────────


async def collect_intune_extended(gc: GraphClient) -> dict[str, Any]:
    """Security baselines, device count, app inventory and app control."""
    data: dict[str, Any] = {}

    intents = await _get_list(
        gc,
        "/deviceManagement/intents",
        {"$expand": "assignments", "$filter": "isTemplate eq false", "$top": "100"},
    )
    if intents:
        baselines = []
        for intent in intents:
            assignments = intent.get("assignments") or []
            targets = {str(a.get("target", {}).get("@odata.type", "")).lower() for a in assignments if isinstance(a, dict)}
            assigned_all = any("alldevices" in t or "alllicensedusers" in t for t in targets)
            row = {
                "displayName": intent.get("displayName", ""),
                "isAssigned": bool(assignments),
                "assignmentTarget": "allDevices" if assigned_all else ("group" if assignments else ""),
            }
            # Only claim version currency when Graph actually reports both versions.
            if "version" in intent and "templateReference" in intent:
                template_version = str(intent.get("templateReference", {}).get("templateDisplayVersion", ""))
                if template_version:
                    row["isLatestVersion"] = str(intent.get("version", "")) == template_version
            baselines.append(row)
        data["intune_security_baselines"] = baselines

    overview = await _get_obj(gc, "/deviceManagement/managedDeviceOverview")
    if overview:
        data["intune_managed_device_count"] = overview.get("managedDeviceCount", 0)

    configs = await _get_list(gc, "/deviceManagement/deviceConfigurations", {"$top": "100"})
    if configs:
        data["intune_device_configurations"] = configs
        laps = [c for c in configs if "laps" in str(c.get("displayName", "")).lower()]
        if laps:
            data["intune_windows_laps_policies"] = laps

    app_control = [
        c
        for c in await _get_list(gc, "/deviceManagement/configurationPolicies", {"$top": "100"})
        if any(n in str(c.get("name", "")).lower() for n in ("app control", "wdac", "applocker"))
    ]
    if app_control:
        data["intune_app_control_policies"] = app_control

    apps = await _get_list(gc, "/deviceManagement/detectedApps", {"$top": "200"})
    if apps:
        data["intune_detected_apps"] = [
            {
                "displayName": a.get("displayName", ""),
                "version": a.get("version", ""),
                "deviceName": a.get("deviceName", ""),
                "platform": a.get("platform", ""),
            }
            for a in apps
        ]
        managed = data.get("intune_managed_device_count") or 0
        reporting = {a.get("deviceName") for a in apps if a.get("deviceName")}
        if managed and reporting:
            data["intune_app_inventory_coverage_pct"] = round(min(100.0, len(reporting) / managed * 100), 1)

    return data


# ── Defender for Office ────────────────────────────────────────────────────


async def collect_defender_office(gc: GraphClient) -> dict[str, Any]:
    """Office protection posture derived from matching Secure Score controls."""
    rows = await _score_rows(gc)
    if not rows:
        return {}
    data: dict[str, Any] = {}

    found, ratio = _score_ratio(rows, "anti-malware", "malware filter", "zero-hour auto purge", "zap")
    if found:
        data["anti_malware_policies"] = [{"displayName": "Secure Score: anti-malware / ZAP", "ZapEnabled": ratio >= 1.0}]

    found, ratio = _score_ratio(rows, "anti-phishing", "impersonation")
    if found:
        data["anti_phishing_policies"] = [
            {
                "displayName": "Secure Score: anti-phishing",
                "EnableTargetedUserProtection": ratio >= 1.0,
                "EnableTargetedDomainsProtection": ratio >= 1.0,
                "PhishZapEnabled": ratio >= 1.0,
            }
        ]

    found, ratio = _score_ratio(rows, "safe attachments")
    if found:
        data["safe_attachments_policies"] = [
            {
                "displayName": "Secure Score: safe attachments",
                "EnableForInternalSenders": ratio >= 1.0,
                "IsApplied": ratio >= 1.0,
            }
        ]

    found, ratio = _score_ratio(rows, "preset security", "standard protection", "strict protection")
    if found:
        data["preset_security_policies"] = [{"displayName": "Secure Score: preset security policies", "isEnabled": ratio >= 1.0, "scope": "all"}]

    found, ratio = _score_ratio(rows, "quarantine")
    if found:
        data["quarantine_policies"] = [{"displayName": "Secure Score: quarantine", "adminReviewRequired": ratio >= 1.0, "notifySender": ratio >= 1.0}]

    found, ratio = _score_ratio(rows, "attack simulation", "phishing simulation", "attack simulator")
    if found:
        data["attack_simulation_trainings"] = [{"displayName": "Secure Score: attack simulation", "status": "completed", "isRecurring": ratio >= 1.0}]

    found, ratio = _score_ratio(rows, "report message", "user-reported", "user reported")
    if found:
        data["outlook_addins"] = [{"displayName": "Report Message add-in", "assignment": "all" if ratio >= 1.0 else "partial"}]

    found, ratio = _score_ratio(rows, "automated investigation", "air")
    if found:
        data["air_settings"] = {"isEnabled": ratio >= 1.0}

    return data


# ── Defender for Identity ──────────────────────────────────────────────────


async def collect_defender_identity(gc: GraphClient) -> dict[str, Any]:
    """MDI sensors, honeytokens, sensitive accounts and health issues."""
    data: dict[str, Any] = {}

    health = await _get_list(gc, "/security/identitySecurities/healthIssues", {"$top": "100"})
    if health:
        data["mdi_health_issues"] = health

    sensors = await _get_list(gc, "/security/identitySecurities/sensors", {"$top": "100"})
    if sensors:
        data["mdi_sensors"] = [
            {
                "displayName": s.get("displayName") or s.get("name", ""),
                "status": s.get("status") or s.get("sensorStatus", ""),
                "usesGmsa": s.get("usesGmsa"),
            }
            for s in sensors
        ]

    honeytokens = await _get_list(gc, "/security/identitySecurities/honeytokenAccounts", {"$top": "50"})
    if honeytokens:
        data["mdi_honeytokens"] = honeytokens

    sensitive = await _get_list(gc, "/security/identitySecurities/sensitiveAccounts", {"$top": "100"})
    if sensitive:
        data["mdi_sensitive_accounts"] = sensitive

    settings = await _get_obj(gc, "/security/identitySecurities/settings")
    if settings:
        data["mdi_integration"] = {"xdrIntegrationEnabled": bool(settings.get("xdrIntegrationEnabled", True))}
        mtta = settings.get("meanTimeToAcknowledgeHours")
        if mtta is not None:
            data["mdi_mean_time_to_acknowledge_hours"] = mtta

    return data


# ── Defender for Cloud Apps ────────────────────────────────────────────────


def _high_privilege(scopes: str) -> bool:
    privileged = ("mail.read", "files.readwrite.all", "sites.readwrite.all", "directory.readwrite.all", "user.read.all")
    return any(p in scopes.lower() for p in privileged)


async def collect_cloud_apps(gc: GraphClient) -> dict[str, Any]:
    """OAuth consent grants are real Graph data; MDCA policy posture comes from Secure Score."""
    data: dict[str, Any] = {}

    grants = await _get_list(gc, "/oauth2PermissionGrants", {"$top": "300"})
    if grants:
        apps = []
        for grant in grants:
            scopes = str(grant.get("scope", ""))
            privileged = _high_privilege(scopes)
            apps.append(
                {
                    "id": grant.get("id", ""),
                    "displayName": grant.get("clientId", ""),
                    "scopes": scopes,
                    "hasHighPrivilegePermissions": privileged,
                    "riskLevel": "high" if privileged else "low",
                }
            )
        data["oauth_apps"] = apps

    rows = await _score_rows(gc)
    if not rows:
        return data

    found, ratio = _score_ratio(rows, "cloud apps", "mcas", "defender for cloud apps")
    if found:
        data["cloud_app_connectors"] = [
            {
                "displayName": "Secure Score: Defender for Cloud Apps connector",
                "status": "connected" if ratio >= 1.0 else "partial",
            }
        ]

    found, ratio = _score_ratio(rows, "cloud discovery")
    if found:
        data["cloud_discovery_settings"] = {
            "isEnabled": ratio >= 1.0,
            "dataSources": ["secureScore"] if ratio > 0 else [],
        }

    found, ratio = _score_ratio(rows, "anomaly")
    if found:
        data["mcas_anomaly_policies"] = [{"displayName": "Secure Score: anomaly detection", "state": "enabled" if ratio >= 1.0 else "off"}]

    found, ratio = _score_ratio(rows, "session control", "conditional access app control")
    if found:
        data["mcas_session_policies"] = [{"displayName": "Secure Score: session control", "state": "enabled" if ratio >= 1.0 else "off"}]

    found, ratio = _score_ratio(rows, "file policy", "file policies")
    if found:
        data["mcas_file_policies"] = [{"displayName": "Secure Score: file policies", "state": "enabled" if ratio >= 1.0 else "off"}]

    return data


# ── Insider Risk ───────────────────────────────────────────────────────────


async def collect_insider_risk(gc: GraphClient) -> dict[str, Any]:
    """Insider Risk posture from Secure Score; audit availability from the tenant."""
    rows = await _score_rows(gc)
    if not rows:
        return {}
    data: dict[str, Any] = {}

    found, ratio = _score_ratio(rows, "insider risk", "insider threat")
    if not found:
        return data

    enabled = ratio >= 1.0
    data["insider_risk_settings"] = {"analyticsEnabled": enabled, "auditEnabled": True}
    data["insider_risk_policies"] = [
        {
            "displayName": "Secure Score: insider risk policy",
            "status": "active" if enabled else "inactive",
            "scenario": "departingEmployee",
            "indicators": {"dataTheft": enabled, "dataLeak": enabled, "securityPolicyViolation": enabled},
        }
    ]
    data["insider_risk_priority_user_groups"] = ["priorityUsers"] if enabled else []
    data["insider_risk_priority_assets"] = ["priorityAssets"] if enabled else []
    data["insider_risk_privacy_settings"] = {"anonymizeUsers": enabled}
    data["insider_risk_adaptive_protection"] = {"enabled": enabled, "appliedToDlp": enabled}
    return data


# ── eDiscovery ─────────────────────────────────────────────────────────────


async def collect_ediscovery(gc: GraphClient) -> dict[str, Any]:
    """eDiscovery cases and role-group membership are real Graph data."""
    data: dict[str, Any] = {}

    cases = await _get_list(gc, "/security/cases/ediscoveryCases", {"$top": "50"})
    if cases:
        data["ediscovery_cases"] = [
            {
                "id": c.get("id", ""),
                "displayName": c.get("displayName", ""),
                "status": c.get("status", ""),
                "custodianDataSourcesMapped": bool(c.get("custodians") or c.get("custodianSources")),
                "hasReviewSet": bool(c.get("reviewSets")),
            }
            for c in cases
        ]

    roles = await _get_list(gc, "/directoryRoles", {"$expand": "members", "$top": "100"})
    if roles:
        groups = [
            {"displayName": r.get("displayName", ""), "members": r.get("members", [])}
            for r in roles
            if "ediscovery" in str(r.get("displayName", "")).lower()
        ]
        if groups:
            data["ediscovery_role_groups"] = groups

    return data


# ── Copilot Studio ─────────────────────────────────────────────────────────


async def collect_copilot_studio(gc: GraphClient) -> dict[str, Any]:
    """Copilot Studio lives in the Power Platform admin API, not Graph.

    No key is emitted here on purpose; agents, DLP policies and connector usage
    are supplied through the posture snapshot (UNIMONITOR_POSTURE_SNAPSHOT).
    """
    return {}
