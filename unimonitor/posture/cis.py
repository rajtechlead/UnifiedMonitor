"""CIS benchmark rule packs.

These packs implement the *intent* of the CIS Foundations benchmarks for each
platform as rules over a normalised inventory. Rule ids are internal
(``CIS-AWS-IAM-MFA``) rather than CIS section numbers: a section number changes
between benchmark versions, and claiming the official number would imply a
certified mapping this product does not have.

A rule whose resources are missing from the snapshot returns *not applicable*, so
an incomplete export produces gaps, never a false pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from unimonitor.posture.engine import Rule, evaluate_rules, no_resources
from unimonitor.posture.inventory import field, flag, text_list


@dataclass(frozen=True)
class Benchmark:
    id: str
    name: str
    platform: str
    rules: list[Rule]


def _sample(resources: list[dict[str, Any]], limit: int = 3) -> str:
    names = [str(resource.get("name") or resource.get("id")) for resource in resources[:limit]]
    more = ", …" if len(resources) > limit else ""
    return ", ".join(names) + more


def _flag_rule(
    rule_id: str,
    title: str,
    severity: str,
    resource_type: str,
    names: tuple[str, ...],
    *,
    want: bool,
    remediation: str,
    tags: tuple[str, ...] = (),
) -> Rule:
    """Pass when every resource's flag equals *want*."""

    def check(groups: dict[str, list[dict[str, Any]]]) -> tuple[bool | None, str]:
        items = groups.get(resource_type, [])
        if not items:
            return no_resources(f"{resource_type} resources")
        checked = [item for item in items if field(item, *names) is not None]
        if not checked:
            return None, f"{resource_type} resources carry no {'/'.join(names)} field"
        bad = [item for item in checked if flag(item, *names) != want]
        if bad:
            expectation = "enabled" if want else "disabled"
            return False, f"{len(bad)} of {len(checked)} not {expectation}: {_sample(bad)}"
        return True, f"all {len(checked)} {resource_type} resources are {'enabled' if want else 'disabled'}"

    return Rule(id=rule_id, title=title, severity=severity, check=check, remediation=remediation, tags=tags)


def _setting_rule(
    rule_id: str,
    title: str,
    severity: str,
    names: tuple[str, ...],
    *,
    want: bool,
    remediation: str,
    tags: tuple[str, ...] = (),
) -> Rule:
    """Pass when a tenant-wide setting (``tenant_settings`` resource) has *want*."""

    def check(groups: dict[str, list[dict[str, Any]]]) -> tuple[bool | None, str]:
        settings = groups.get("tenant_settings", [])
        if not settings:
            return no_resources("tenant settings")
        values = [field(item, *names) for item in settings]
        present = [value for value in values if value is not None]
        if not present:
            return None, f"tenant settings do not include {'/'.join(names)}"
        bad = [value for value in present if flag({names[0]: value}) != want]
        if bad:
            return False, f"setting {'/'.join(names)} is {bad[0]!r}, expected {'enabled' if want else 'disabled'}"
        return True, f"setting {'/'.join(names)} is {'enabled' if want else 'disabled'}"

    return Rule(id=rule_id, title=title, severity=severity, check=check, remediation=remediation, tags=tags)


def _number_rule(
    rule_id: str,
    title: str,
    severity: str,
    names: tuple[str, ...],
    *,
    maximum: int | None = None,
    minimum: int | None = None,
    remediation: str,
) -> Rule:
    """Pass when a tenant-wide numeric setting is within bounds."""

    def check(groups: dict[str, list[dict[str, Any]]]) -> tuple[bool | None, str]:
        settings = groups.get("tenant_settings", [])
        if not settings:
            return no_resources("tenant settings")
        values = [field(item, *names) for item in settings]
        present = []
        for value in values:
            if value is None:
                continue
            try:
                present.append(float(str(value)))
            except ValueError:
                continue
        if not present:
            return None, f"tenant settings do not include {'/'.join(names)}"
        value = present[0]
        if maximum is not None and value > maximum:
            return False, f"{'/'.join(names)} is {value:g}, above the maximum of {maximum}"
        if minimum is not None and value < minimum:
            return False, f"{'/'.join(names)} is {value:g}, below the minimum of {minimum}"
        return True, f"{'/'.join(names)} is {value:g}"

    return Rule(id=rule_id, title=title, severity=severity, check=check, remediation=remediation)


