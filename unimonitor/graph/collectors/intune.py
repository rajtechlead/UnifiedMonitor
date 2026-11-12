"""Intune collector: compliance, endpoint security, baselines, app protection."""

from __future__ import annotations

from dataclasses import dataclass, field

from unimonitor.core.logging import get_logger
from unimonitor.graph.client import GraphClient

logger = get_logger(__name__)


@dataclass
class IntuneData:
    managed_devices: list[dict] = field(default_factory=list)
    device_compliance_policies: list[dict] = field(default_factory=list)
    device_compliance_policy_states: list[dict] = field(default_factory=list)
    device_configurations: list[dict] = field(default_factory=list)
    security_baselines: list[dict] = field(default_factory=list)
    endpoint_security_templates: list[dict] = field(default_factory=list)
    app_protection_policies_ios: list[dict] = field(default_factory=list)
    app_protection_policies_android: list[dict] = field(default_factory=list)
    app_protection_policies_windows: list[dict] = field(default_factory=list)
    mobile_apps: list[dict] = field(default_factory=list)
    detected_apps: list[dict] = field(default_factory=list)
    autopilot_devices: list[dict] = field(default_factory=list)
    enrollment_restrictions: list[dict] = field(default_factory=list)
    device_enrollment_configurations: list[dict] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class IntuneCollector:
    """Collect Intune MDM/MAM security configuration from Graph API."""

    NAME = "intune"
    DISPLAY_NAME = "Microsoft Intune"

    def __init__(self, client: GraphClient) -> None:
        self.client = client

    async def collect(self) -> IntuneData:
        data = IntuneData()
        await self._collect_devices(data)
        await self._collect_compliance(data)
        await self._collect_security(data)
        await self._collect_apps(data)
        await self._collect_enrollment(data)
        logger.info(
            "Intune collection complete",
            devices=len(data.managed_devices),
            compliance_policies=len(data.device_compliance_policies),
        )
        return data

    async def _collect_devices(self, data: IntuneData) -> None:
        try:
            devices = await self.client.get_all_pages(
                "/deviceManagement/managedDevices",
                params={
                    "$select": "id,deviceName,operatingSystem,osVersion,complianceState,"
                               "managementAgent,deviceEnrollmentType,lastSyncDateTime,"
                               "azureADDeviceId,userPrincipalName",
                    "$top": "500",
                },
                max_pages=20,
            )
            data.managed_devices = devices
        except Exception as e:
            data.errors["managed_devices"] = str(e)

        try:
            ap_resp = await self.client.get(
                "/deviceManagement/windowsAutopilotDeviceIdentities",
                params={"$top": "500"},
            )
            if ap_resp.success:
                data.autopilot_devices = ap_resp.data if isinstance(ap_resp.data, list) else []
        except Exception as e:
            data.errors["autopilot_devices"] = str(e)

    async def _collect_compliance(self, data: IntuneData) -> None:
        try:
            policies = await self.client.get_all_pages(
                "/deviceManagement/deviceCompliancePolicies",
                params={"$top": "100"},
            )
            data.device_compliance_policies = policies
        except Exception as e:
            data.errors["device_compliance_policies"] = str(e)

        try:
            configs = await self.client.get_all_pages(
                "/deviceManagement/deviceConfigurations",
                params={"$top": "100"},
            )
            data.device_configurations = configs
        except Exception as e:
            data.errors["device_configurations"] = str(e)

    async def _collect_security(self, data: IntuneData) -> None:
        try:
            baselines = await self.client.get_all_pages(
                "/deviceManagement/intents",
                params={"$filter": "isTemplate eq false", "$top": "100"},
            )
            data.security_baselines = baselines
        except Exception as e:
            data.errors["security_baselines"] = str(e)

        try:
            templates_resp = await self.client.get(
                "/deviceManagement/templates",
                params={"$filter": "templateType eq 'securityBaseline'", "$top": "50"},
            )
            if templates_resp.success:
                data.endpoint_security_templates = templates_resp.data if isinstance(templates_resp.data, list) else []
        except Exception as e:
            data.errors["endpoint_security_templates"] = str(e)

    async def _collect_apps(self, data: IntuneData) -> None:
        try:
            ios_mam = await self.client.get_all_pages(
                "/deviceAppManagement/iosManagedAppProtections",
                params={"$top": "50"},
            )
            data.app_protection_policies_ios = ios_mam
        except Exception as e:
            data.errors["app_protection_ios"] = str(e)

        try:
            android_mam = await self.client.get_all_pages(
                "/deviceAppManagement/androidManagedAppProtections",
                params={"$top": "50"},
            )
            data.app_protection_policies_android = android_mam
        except Exception as e:
            data.errors["app_protection_android"] = str(e)

        try:
            win_mam = await self.client.get_all_pages(
                "/deviceAppManagement/mdmWindowsInformationProtectionPolicies",
                params={"$top": "50"},
            )
            data.app_protection_policies_windows = win_mam
        except Exception as e:
            data.errors["app_protection_windows"] = str(e)

        try:
            detected = await self.client.get_all_pages(
                "/deviceManagement/detectedApps",
                params={"$top": "200"},
                max_pages=5,
            )
            data.detected_apps = detected
        except Exception as e:
            data.errors["detected_apps"] = str(e)

    async def _collect_enrollment(self, data: IntuneData) -> None:
        try:
            restrictions = await self.client.get_all_pages(
                "/deviceManagement/deviceEnrollmentConfigurations",
                params={"$top": "50"},
            )
            data.device_enrollment_configurations = restrictions
        except Exception as e:
            data.errors["enrollment_configurations"] = str(e)
