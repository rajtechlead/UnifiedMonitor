"""Cloud infrastructure entitlement management (CIEM).

Looks at what each identity can actually do — wildcard actions, standing admin
roles, privilege-escalation combinations, long-lived keys and unused grants — and
reports the entitlements that make an incident worse.
"""

from __future__ import annotations

from typing import Any

from unimonitor.posture.findings import PostureFinding, resource_name, result
from unimonitor.posture.inventory import field, flag, number, text_list

CATEGORY = "ciem"
LABEL = "Identity entitlements"

# Actions that, combined with iam:PassRole, allow an identity to grant itself or
# another principal more privilege than it was given.
_ESCALATION_ACTIONS = {
    "iam:createpolicyversion",
    "iam:setdefaultpolicyversion",
    "iam:attachuserpolicy",
    "iam:attachgrouppolicy",
    "iam:attachrolepolicy",
    "iam:putuserpolicy",
    "iam:putgrouppolicy",
    "iam:putrolepolicy",
    "iam:createaccesskey",
    "iam:updateloginprofile",
}
_IAM_ROLE_FORWARDING_ACTION = "iam:passrole"
_ADMIN_ROLE_WORDS = ("admin", "owner", "global administrator", "root", "superuser", "cluster-admin")


def actions_of(identity: dict[str, Any]) -> list[str]:
    """Flatten the action/scope names an identity carries."""
    actions: list[str] = []
    for name in ("permissions", "actions", "policies", "scopes", "role_permissions"):
        actions.extend(text_list(identity, name))
    return [action.lower() for action in actions]


def has_wildcard(actions: list[str]) -> bool:
    return any(action in {"*", "*:*", "all", "full"} or action.endswith(":*") for action in actions)


def is_privileged(identity: dict[str, Any]) -> bool:
    roles = " ".join(text_list(identity, "role", "roles", "directory_roles")).lower()
    return has_wildcard(actions_of(identity)) or any(word in roles for word in _ADMIN_ROLE_WORDS)


def analyse(resources: list[dict[str, Any]], _edges: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Assess identity entitlements."""
    identities = [resource for resource in resources if resource.get("type") == "identity"]
    findings: list[PostureFinding] = []

    for identity in identities:
        name = resource_name(identity)
        actions = actions_of(identity)
        privileged = is_privileged(identity)
        kind = str(field(identity, "kind", "principal_type", "type_name", default="identity")).lower()

        if has_wildcard(actions):
            findings.append(
                PostureFinding(
                    "CIEM-WILDCARD",
                    "Identity has wildcard permissions",
                    "critical" if privileged else "high",
                    CATEGORY,
                    name,
                    f"Granted actions include a wildcard: {', '.join(sorted({a for a in actions if '*' in a or a == 'all'})) or '*'}.",
                    "Replace wildcards with the specific actions the workload calls, then re-check with access analyser data.",
                )
            )

        if privileged and flag(identity, "service_account", "is_service_account", "workload_identity"):
            findings.append(
                PostureFinding(
                    "CIEM-SERVICE-ADMIN",
                    "Service account holds administrative rights",
                    "critical",
                    CATEGORY,
                    name,
                    "A non-human identity carries an administrative role or wildcard grant.",
                    "Move the workload to a scoped role; keep admin for just-in-time human elevation.",
                )
            )

        if privileged and not flag(identity, "mfa_enabled", "mfa", "strong_auth", default=False):
            findings.append(
                PostureFinding(
                    "CIEM-PRIVILEGED-NO-MFA",
                    "Privileged identity has no strong authentication",
                    "critical",
                    CATEGORY,
                    name,
                    "The identity is administrative but the export reports no MFA or strong authentication.",
                    "Require phishing-resistant MFA for every administrative identity.",
                )
            )

        if _IAM_ROLE_FORWARDING_ACTION in actions and any(action in _ESCALATION_ACTIONS for action in actions):
            findings.append(
                PostureFinding(
                    "CIEM-ESCALATION",
                    "Identity can escalate its own privilege",
                    "critical",
                    CATEGORY,
                    name,
                    "iam:PassRole is combined with an action that can attach or create policy.",
                    "Remove the pair; use permission boundaries and an approval workflow for role changes.",
                )
            )

        age = number(identity, "key_age_days", "credential_age_days")
        if age is not None and age > 90:
            findings.append(
                PostureFinding(
                    "CIEM-LONG-LIVED-KEY",
                    "Long-lived credential on identity",
                    "high" if privileged else "medium",
                    CATEGORY,
                    name,
                    f"The reported credential is {age} days old.",
                    "Move to short-lived federation (OIDC/workload identity) and retire static keys.",
                )
            )

        unused = number(identity, "unused_permissions", "unused_permission_count")
        if unused is not None and unused > 0:
            findings.append(
                PostureFinding(
                    "CIEM-UNUSED-GRANTS",
                    "Identity has unused permissions",
                    "low",
                    CATEGORY,
                    name,
                    f"{unused} granted permissions were unused during the observation window.",
                    "Trim unused grants so a compromised credential reaches less.",
                )
            )

        trusted = " ".join(text_list(identity, "trusted_accounts", "trusted_principals", "assume_role_principals")).lower()
        if "*" in trusted or "any" in trusted:
            findings.append(
                PostureFinding(
                    "CIEM-TRUST-ANYONE",
                    "Identity trusts any principal",
                    "critical",
                    CATEGORY,
                    name,
                    "The trust policy accepts any account or principal.",
                    "Restrict the trust policy to named accounts and require an external ID.",
                )
            )

        if kind in {"ci", "cicd", "pipeline", "build"} and privileged:
            findings.append(
                PostureFinding(
                    "CIEM-CI-ADMIN",
                    "Build pipeline identity is over-privileged",
                    "high",
                    CATEGORY,
                    name,
                    "A CI/CD identity carries administrative or wildcard rights.",
                    "Scope the pipeline role to the artefacts it deploys; use separate roles per environment.",
                )
            )

    return result(
        CATEGORY,
        LABEL,
        findings,
        empty_note="No identity resources were present in the snapshot.",
    )


__all__ = ["CATEGORY", "LABEL", "actions_of", "analyse", "has_wildcard", "is_privileged"]
