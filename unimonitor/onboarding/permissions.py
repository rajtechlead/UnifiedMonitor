"""Single source of truth for the Microsoft Graph application permissions UniMonitor needs.

The setup wizard reads this list to create the Entra app registration, request the
roles, and grant admin consent, so an install never depends on a human ticking boxes
in the portal. `INSTALL.md` documents the same list and a test keeps them in sync.

`Exchange.ManageAsApp` is deliberately absent: it is an Exchange Online role, not a
Graph app role, so it cannot be granted through the Graph API. The wizard reports it
as a manual follow-up only if Exchange collection is wanted.
"""

from __future__ import annotations

from dataclasses import dataclass

GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"


@dataclass(frozen=True)
class GraphPermission:
    name: str
    feature: str


# Read-only app roles the collectors use. Requesting them all at registration time
# means admin consent is granted once, not every time a dashboard is opened.
REQUIRED: tuple[GraphPermission, ...] = (
    GraphPermission("Directory.Read.All", "Entra ID users, groups, roles"),
    GraphPermission("Policy.Read.All", "Conditional Access and authentication policies"),
    GraphPermission("DeviceManagementConfiguration.Read.All", "Intune compliance policies"),
    GraphPermission("DeviceManagementManagedDevices.Read.All", "Intune managed devices"),
    GraphPermission("SecurityEvents.Read.All", "Secure Score and Defender alerts"),
    GraphPermission("InformationProtectionPolicy.Read.All", "Purview sensitivity labels"),
    GraphPermission("Sites.Read.All", "SharePoint sharing settings"),
    GraphPermission("Teams.ReadBasic.All", "Teams settings"),
    GraphPermission("AuditLog.Read.All", "Sign-in and directory audit logs"),
    GraphPermission("Reports.Read.All", "Usage and security reports"),
    GraphPermission("User.Read.All", "User profile and authentication methods"),
)

# Granted when the tenant allows it; a refusal is reported, never fatal.
OPTIONAL: tuple[GraphPermission, ...] = (
    GraphPermission("SecurityAlert.Read.All", "Defender XDR alert detail"),
    GraphPermission("IdentityRiskyUser.Read.All", "Entra ID risky users"),
)

# Not read-only: `addKey`/`removeKey` on the app itself. It only reaches applications
# this app owns, and the wizard makes it an owner of its own registration, so the
# scope of the permission is exactly "rotate my own certificate".
SELF_MANAGEMENT: tuple[GraphPermission, ...] = (GraphPermission("Application.ReadWrite.OwnedBy", "Rotate its own certificate from Settings"),)

MANUAL_FOLLOW_UP = (
    "Exchange.ManageAsApp is an Exchange Online role and cannot be granted through Graph. "
    "Assign it in the Exchange admin center only if you collect Exchange settings.",
)
