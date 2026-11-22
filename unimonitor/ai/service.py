"""Call an AI provider, falling through the list when one is exhausted.

Every provider in ``AI_PROVIDER_ORDER`` with a key is tried in turn. A quota,
rate-limit, auth or availability failure moves to the next model rather than failing
the request, so a free tier running out is invisible to the user except in the
returned provider name. The prompt is built by :mod:`unimonitor.ai.anonymize`, so no
tenant data is sent to any of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from unimonitor.ai.providers import Provider, configured_providers
from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger

logger = get_logger(__name__)

# Statuses that mean "this provider will not serve us now" rather than "the request
# was wrong": quota exhausted (402/403/429), rate limited (429), unavailable (5xx).
JSON_CONTENT = "application/json"

_FAILOVER_STATUS = {401, 402, 403, 404, 408, 409, 425, 429}


class AIUnavailableError(RuntimeError):
    """No provider produced an answer."""


@dataclass
class AIResponse:
    text: str
    provider: str
    model: str
    attempts: list[str] = field(default_factory=list)


def _should_failover(status_code: int) -> bool:
    return status_code in _FAILOVER_STATUS or status_code >= 500


def _openai_request(provider: Provider, system_prompt: str, user_prompt: str, max_tokens: int) -> tuple[str, dict, dict]:
    url = f"{provider.base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {provider.api_key}", "Content-Type": JSON_CONTENT}
    payload = {
        "model": provider.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    return url, headers, payload


def _anthropic_request(provider: Provider, system_prompt: str, user_prompt: str, max_tokens: int) -> tuple[str, dict, dict]:
    url = f"{provider.base_url.rstrip('/')}/messages"
    headers = {
        "x-api-key": provider.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": JSON_CONTENT,
    }
    payload = {
        "model": provider.model,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    return url, headers, payload


def _extract(provider: Provider, body: dict) -> str:
    if provider.kind == "anthropic":
        blocks = body.get("content") or []
        return "".join(str(block.get("text", "")) for block in blocks if isinstance(block, dict))
    return str(body["choices"][0]["message"]["content"])


async def _attempt(
    provider: Provider,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    http: httpx.AsyncClient,
    attempts: list[str],
) -> AIResponse | None:
    """One provider's turn: an answer, or ``None`` when the next one should be tried."""
    build = {"openai": _openai_request, "anthropic": _anthropic_request}[provider.kind]
    url, headers, payload = build(provider, system_prompt, user_prompt, max_tokens)
    try:
        response = await http.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        attempts.append(f"{provider.name}: {type(exc).__name__}")
        logger.warning("ai_provider_unreachable", provider=provider.name, error=str(exc)[:200])
        return None

    if response.status_code >= 400:
        attempts.append(f"{provider.name}: HTTP {response.status_code}")
        if not _should_failover(response.status_code):
            raise AIUnavailableError(f"{provider.name} rejected the request: HTTP {response.status_code}")
        # Quota/limit/auth/outage: the next provider gets the request.
        logger.info("ai_provider_failover", provider=provider.name, status=response.status_code)
        return None

    try:
        text = _extract(provider, response.json())
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        attempts.append(f"{provider.name}: bad response")
        logger.warning("ai_provider_bad_response", provider=provider.name, error=str(exc)[:200])
        return None

    if not text.strip():
        attempts.append(f"{provider.name}: empty answer")
        return None

    logger.info("ai_provider_answered", provider=provider.name, model=provider.model)
    return AIResponse(text=text, provider=provider.name, model=provider.model, attempts=attempts)


async def complete(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 1200,
    providers: list[Provider] | None = None,
    client: httpx.AsyncClient | None = None,
) -> AIResponse:
    """Ask each configured provider in order; the first answer wins."""
    settings = get_settings()
    chain = providers if providers is not None else configured_providers()
    if not chain:
        raise AIUnavailableError("No AI provider is configured")

    attempts: list[str] = []
    owned_client = client is None
    http = client or httpx.AsyncClient(timeout=settings.AI_TIMEOUT_SECONDS)
    try:
        for provider in chain:
            answer = await _attempt(provider, system_prompt, user_prompt, max_tokens, http, attempts)
            if answer is not None:
                return answer
    finally:
        if owned_client:
            await http.aclose()

    raise AIUnavailableError(f"No AI provider answered ({'; '.join(attempts) or 'none configured'})")


async def list_live_models(provider: Provider, client: httpx.AsyncClient | None = None) -> list[str]:
    """Ask an OpenAI-compatible provider which models it currently serves."""
    if provider.kind != "openai":
        return list(provider.models)
    owned = client is None
    http = client or httpx.AsyncClient(timeout=10)
    try:
        response = await http.get(
            f"{provider.base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {provider.api_key}"},
        )
        response.raise_for_status()
        data = response.json().get("data") or []
        return sorted({str(item.get("id")) for item in data if isinstance(item, dict) and item.get("id")})
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        logger.warning("ai_model_list_failed", provider=provider.name, error=str(exc)[:200])
        return list(provider.models)
    finally:
        if owned:
            await http.aclose()


__all__ = ["AIResponse", "AIUnavailableError", "complete", "list_live_models"]