def _identity_key_age_rule(rule_id: str) -> Rule:
    """Every service-account key is younger than 90 days."""

    def check(groups: dict[str, list[dict[str, Any]]]) -> tuple[bool | None, str]:
        identities = groups.get("identity", [])
        if not identities:
            return no_resources("identity resources")
        ages = [field(item, "key_age_days") for item in identities]
        present = [int(age) for age in ages if age is not None]
        if not present:
            return None, "identities carry no key_age_days field"
        stale = [age for age in present if age > 90]
        if stale:
            return False, f"{len(stale)} of {len(present)} keys are older than 90 days (oldest {max(stale)} days)"
        return True, f"oldest key is {max(present)} days old"

    return Rule(
        id=rule_id,
        title="Service-account keys rotated",
        severity="high",
        check=check,
        remediation="Prefer workload identity over long-lived keys; rotate any key older than 90 days.",
    )


def _identities(groups: dict[str, list[dict[str, Any]]], *, privileged_only: bool = False) -> list[dict[str, Any]]:
    items = groups.get("identity", [])
    if not privileged_only:
        return items
    return [
        item for item in items if flag(item, "admin", "is_admin", "privileged") or "admin" in str(field(item, "role", "roles", default="")).lower()
    ]


def _mfa_rule(rule_id: str, severity: str, *, admins_only: bool) -> Rule:
    """MFA is required on every (or every privileged) identity that can sign in."""

    def check(groups: dict[str, list[dict[str, Any]]]) -> tuple[bool | None, str]:
        candidates = _identities(groups, privileged_only=admins_only)
        if not candidates:
            return no_resources("identity resources" + (" with administrative access" if admins_only else ""))
        checked = [item for item in candidates if field(item, "mfa_enabled", "mfa", "mfa_enforced") is not None]
        if not checked:
            return None, "identities carry no mfa field"
        missing = [item for item in checked if not flag(item, "mfa_enabled", "mfa", "mfa_enforced")]
        scope = "privileged identities" if admins_only else "identities"
        if missing:
            return False, f"{len(missing)} of {len(checked)} {scope} without MFA: {_sample(missing)}"
        return True, f"all {len(checked)} {scope} enforce MFA"

    return Rule(
        id=rule_id,
        title="MFA enforced" + (" for administrators" if admins_only else ""),
        severity=severity,
        check=check,
        remediation="Require multi-factor authentication for every account that can reach the tenant, and for administrators before anything else.",
    )


def _wildcard_rule(rule_id: str) -> Rule:
    """No identity may hold an unconditional wildcard permission."""

    def check(groups: dict[str, list[dict[str, Any]]]) -> tuple[bool | None, str]:
        identities = groups.get("identity", [])
        holding = [(item, text_list(item, "permissions", "actions", "policies")) for item in identities]
        holding = [(item, permissions) for item, permissions in holding if permissions]
        if not holding:
            return no_resources("identity permissions")
        broad = [(item, permissions) for item, permissions in holding if any(permission.strip() in ("*", "*:*") for permission in permissions)]
        if broad:
            return False, f"{len(broad)} identities hold a wildcard permission: {_sample([item for item, _ in broad])}"
        return True, f"none of {len(holding)} identities holds a wildcard permission"

    return Rule(
        id=rule_id,
        title="No wildcard permissions",
        severity="high",
        check=check,
        remediation="Replace '*' with the specific actions the workload needs; a wildcard grants every future action too.",
    )


def _open_ports_rule(rule_id: str, platform: str) -> Rule:
    """Management ports must not be reachable from the internet."""

    def check(groups: dict[str, list[dict[str, Any]]]) -> tuple[bool | None, str]:
        groups_with_rules = groups.get("security_group", [])
        if not groups_with_rules:
            return no_resources("network security groups / firewalls")
        exposed = [
            item
            for item in groups_with_rules
            if flag(item, "open_admin_ports", "allows_ssh_from_internet", "allows_rdp_from_internet")
            or any(str(port) in ("22", "3389") for port in text_list(item, "internet_ports", "open_ports"))
        ]
        if exposed:
            return False, f"{len(exposed)} rule sets expose SSH/RDP to the internet: {_sample(exposed)}"
        return True, f"none of {len(groups_with_rules)} rule sets exposes management ports to the internet"

    return Rule(
        id=rule_id,
        title="Management ports not internet-facing",
        severity="critical",
        check=check,
        remediation=f"Restrict 22/3389 on {platform.upper()} to a bastion or VPN range; remove 0.0.0.0/0 ingress for management ports.",
    )


def _logging_rule(rule_id: str, platform: str) -> Rule:
    """Audit logging exists and is enabled."""

    def check(groups: dict[str, list[dict[str, Any]]]) -> tuple[bool | None, str]:
        items = groups.get("logging", [])
        if not items:
            return no_resources("logging configuration")
        disabled = [item for item in items if not flag(item, "enabled", "is_logging", default=True)]
        if disabled:
            return False, f"{len(disabled)} logging configurations are disabled: {_sample(disabled)}"
        multi_region = [item for item in items if field(item, "multi_region") is not None]
        if platform == "aws" and multi_region and not any(flag(item, "multi_region") for item in multi_region):
            return False, "no trail is multi-region"
        return True, f"{len(items)} logging configurations enabled"

    return Rule(
        id=rule_id,
        title="Audit logging enabled",
        severity="high",
        check=check,
        remediation=f"Enable {platform.upper()} audit logging for every region and send it to a protected account.",
    )


