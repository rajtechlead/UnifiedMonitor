"""AI providers the remediation engine can call, and their model catalogues.

The provider list is ordered by cost: a free-tier provider is exhausted before a paid
one is touched, and the service falls through the list when a provider answers with a
quota, rate-limit or availability error. Keys come from configuration (which reads
the environment), never from the database, so they are not exposed to the tenant UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from unimonitor.config import get_settings


@dataclass(frozen=True)
class Provider:
    """One configured endpoint. ``kind`` selects the request/response shape."""

    name: str
    kind: str  # openai | anthropic | azure
    base_url: str
    model: str
    api_key: str
    free_tier: bool = False
    models: tuple[str, ...] = field(default=())

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url)


# Models known to each provider. The Freebuff catalogue grows often, so it is
# discovered at runtime from its OpenAI-compatible /models endpoint as well.
KNOWN_MODELS: dict[str, tuple[str, ...]] = {
    "freebuff": (
        "gpt-4o-mini",
        "gpt-4o",
        "claude-3-5-sonnet",
        "claude-3-5-haiku",
        "llama-3.3-70b",
    ),
    "openai": ("gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "o4-mini"),
    "anthropic": ("claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-sonnet-4-5"),
    "groq": ("llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"),
    "azure_openai": ("gpt-4o", "gpt-4o-mini"),
}


def configured_providers() -> list[Provider]:
    """Providers that have a key, in the configured failover order."""
    settings = get_settings()
    catalogue = {
        "freebuff": Provider(
            name="freebuff",
            kind="openai",
            base_url=settings.FREEBUFF_BASE_URL,
            model=settings.FREEBUFF_MODEL or (KNOWN_MODELS["freebuff"][0]),
            api_key=settings.FREEBUFF_API_KEY or settings.OPENAI_API_KEY,
            free_tier=True,
            models=KNOWN_MODELS["freebuff"],
        ),
        "openai": Provider(
            name="openai",
            kind="openai",
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            models=KNOWN_MODELS["openai"],
        ),
        "anthropic": Provider(
            name="anthropic",
            kind="anthropic",
            base_url=settings.ANTHROPIC_BASE_URL,
            model=settings.ANTHROPIC_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            models=KNOWN_MODELS["anthropic"],
        ),
        "groq": Provider(
            name="groq",
            kind="openai",
            base_url=settings.GROQ_BASE_URL,
            model=settings.GROQ_MODEL,
            api_key=settings.GROQ_API_KEY,
            free_tier=True,
            models=KNOWN_MODELS["groq"],
        ),
        "azure_openai": Provider(
            name="azure_openai",
            kind="azure",
            base_url=settings.AZURE_OPENAI_ENDPOINT,
            model=settings.AZURE_OPENAI_DEPLOYMENT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            models=KNOWN_MODELS["azure_openai"],
        ),
    }

    order = [name.strip().lower() for name in (settings.AI_PROVIDER_ORDER or "").split(",") if name.strip()]
    return [catalogue[name] for name in order if name in catalogue and catalogue[name].configured]


def provider_status() -> list[dict[str, object]]:
    """Safe description of each provider for the settings API (never the key)."""
    settings = get_settings()
    configured = {provider.name for provider in configured_providers()}
    order = [name.strip().lower() for name in (settings.AI_PROVIDER_ORDER or "").split(",") if name.strip()]
    status: list[dict[str, object]] = []
    for name in order:
        models = KNOWN_MODELS.get(name, ())
        status.append(
            {
                "name": name,
                "configured": name in configured,
                "free_tier": name in {"freebuff", "groq"},
                "models": list(models),
            }
        )
    return status


__all__ = ["KNOWN_MODELS", "Provider", "configured_providers", "provider_status"]
