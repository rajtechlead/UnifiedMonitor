"""
Collector Registry — discovers and runs all data collectors for a tenant.
Each collector returns a dict of data keyed by Graph API data type.
"""

from __future__ import annotations

import asyncio
from typing import Any

from unimonitor.core.logging import get_logger
from unimonitor.graph.client import GraphClient

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
                    all_data.update(result)

        return all_data

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
        }
        fn = collector_map.get(name)
        if fn is None:
            logger.warning("Unknown collector", name=name)
            return {}
        return await fn(gc)


# ── Individual collectors ──────────────────────────────────────────────────

async def _safe_get(gc: GraphClient, endpoint: str, key: str) -> dict[str, Any]:
    """Get a Graph endpoint, return empty on failure."""
    try:
        resp = await gc.get(endpoint)
        return {key: resp.data} if resp.success else {}
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
            data.update(r)

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
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, dict):
            data.update(r)

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
            data.update(r)

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
            data.update(r)

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
            data.update(r)

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
            data.update(r)

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
            data.update(r)

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
            data.update(r)

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
            data.update(r)

    return data


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
            data.update(r)

    return data