AWS_RULES = [
    _mfa_rule("CIS-AWS-IAM-ROOT-MFA", "critical", admins_only=True),
    _wildcard_rule("CIS-AWS-IAM-WILDCARD"),
    _flag_rule(
        "CIS-AWS-S3-PUBLIC",
        "Storage not publicly accessible",
        "critical",
        "storage",
        ("public", "public_access", "is_public"),
        want=False,
        remediation="Enable S3 Block Public Access at the account and bucket level; serve public content through CloudFront.",
    ),
    _flag_rule(
        "CIS-AWS-S3-ENCRYPT",
        "Storage encrypted at rest",
        "high",
        "storage",
        ("encrypted", "encryption_enabled", "sse_enabled"),
        want=True,
        remediation="Enable default SSE-KMS encryption on every bucket and deny unencrypted PUT requests.",
    ),
    _open_ports_rule("CIS-AWS-SG-OPEN-ADMIN", "aws"),
    _logging_rule("CIS-AWS-CLOUDTRAIL", "aws"),
    _flag_rule(
        "CIS-AWS-KMS-ROTATION",
        "KMS key rotation enabled",
        "medium",
        "key",
        ("rotation_enabled", "auto_rotate"),
        want=True,
        remediation="Enable automatic yearly rotation on customer-managed KMS keys.",
    ),
    _flag_rule(
        "CIS-AWS-EBS-ENCRYPT",
        "Block volumes encrypted",
        "high",
        "compute",
        ("encrypted", "ebs_encrypted"),
        want=True,
        remediation="Turn on EBS encryption by default per region and re-create unencrypted volumes.",
    ),
]

AZURE_RULES = [
    _mfa_rule("CIS-AZURE-MFA-ADMIN", "critical", admins_only=True),
    _setting_rule(
        "CIS-AZURE-GUEST-ACCESS",
        "Guest access restricted",
        "high",
        ("guest_access_restricted", "guest_invite_restricted"),
        want=True,
        remediation="Restrict guest invitations and directory roles for external users in Entra ID.",
    ),
    _flag_rule(
        "CIS-AZURE-STORAGE-PUBLIC",
        "Storage public access disabled",
        "critical",
        "storage",
        ("public", "public_access", "allow_blob_public_access"),
        want=False,
        remediation="Disable 'Allow blob public access' on storage accounts and use private endpoints.",
    ),
    _flag_rule(
        "CIS-AZURE-STORAGE-ENCRYPT",
        "Storage encrypted at rest",
        "high",
        "storage",
        ("encrypted", "encryption_enabled"),
        want=True,
        remediation="Enable infrastructure encryption or customer-managed keys on every storage account.",
    ),
    _open_ports_rule("CIS-AZURE-NSG-OPEN-ADMIN", "azure"),
    _flag_rule(
        "CIS-AZURE-KV-PURGE",
        "Key Vault purge protection",
        "high",
        "key",
        ("purge_protection", "purge_protection_enabled"),
        want=True,
        remediation="Enable purge protection and soft delete on every Key Vault.",
    ),
    _number_rule(
        "CIS-AZURE-ACTIVITY-LOG",
        "Activity log retained",
        "medium",
        ("activity_log_retention_days",),
        minimum=90,
        remediation="Export activity logs to a Log Analytics workspace with at least 90 days retention.",
    ),
]

GCP_RULES = [
    _wildcard_rule("CIS-GCP-IAM-WILDCARD"),
    _mfa_rule("CIS-GCP-MFA-ADMIN", "critical", admins_only=True),
    _flag_rule(
        "CIS-GCP-BUCKET-PUBLIC",
        "Buckets not publicly accessible",
        "critical",
        "storage",
        ("public", "public_access", "all_users"),
        want=False,
        remediation="Remove allUsers/allAuthenticatedUsers bindings and enable public access prevention.",
    ),
    _flag_rule(
        "CIS-GCP-BUCKET-CMEK",
        "Buckets use customer-managed keys",
        "medium",
        "storage",
        ("cmek", "customer_managed_key", "encrypted"),
        want=True,
        remediation="Enable CMEK on buckets that hold regulated data.",
    ),
    _open_ports_rule("CIS-GCP-FIREWALL-OPEN-ADMIN", "gcp"),
    _logging_rule("CIS-GCP-AUDIT-LOGS", "gcp"),
    _identity_key_age_rule("CIS-GCP-SA-KEY-AGE"),
]

