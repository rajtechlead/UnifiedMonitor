"""
Collector Registry — discovers and runs all data collectors for a tenant.
Each collector returns a dict of data keyed by Graph API data type.
"""

from __future__ import annotations

import asyncio
from typing import Any

from unimonitor.core.logging import get_logger
from unimonitor.graph.client import GraphClient
from unimonitor.graph.collectors.extended import (
    collect_cloud_apps,
    collect_copilot_studio,
    collect_defender_identity,
    collect_defender_office,
    collect_ediscovery,
    collect_insider_risk,
    collect_intune_extended,
)
from unimonitor.graph.collectors.snapshot import load_snapshot, merge_snapshot
from unimonitor.graph.staleness import mark_stale, merge_data, stale_keys

logger = get_logger(__name__)


class CollectorRegistry:
    """Manages and runs all Graph data collectors for a tenant."""

    ALL_COLLECTORS = [
        "entra_id",
        "intune",
        "defender",
        "purview",
        "exchange",
        "sharepoint",
        "teams",
        "copilot",
        "azure_security",
        "secure_score",
        "aws",
        "gcp",
        "google_workspace",
    ]

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret

    async def collect_all(
        self,
        collector_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run all (or specified) collectors and merge results."""
        names = collector_names or self.ALL_COLLECTORS
        all_data: dict[str, Any] = {}

        async with GraphClient(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret,
        ) as gc:
            tasks = {name: self._run_collector(name, gc) for name in names}
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)

            for name, result in zip(tasks.keys(), results, strict=False):
                if isinstance(result, Exception):
                    logger.error("Collector failed", collector=name, error=str(result))
                    all_data[f"_error_{name}"] = str(result)
                elif isinstance(result, dict):
                    merge_data(all_data, result)

        # Snapshot fills keys with no Graph endpoint; live data always wins.
        return merge_snapshot(all_data, load_snapshot())

    async def _run_collector(self, name: str, gc: GraphClient) -> dict[str, Any]:
        """Dispatch to the appropriate collector module."""
        collector_map = {
            "entra_id": _collect_entra_id,
            "intune": _collect_intune,
            "defender": _collect_defender,
            "purview": _collect_purview,
            "exchange": _collect_exchange,
            "sharepoint": _collect_sharepoint,
            "teams": _collect_teams,
            "copilot": _collect_copilot,
            "azure_security": _collect_azure_security,
            "secure_score": _collect_secure_score,
            "aws": _collect_aws,
            "gcp": _collect_gcp,
            "google_workspace": _collect_google_workspace,
        }
        fn = collector_map.get(name)
        if fn is None:
            logger.warning("Unknown collector", name=name)
            return {}
        return await fn(gc)


# ── Individual collectors ──────────────────────────────────────────────────


async def _safe_get(gc: GraphClient, endpoint: str, key: str) -> dict[str, Any]:
    """Get a Graph endpoint, return empty on failure.

    Data answered from the last successful response during an outage is still
    evidence, but the key it fills is flagged stale so the control scored from
    it can say so.
    """
    try:
        resp = await gc.get(endpoint)
        if not resp.usable:
            return {}
        data = {key: resp.data}
        return mark_stale(data, key) if resp.stale else data
    except Exception as exc:
        logger.debug("Graph endpoint skipped", endpoint=endpoint, error=str(exc))
        return {}


async def _collect_entra_id(gc: GraphClient) -> dict[str, Any]:
    """Collect Entra ID data: CA policies, MFA, PIM, risky users, auth methods."""
    data: dict[str, Any] = {}

    tasks = [
        _safe_get(gc, "/identity/conditionalAccess/policies", "conditionalAccessPolicies"),
        _safe_get(gc, "/policies/authorizationPolicy", "authorizationPolicy"),
        _safe_get(gc, "/policies/identitySecurityDefaultsEnforcementPolicy", "securityDefaults"),
        _safe_get(gc, "/riskyUsers?$top=100", "riskyUsers"),
        _safe_get(gc, "/auditLogs/signIns?$top=50&$filter=riskState ne 'none'", "riskySignIns"),
        _safe_get(gc, "/policies/authenticationMethodsPolicy", "authMethodsPolicy"),
        _safe_get(gc, "/directoryRoles?$expand=members", "directoryRoles"),
        _safe_get(gc, "/privilegedIdentityManagement/resources", "pimResources"),
        _safe_get(gc, "/organization", "organization"),
        _safe_get(gc, "/users?$top=1&$count=true", "userCount"),
        _safe_get(gc, "/groups?$filter=securityEnabled eq true&$top=100", "securityGroups"),
        _safe_get(gc, "/policies/crossTenantAccessPolicy", "crossTenantAccessPolicy"),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, dict):
            merge_data(data, r)

    return data


async def _collect_intune(gc: GraphClient) -> dict[str, Any]:
    """Collect Intune: device compliance, security baselines, app protection."""
    data: dict[str, Any] = {}

    tasks = [
        _safe_get(gc, "/deviceManagement/deviceCompliancePolicies?$expand=assignments", "deviceCompliancePolicies"),
        _safe_get(gc, "/deviceManagement/managedDevices?$top=100", "managedDevices"),
        _safe_get(gc, "/deviceManagement/deviceConfigurations?$top=100", "deviceConfigurations"),
        _safe_get(gc, "/deviceManagement/intents?$top=100", "securityBaselines"),
        _safe_get(gc, "/deviceAppManagement/managedAppPolicies", "appProtectionPolicies"),
        _safe_get(gc, "/deviceManagement/deviceCompliancePolicyDeviceStateSummary", "complianceSummary"),
        _safe_get(gc, "/deviceManagement/mobileThreatDefenseConnectors", "mtdConnectors"),
        _safe_get(gc, "/deviceManagement/windowsAutopilotDeviceIdentities?$top=10", "autopilotDevices"),
        _safe_get(gc, "/deviceAppManagement/mobileApps?$top=100", "mobileApps"),
        _safe_get(gc, "/deviceManagement/windowsQualityUpdateProfiles", "windowsUpdatePolicies"),
        _safe_get(gc, "/deviceManagement/deviceEnrollmentConfigurations", "deviceEnrollmentConfigurations"),
        _safe_get(gc, "/deviceManagement/configurationPolicies", "configurationPolicies"),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, dict):
            merge_data(data, r)

    merge_data(data, await collect_intune_extended(gc))
    # The control library reads normalised intune_* keys; expose the Graph results
    # under those names instead of asking every control to know the API spelling.
    aliases = {
        "intune_compliance_policies": "deviceCompliancePolicies",
        "intune_device_configurations": "deviceConfigurations",
        "intune_security_baselines": "securityBaselines",
        "intune_app_protection_policies": "appProtectionPolicies",
        "intune_enrollment_restrictions": "deviceEnrollmentConfigurations",
        "intune_endpoint_security_configs": "configurationPolicies",
        "intune_update_rings": "windowsUpdatePolicies",
    }
    stale = stale_keys(data)
    for target, source in aliases.items():
        if source in data:
            data[target] = data[source]
            if source in stale:
                mark_stale(data, target)
    if "managedDevices" in data:
        data["intune_managed_device_count"] = len(data["managedDevices"])
        if "managedDevices" in stale:
            mark_stale(data, "intune_managed_device_count")
    return data


async def _collect_defender(gc: GraphClient) -> dict[str, Any]:
    """Collect Defender: incidents, alerts, secure score, endpoint settings."""
    data: dict[str, Any] = {}

    tasks = [
        _safe_get(gc, "/security/incidents?$top=50", "incidents"),
        _safe_get(gc, "/security/alerts_v2?$top=100", "alerts"),
        _safe_get(gc, "/security/secureScores?$top=1", "secureScores"),
        _safe_get(gc, "/security/secureScoreControlProfiles?$top=200", "secureScoreControls"),
        _safe_get(gc, "/security/attackSimulation/simulationAutomations", "attackSimulations"),
        _safe_get(gc, "/security/threatIntelligence/hosts?$top=50", "threatIntelHosts"),
        _safe_get(gc, "/deviceManagement/advancedThreatProtectionOnboardingStateSummary", "mdeOnboarding"),
        _safe_get(gc, "/security/identitySecurities/healthIssues?$top=100", "mdiHealthIssues"),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, dict):
            merge_data(data, r)

    for section in (collect_defender_office(gc), collect_defender_identity(gc), collect_cloud_apps(gc)):
        merge_data(data, await section)
    return data


async def _collect_purview(gc: GraphClient) -> dict[str, Any]:
    """Collect Purview: DLP, sensitivity labels, insider risk."""
    data: dict[str, Any] = {}

    tasks = [
        _safe_get(gc, "/security/informationProtection/sensitivityLabels", "sensitivityLabels"),
        _safe_get(gc, "/security/dataLossPrevention/policies?$top=100", "dlpPolicies"),
        _safe_get(gc, "/security/cases/ediscoveryCases?$top=50", "ediscoveryCases"),
        _safe_get(gc, "/security/identitySecurities/insiderRiskPolicies?$top=50", "insiderRiskPolicies"),
        _safe_get(gc, "/informationProtection/policy/labels", "infoProtectionLabels"),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, dict):
            merge_data(data, r)

    for section in (collect_insider_risk(gc), collect_ediscovery(gc)):
        merge_data(data, await section)
    return data


async def _collect_exchange(gc: GraphClient) -> dict[str, Any]:
    """Collect Exchange Online security configuration."""
    data: dict[str, Any] = {}

    tasks = [
        _safe_get(gc, "/security/attackSimulation/trainings?$top=50", "securityTrainings"),
        _safe_get(gc, "/domains", "domains"),
        _safe_get(gc, "/security/attackSimulation/simulations?$top=50", "phishSimulations"),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, dict):
            merge_data(data, r)

    return data


async def _collect_sharepoint(gc: GraphClient) -> dict[str, Any]:
    """Collect SharePoint Online security settings."""
    data: dict[str, Any] = {}

    tasks = [
        _safe_get(gc, "/admin/sharepoint/settings", "sharepointSettings"),
        _safe_get(gc, "/sites?$select=id,name,webUrl,isPersonalSite&$top=100", "sites"),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, dict):
            merge_data(data, r)

    # Control library spelling for the same SharePoint data.
    data.setdefault("sharePointSettings", data.get("sharepointSettings"))
    data.setdefault("sharePointSites", data.get("sites", []))
    stale = stale_keys(data)
    for target, source in (("sharePointSettings", "sharepointSettings"), ("sharePointSites", "sites")):
        if source in stale:
            mark_stale(data, target)
    return data


async def _collect_teams(gc: GraphClient) -> dict[str, Any]:
    """Collect Teams security policies."""
    data: dict[str, Any] = {}

    tasks = [
        _safe_get(gc, "/teamwork/teamsAppSettings", "teamsAppSettings"),
        _safe_get(gc, "/teamwork/workforceIntegrations?$top=50", "workforceIntegrations"),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, dict):
            merge_data(data, r)

    return data


async def _collect_copilot(gc: GraphClient) -> dict[str, Any]:
    """Collect Copilot for M365 configuration."""
    data: dict[str, Any] = {}

    tasks = [
        _safe_get(gc, "/copilot/users?$top=100", "copilotUsers"),
        _safe_get(gc, "/policies/copilotPolicies", "copilotPolicies"),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, dict):
            merge_data(data, r)

    merge_data(data, collect_copilot_studio())
    return data


async def _collect_azure_security(gc: GraphClient) -> dict[str, Any]:
    """Collect Azure Security posture via Defender for Cloud."""
    data: dict[str, Any] = {}

    tasks = [
        _safe_get(gc, "/security/secureScores?$top=1", "azureSecureScore"),
        _safe_get(gc, "/security/secureScoreControlProfiles?$filter=controlCategory eq 'Azure'&$top=100", "azureSecureControls"),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, dict):
            merge_data(data, r)

    return data


async def _collect_aws(gc: GraphClient) -> dict[str, Any]:
    """Collect AWS posture (boto3 default credential chain)."""
    from unimonitor.graph.collectors.cloud_providers import collect_aws

    return await collect_aws()


async def _collect_gcp(gc: GraphClient) -> dict[str, Any]:
    """Collect Google Cloud posture (REST, access token from settings)."""
    from unimonitor.graph.collectors.cloud_providers import collect_gcp

    return await collect_gcp()


async def _collect_google_workspace(gc: GraphClient) -> dict[str, Any]:
    """Collect Google Workspace posture (Admin SDK REST)."""
    from unimonitor.graph.collectors.cloud_providers import collect_google_workspace

    return await collect_google_workspace()


async def _collect_secure_score(gc: GraphClient) -> dict[str, Any]:
    """Collect Microsoft Secure Score trends."""
    data: dict[str, Any] = {}

    tasks = [
        _safe_get(gc, "/security/secureScores?$top=30&$orderby=createdDateTime desc", "secureScoreHistory"),
        _safe_get(gc, "/security/secureScoreControlProfiles?$top=200", "secureScoreControlProfiles"),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, dict):
            merge_data(data, r)

    return data
