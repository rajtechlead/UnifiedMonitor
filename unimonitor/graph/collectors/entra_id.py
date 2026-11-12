"""Entra ID collector: Conditional Access, MFA, PIM, Identity Protection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from unimonitor.core.logging import get_logger
from unimonitor.graph.client import GraphClient

logger = get_logger(__name__)


@dataclass
class EntraIdData:
    conditional_access_policies: list[dict] = field(default_factory=list)
    named_locations: list[dict] = field(default_factory=list)
    auth_methods_policy: dict = field(default_factory=dict)
    auth_method_registrations: dict = field(default_factory=dict)
    users: list[dict] = field(default_factory=list)
    privileged_users: list[dict] = field(default_factory=list)
    pim_role_assignments: list[dict] = field(default_factory=list)
    pim_eligible_assignments: list[dict] = field(default_factory=list)
    risky_users: list[dict] = field(default_factory=list)
    risky_sign_ins: list[dict] = field(default_factory=list)
    identity_protection_policy: dict = field(default_factory=dict)
    authorization_policy: dict = field(default_factory=dict)
    security_defaults: dict = field(default_factory=dict)
    directory_roles: list[dict] = field(default_factory=list)
    guest_users: list[dict] = field(default_factory=list)
    service_principals: list[dict] = field(default_factory=list)
    app_registrations: list[dict] = field(default_factory=list)
    sign_in_logs_summary: dict = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class EntraIdCollector:
    """Collect Entra ID security configuration from Microsoft Graph."""

    NAME = "entra_id"
    DISPLAY_NAME = "Microsoft Entra ID"

    def __init__(self, client: GraphClient) -> None:
        self.client = client

    async def collect(self) -> EntraIdData:
        data = EntraIdData()

        await self._collect_conditional_access(data)
        await self._collect_auth_methods(data)
        await self._collect_identity_protection(data)
        await self._collect_pim(data)
        await self._collect_users(data)
        await self._collect_apps(data)
        await self._collect_policies(data)

        logger.info(
            "Entra ID collection complete",
            ca_policies=len(data.conditional_access_policies),
            risky_users=len(data.risky_users),
        )
        return data

    async def _collect_conditional_access(self, data: EntraIdData) -> None:
        try:
            resp = await self.client.get("/identity/conditionalAccess/policies")
            if resp.success:
                data.conditional_access_policies = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["conditional_access_policies"] = str(e)

        try:
            resp = await self.client.get("/identity/conditionalAccess/namedLocations")
            if resp.success:
                data.named_locations = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["named_locations"] = str(e)

    async def _collect_auth_methods(self, data: EntraIdData) -> None:
        try:
            resp = await self.client.get("/policies/authenticationMethodsPolicy")
            if resp.success:
                data.auth_methods_policy = resp.data if isinstance(resp.data, dict) else {}
        except Exception as e:
            data.errors["auth_methods_policy"] = str(e)

        try:
            resp = await self.client.get(
                "/reports/authenticationMethods/userRegistrationDetails",
                params={"$top": "999"},
            )
            if resp.success:
                data.auth_method_registrations = {"users": resp.data if isinstance(resp.data, list) else []}
        except Exception as e:
            data.errors["auth_method_registrations"] = str(e)

    async def _collect_identity_protection(self, data: EntraIdData) -> None:
        try:
            resp = await self.client.get(
                "/identityProtection/riskyUsers",
                params={"$filter": "riskLevel ne 'none'", "$top": "250"},
            )
            if resp.success:
                data.risky_users = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["risky_users"] = str(e)

        try:
            resp = await self.client.get(
                "/identityProtection/riskDetections",
                params={"$filter": "riskState eq 'atRisk'", "$top": "100"},
            )
            if resp.success:
                data.risky_sign_ins = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["risky_sign_ins"] = str(e)

        try:
            resp = await self.client.get("/policies/identitySecurityDefaultsEnforcementPolicy")
            if resp.success:
                data.security_defaults = resp.data if isinstance(resp.data, dict) else {}
        except Exception as e:
            data.errors["security_defaults"] = str(e)

    async def _collect_pim(self, data: EntraIdData) -> None:
        try:
            # Active role assignments via privileged access
            resp = await self.client.get(
                "/roleManagement/directory/roleAssignments",
                params={"$expand": "principal,roleDefinition", "$top": "500"},
            )
            if resp.success:
                data.pim_role_assignments = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["pim_role_assignments"] = str(e)

        try:
            resp = await self.client.get(
                "/roleManagement/directory/roleEligibilitySchedules",
                params={"$expand": "principal,roleDefinition", "$top": "500"},
            )
            if resp.success:
                data.pim_eligible_assignments = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["pim_eligible_assignments"] = str(e)

    async def _collect_users(self, data: EntraIdData) -> None:
        try:
            users = await self.client.get_all_pages(
                "/users",
                params={
                    "$select": "id,displayName,userPrincipalName,accountEnabled,assignedLicenses,"
                               "signInSessionsValidFromDateTime,lastPasswordChangeDateTime",
                    "$top": "999",
                },
                max_pages=10,
            )
            data.users = users

            # Guests
            guests = [u for u in users if "#EXT#" in u.get("userPrincipalName", "")]
            data.guest_users = guests
        except Exception as e:
            data.errors["users"] = str(e)

        try:
            resp = await self.client.get(
                "/users",
                params={
                    "$filter": "assignedPlans/any(a:a/servicePlanId eq '41781fb2-bc02-4b7c-bd55-b576a9eb15de')",
                    "$select": "id,displayName,userPrincipalName",
                    "$top": "500",
                },
            )
            if resp.success:
                data.privileged_users = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["privileged_users"] = str(e)

    async def _collect_apps(self, data: EntraIdData) -> None:
        try:
            apps = await self.client.get_all_pages(
                "/applications",
                params={"$select": "id,displayName,appId,createdDateTime,passwordCredentials,keyCredentials", "$top": "500"},
                max_pages=5,
            )
            data.app_registrations = apps
        except Exception as e:
            data.errors["app_registrations"] = str(e)

        try:
            sps = await self.client.get_all_pages(
                "/servicePrincipals",
                params={"$select": "id,displayName,appId,appRoles,oauth2PermissionScopes", "$top": "500"},
                max_pages=10,
            )
            data.service_principals = sps
        except Exception as e:
            data.errors["service_principals"] = str(e)

    async def _collect_policies(self, data: EntraIdData) -> None:
        try:
            resp = await self.client.get("/policies/authorizationPolicy")
            if resp.success:
                data.authorization_policy = resp.data if isinstance(resp.data, dict) else {}
        except Exception as e:
            data.errors["authorization_policy"] = str(e)

        try:
            resp = await self.client.get("/directoryRoles", params={"$expand": "members($select=id,displayName,userPrincipalName)"})
            if resp.success:
                data.directory_roles = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            data.errors["directory_roles"] = str(e)