M365_RULES = [
    _setting_rule(
        "CIS-M365-MFA",
        "MFA enforced for users",
        "critical",
        ("mfa_enforced", "security_defaults_enabled", "conditional_access_mfa"),
        want=True,
        remediation="Enable security defaults or a Conditional Access policy requiring MFA for all users.",
    ),
    _setting_rule(
        "CIS-M365-LEGACY-AUTH",
        "Legacy authentication blocked",
        "critical",
        ("legacy_auth_blocked",),
        want=True,
        remediation="Block legacy authentication protocols with Conditional Access; they cannot enforce MFA.",
    ),
    _setting_rule(
        "CIS-M365-MAILBOX-AUDIT",
        "Mailbox auditing enabled",
        "high",
        ("mailbox_auditing_enabled", "audit_enabled"),
        want=True,
        remediation="Enable mailbox audit logging organisation-wide in Purview.",
    ),
    _setting_rule(
        "CIS-M365-EXTERNAL-SHARING",
        "External sharing restricted",
        "high",
        ("external_sharing_restricted", "external_sharing"),
        want=True,
        remediation="Set SharePoint/OneDrive external sharing to 'New and existing guests' or stricter.",
    ),
    _number_rule(
        "CIS-M365-ADMIN-COUNT",
        "Few standing administrators",
        "medium",
        ("admin_count",),
        maximum=4,
        remediation="Keep fewer than five standing Global Administrators and use PIM for elevation.",
    ),
    _setting_rule(
        "CIS-M365-SELFSERVICE-PASSWORD",
        "Self-service password reset controlled",
        "low",
        ("sspr_enabled",),
        want=True,
        remediation="Require two methods for SSPR and restrict it to a pilot group before broad rollout.",
    ),
]

WORKSPACE_RULES = [
    _setting_rule(
        "CIS-GWS-2SV",
        "Two-step verification enforced",
        "critical",
        ("two_step_verification", "2sv_enforced"),
        want=True,
        remediation="Enforce 2-step verification for the whole domain, with a two-week enrolment window.",
    ),
    _setting_rule(
        "CIS-GWS-LESS-SECURE-APPS",
        "Less secure apps blocked",
        "critical",
        ("less_secure_apps_blocked",),
        want=True,
        remediation="Disable less secure app access and use OAuth for mail clients.",
    ),
    _setting_rule(
        "CIS-GWS-EXTERNAL-SHARING",
        "External sharing restricted",
        "high",
        ("external_sharing_restricted",),
        want=True,
        remediation="Restrict Drive external sharing to allowlisted domains or 'off'.",
    ),
    _number_rule(
        "CIS-GWS-ADMIN-COUNT",
        "Few super administrators",
        "medium",
        ("admin_count",),
        maximum=4,
        remediation="Keep at most four super administrators and use delegated admin roles for everything else.",
    ),
    _number_rule(
        "CIS-GWS-PASSWORD-LENGTH",
        "Password length meets policy",
        "medium",
        ("password_min_length",),
        minimum=12,
        remediation="Set a minimum password length of at least 12 characters.",
    ),
    _setting_rule(
        "CIS-GWS-MAIL-DELEGATION",
        "Mail delegation restricted",
        "high",
        ("mail_delegation_restricted",),
        want=True,
        remediation="Restrict mail delegation to the organisation and review delegates quarterly.",
    ),
]

BENCHMARKS: dict[str, Benchmark] = {
    "aws": Benchmark(id="cis-aws-foundations", name="CIS AWS Foundations (indicative)", platform="aws", rules=AWS_RULES),
    "azure": Benchmark(id="cis-azure-foundations", name="CIS Microsoft Azure Foundations (indicative)", platform="azure", rules=AZURE_RULES),
    "gcp": Benchmark(id="cis-gcp-foundations", name="CIS Google Cloud Foundations (indicative)", platform="gcp", rules=GCP_RULES),
    "m365": Benchmark(id="cis-m365-foundations", name="CIS Microsoft 365 Foundations (indicative)", platform="m365", rules=M365_RULES),
    "google_workspace": Benchmark(
        id="cis-workspace-foundations", name="CIS Google Workspace Foundations (indicative)", platform="google_workspace", rules=WORKSPACE_RULES
    ),
}


def evaluate_cis(platform: str, groups: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Evaluate the CIS pack for a platform (empty result when none exists)."""
    benchmark = BENCHMARKS.get(platform)
    if benchmark is None:
        return {"platform": platform, "benchmark": None, "score": None, "rules_total": 0, "evaluated": 0, "passed": 0, "failed": 0, "results": []}
    result = evaluate_rules(benchmark.rules, groups, benchmark=benchmark.id)
    return {"platform": platform, "benchmark_name": benchmark.name, **result}


__all__ = ["BENCHMARKS", "Benchmark", "evaluate_cis"]
