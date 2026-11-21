"""AI security posture management (AI-SPM).

Covers the deployments a modern tenant actually runs: Copilot agents, Power
Platform connectors, model endpoints and their identities. The engine reports
exposure and control gaps from what the snapshot states; it does not infer model
quality or safety from a name.
"""

from __future__ import annotations

from typing import Any

from unimonitor.posture.findings import PostureFinding, resource_name, result
from unimonitor.posture.inventory import field, flag, text_list

CATEGORY = "aispm"
LABEL = "AI security posture"

# Scopes that let an agent read or send organisational content on its own.
_BROAD_SCOPES = {
    "mail.readwrite",
    "mail.send",
    "files.readwrite.all",
    "sites.fullcontrol.all",
    "directory.readwrite.all",
    "chat.readwrite",
    "*.readwrite.all",
}
# Tools that turn a prompt injection into a real-world action.
_ACTION_TOOLS = ("send_email", "send_mail", "delete", "execute", "run_command", "write_file", "create_ticket", "post_message")


def _scopes(deployment: dict[str, Any]) -> list[str]:
    scopes: list[str] = []
    for name in ("scopes", "permissions", "graph_permissions", "oauth_scopes"):
        scopes.extend(text_list(deployment, name))
    return [scope.lower() for scope in scopes]


def _broad_scopes(scopes: list[str]) -> list[str]:
    return [scope for scope in scopes if scope in _BROAD_SCOPES or scope.endswith("readwrite.all") or "*" in scope]


def analyse(resources: list[dict[str, Any]], _edges: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Assess AI deployments and agents."""
    deployments = [resource for resource in resources if resource.get("type") == "ai_deployment"]
    findings: list[PostureFinding] = []

    for deployment in deployments:
        name = resource_name(deployment)
        public = flag(deployment, "public", "public_endpoint", "internet_exposed", "externally_accessible")
        auth = str(field(deployment, "authentication", "auth_type", "auth", default="")).lower()
        unauthenticated = auth in {"none", "anonymous", "disabled", "open"} or flag(deployment, "anonymous_access", "allow_anonymous")

        if public:
            findings.append(
                PostureFinding(
                    "AISPM-PUBLIC-ENDPOINT",
                    "AI endpoint is reachable from the internet",
                    "high",
                    CATEGORY,
                    name,
                    "The deployment is marked public.",
                    "Put the endpoint behind the gateway/VNet and require authenticated callers.",
                )
            )

        if unauthenticated:
            findings.append(
                PostureFinding(
                    "AISPM-NO-AUTH",
                    "AI deployment accepts unauthenticated callers",
                    "critical" if public else "high",
                    CATEGORY,
                    name,
                    "Authentication is disabled or anonymous access is allowed.",
                    "Require an authenticated identity per caller and scope each one separately.",
                )
            )

        if flag(deployment, "trains_on_data", "uses_customer_data", "training_on_tenant_data", "data_used_for_training"):
            findings.append(
                PostureFinding(
                    "AISPM-TRAINS-ON-DATA",
                    "Tenant data is used to train the model",
                    "high",
                    CATEGORY,
                    name,
                    "The export states that customer data is used for model training.",
                    "Turn off training on tenant data and confirm the contractual data-use terms.",
                )
            )

        for scope in _broad_scopes(_scopes(deployment)):
            findings.append(
                PostureFinding(
                    "AISPM-BROAD-SCOPE",
                    "AI agent holds a broad permission",
                    "high",
                    CATEGORY,
                    name,
                    f"Scope {scope!r} allows the agent to read or change content on its own.",
                    "Grant read-only, resource-scoped permissions and require user consent for writes.",
                )
            )
            break

        if field(deployment, "content_filtering", "guardrails", "prompt_shields") is not None and not flag(
            deployment, "content_filtering", "guardrails", "prompt_shields"
        ):
            findings.append(
                PostureFinding(
                    "AISPM-NO-CONTENT-FILTER",
                    "AI deployment has no content filtering",
                    "high",
                    CATEGORY,
                    name,
                    "Prompt shields/content filtering are reported as disabled.",
                    "Enable the platform's prompt-injection and harmful-content filters.",
                )
            )

        if field(deployment, "logging", "audit_logging", "activity_logging") is not None and not flag(
            deployment, "logging", "audit_logging", "activity_logging"
        ):
            findings.append(
                PostureFinding(
                    "AISPM-NO-LOGGING",
                    "AI interactions are not logged",
                    "medium",
                    CATEGORY,
                    name,
                    "Interaction logging is reported as disabled.",
                    "Log prompts, tool calls and data accesses to the SIEM with the invoking user.",
                )
            )

        tools = {tool.lower() for tool in text_list(deployment, "tools", "actions", "plugins")}
        dangerous = sorted(tools.intersection(_ACTION_TOOLS))
        if dangerous:
            findings.append(
                PostureFinding(
                    "AISPM-ACTION-TOOLS",
                    "AI agent can perform write actions",
                    "medium" if not unauthenticated else "high",
                    CATEGORY,
                    name,
                    f"Tools available: {', '.join(dangerous)}.",
                    "Require human approval for write/send actions and limit the tools to what the use case needs.",
                )
            )

        if not field(deployment, "model_version", "version"):
            findings.append(
                PostureFinding(
                    "AISPM-UNPINNED-MODEL",
                    "AI deployment does not pin a model version",
                    "low",
                    CATEGORY,
                    name,
                    "No model version is recorded, so behaviour can change silently.",
                    "Pin the model version and review upgrades before rollout.",
                )
            )

    return result(
        CATEGORY,
        LABEL,
        findings,
        empty_note="No AI deployments were present in the snapshot.",
    )


__all__ = ["CATEGORY", "LABEL", "analyse"]
