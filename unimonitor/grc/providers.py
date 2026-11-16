"""Cloud provider registry.

UniMonitor monitors several cloud platforms, not just Microsoft 365. A *provider*
owns a set of control-library ``service`` values; findings and controls carry
``service``, so provider roll-ups are a pure grouping operation over the existing
control library and findings table.

Adding a provider is a one-line change here plus its ``controls/<provider>/``
directory: the dashboards, collector list and coverage maths all read this map.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CloudProvider:
    """A monitored cloud platform."""

    id: str
    name: str
    short_name: str
    description: str
    services: tuple[str, ...]
    collectors: tuple[str, ...]
    # Settings that must be present before live data can be collected.
    credential_settings: tuple[str, ...] = ()


PROVIDERS: dict[str, CloudProvider] = {
    "microsoft": CloudProvider(
        id="microsoft",
        name="Microsoft 365",
        short_name="M365",
        description="Entra ID, Intune, Defender, Purview, Exchange, SharePoint, Teams and Copilot",
        services=(
            "entra_id",
            "intune",
            "defender",
            "defender_office",
            "defender_identity",
            "defender_cloud_apps",
            "purview",
            "purview_insider_risk",
            "purview_ediscovery",
            "exchange",
            "sharepoint",
            "teams",
            "copilot_m365",
            "copilot_studio",
        ),
        collectors=(
            "entra_id",
            "intune",
            "defender",
            "purview",
            "exchange",
            "sharepoint",
            "teams",
            "copilot",
            "secure_score",
            "azure_security",
        ),
        credential_settings=("TENANT_CLIENT_ID", "TENANT_CLIENT_SECRET"),
    ),
    "aws": CloudProvider(
        id="aws",
        name="Amazon Web Services",
        short_name="AWS",
        description="IAM, S3, CloudTrail, GuardDuty, AWS Config and Security Hub",
        services=("aws",),
        collectors=("aws",),
        credential_settings=("AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"),
    ),
    "gcp": CloudProvider(
        id="gcp",
        name="Google Cloud Platform",
        short_name="GCP",
        description="Cloud IAM, service accounts, firewall rules, audit sinks, buckets, KMS and org policy",
        services=("gcp",),
        collectors=("gcp",),
        credential_settings=("GCP_PROJECT_ID", "GCP_ACCESS_TOKEN"),
    ),
    "google_workspace": CloudProvider(
        id="google_workspace",
        name="Google Workspace",
        short_name="Workspace",
        description="Admin roles, 2-step verification, OAuth grants, Drive sharing and mobile devices",
        services=("google_workspace",),
        collectors=("google_workspace",),
        credential_settings=("GOOGLE_WORKSPACE_CUSTOMER_ID", "GOOGLE_ACCESS_TOKEN"),
    ),
}

# Accepted spellings for URL paths and query parameters.
PROVIDER_ALIASES: dict[str, str] = {
    "microsoft": "microsoft",
    "microsoft365": "microsoft",
    "microsoft_365": "microsoft",
    "m365": "microsoft",
    "office365": "microsoft",
    "aws": "aws",
    "amazon": "aws",
    "amazon_web_services": "aws",
    "gcp": "gcp",
    "google": "gcp",
    "google_cloud": "gcp",
    "googlecloud": "gcp",
    "google_workspace": "google_workspace",
    "googleworkspace": "google_workspace",
    "workspace": "google_workspace",
    "gws": "google_workspace",
}


def get_provider(provider_id: str | None) -> CloudProvider | None:
    """Resolve a provider by id or alias (case-insensitive)."""
    if not provider_id:
        return None
    key = provider_id.strip().lower().replace("-", "_")
    return PROVIDERS.get(PROVIDER_ALIASES.get(key, key))


def provider_for_service(service: str | None) -> CloudProvider | None:
    """Return the provider that owns a control/finding ``service`` value."""
    if not service:
        return None
    normalised = service.strip().lower()
    for provider in PROVIDERS.values():
        if normalised in provider.services:
            return provider
    # Sub-service names such as ``defender_office_365`` fall back to their prefix.
    for provider in PROVIDERS.values():
        for known in provider.services:
            if normalised.startswith(known):
                return provider
    return None


def provider_ids() -> list[str]:
    return list(PROVIDERS)
