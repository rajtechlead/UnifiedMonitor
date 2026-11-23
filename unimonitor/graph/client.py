"""Async Microsoft Graph API client with rate limiting, retry and caching."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from unimonitor.auth.oauth import acquire_token_for_client
from unimonitor.config import get_settings
from unimonitor.core.cache import cache_get, cache_set, make_graph_cache_key
from unimonitor.core.logging import get_logger
from unimonitor.exceptions import (
    GraphAPIError,
    GraphPermissionError,
    GraphRateLimitError,
    GraphTimeoutError,
)

logger = get_logger(__name__)

JSON_CONTENT_TYPE = "application/json"

# How long the last successful response is kept so an outage can be answered
# with the data of the previous run instead of with nothing.
LAST_GOOD_TTL = 7 * 24 * 3600


def last_good_cache_key(cache_key: str) -> str:
    """Key holding the most recent successful body for an endpoint."""
    return f"{cache_key}:last-good"


@dataclass
class GraphResponse:
    data: Any
    success: bool
    error_code: str | None = None
    error_message: str | None = None
    endpoint: str | None = None
    cached: bool = False
    # True when the body came from the last successful response because Graph
    # could not be reached now. Never a fresh result.
    stale: bool = False

    @property
    def usable(self) -> bool:
        """True when the response carries data the caller may evaluate.

        A stale response is not a fresh answer, but dropping it would turn a
        Graph outage into missing evidence for every control that reads it.
        """
        return self.success or self.stale


def classify_error(exc: Exception) -> str:
    """``consent`` or ``outage`` for a Graph failure.

    A consent problem needs an administrator to grant a permission; an outage only
    needs time, and may be answered from the last good response.
    """
    from unimonitor.exceptions import AuthenticationError, GraphPermissionError

    return "consent" if isinstance(exc, (GraphPermissionError, AuthenticationError)) else "outage"


class RateLimiter:
    """Token bucket rate limiter for Graph API calls."""

    def __init__(self, rate: float = 5.0) -> None:
        self.rate = rate
        self._tokens = rate
        self._last_check = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_check
            self._last_check = now
            self._tokens = min(self.rate, self._tokens + elapsed * self.rate)
            if self._tokens < 1:
                sleep_for = (1 - self._tokens) / self.rate
                await asyncio.sleep(sleep_for)
                self._tokens = 0
            else:
                self._tokens -= 1


class GraphClient:
    """
    Async Graph API client wrapping httpx with:
    - Client credentials token acquisition
    - Rate limiting (token bucket)
    - Automatic retry with exponential backoff
    - Redis response caching
    - Pagination handling
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        cache_ttl: int = 3600,
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.cache_ttl = cache_ttl
        settings = get_settings()
        self.base_url = settings.graph_base_url
        self._rate_limiter = RateLimiter(settings.GRAPH_RATE_LIMIT_PER_SECOND)
        self._semaphore = asyncio.Semaphore(settings.GRAPH_MAX_CONCURRENT)
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._http_client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> GraphClient:
        self._http_client = httpx.AsyncClient(
            timeout=get_settings().GRAPH_REQUEST_TIMEOUT,
            http2=True,
        )
        return self

    async def __aexit__(self, *args) -> None:
        if self._http_client:
            await self._http_client.aclose()

    async def _ensure_token(self) -> str:
        """Acquire or refresh access token."""
        now = time.monotonic()
        if self._token and now < self._token_expiry - 60:
            return self._token
        self._token = await acquire_token_for_client(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        self._token_expiry = now + 3600
        return self._token

    async def get(
        self,
        endpoint: str,
        *,
        params: dict | None = None,
        use_cache: bool = True,
        cache_ttl: int | None = None,
    ) -> GraphResponse:
        """Execute a GET request to the Graph API."""
        cache_key = make_graph_cache_key(self.tenant_id, endpoint)

        if use_cache:
            cached = await cache_get(cache_key)
            if cached is not None:
                return GraphResponse(data=cached, success=True, endpoint=endpoint, cached=True)

        async with self._semaphore:
            await self._rate_limiter.acquire()
            try:
                return await self._execute_get(endpoint, params=params, cache_key=cache_key, cache_ttl=cache_ttl)
            except GraphTimeoutError as exc:
                return await self._last_good(cache_key, endpoint, exc)
            except GraphAPIError as exc:
                from unimonitor.exceptions import GraphPermissionError

                upstream_status = getattr(exc, "upstream_status", None)
                if isinstance(exc, GraphPermissionError) or (upstream_status is not None and upstream_status < 500):
                    # A revoked permission or a bad request is not an outage; stale
                    # data would hide something an administrator must fix.
                    raise
                return await self._last_good(cache_key, endpoint, exc)

    async def _last_good(self, cache_key: str, endpoint: str, exc: Exception) -> GraphResponse:
        """Answer an outage from the last successful response, or re-raise."""
        last_good = await cache_get(last_good_cache_key(cache_key))
        if last_good is None:
            raise exc
        logger.warning("Graph API unavailable; using last good response", endpoint=endpoint, error=str(exc))
        message = getattr(exc, "message", str(exc))[:200]
        return GraphResponse(
            data=last_good,
            success=False,
            cached=True,
            stale=True,
            endpoint=endpoint,
            error_code="GRAPH_UNAVAILABLE",
            error_message=f"{message} — showing the last successful response",
        )

    @retry(
        retry=retry_if_exception_type(GraphRateLimitError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True,
    )
    async def _execute_get(
        self,
        endpoint: str,
        *,
        params: dict | None = None,
        cache_key: str | None = None,
        cache_ttl: int | None = None,
    ) -> GraphResponse:
        token = await self._ensure_token()
        url = f"{self.base_url}{endpoint}" if not endpoint.startswith("http") else endpoint
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": JSON_CONTENT_TYPE,
            "Accept": JSON_CONTENT_TYPE,
        }
        try:
            resp = await self._http_client.get(url, headers=headers, params=params)
        except httpx.TimeoutException as exc:
            raise GraphTimeoutError(f"Graph API timed out for {endpoint}") from exc
        except httpx.HTTPError as exc:
            raise GraphAPIError(f"Graph API HTTP error for {endpoint}: {exc}") from exc

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "10"))
            logger.warning("Graph API rate limited", endpoint=endpoint, retry_after=retry_after)
            await asyncio.sleep(retry_after)
            raise GraphRateLimitError(f"Rate limited on {endpoint}")

        if resp.status_code == 403:
            raise GraphPermissionError(
                f"Insufficient permissions for {endpoint}",
                detail=resp.text[:500],
            )

        if resp.status_code == 401:
            self._token = None  # Force token refresh
            from unimonitor.exceptions import AuthenticationError

            raise AuthenticationError(f"Unauthorised accessing {endpoint}")

        if not resp.is_success:
            error = GraphAPIError(
                f"Graph API error {resp.status_code} for {endpoint}",
                detail=resp.text[:500],
            )
            error.upstream_status = resp.status_code
            raise error

        data = resp.json()
        result_data = data.get("value", data)

        if cache_key:
            await cache_set(cache_key, result_data, ttl=cache_ttl or self.cache_ttl)
            await cache_set(last_good_cache_key(cache_key), result_data, ttl=LAST_GOOD_TTL)

        return GraphResponse(data=result_data, success=True, endpoint=endpoint)

    async def get_all_pages(
        self,
        endpoint: str,
        *,
        params: dict | None = None,
        max_pages: int = 50,
    ) -> list[dict]:
        """Retrieve all pages of a paginated Graph API response."""
        all_items: list[dict] = []
        url: str | None = endpoint
        page_count = 0

        token = await self._ensure_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": JSON_CONTENT_TYPE,
        }

        while url and page_count < max_pages:
            full_url = f"{self.base_url}{url}" if not url.startswith("http") else url
            try:
                resp = await self._http_client.get(full_url, headers=headers, params=params if page_count == 0 else None)
                resp.raise_for_status()
                data = resp.json()
                items = data.get("value", [])
                all_items.extend(items)
                url = data.get("@odata.nextLink")
                page_count += 1
                params = None  # Only use params on first page
            except httpx.HTTPStatusError as exc:
                logger.error("Graph pagination error", endpoint=endpoint, status=exc.response.status_code)
                break

        return all_items

    async def batch_get(self, endpoints: list[str]) -> list[GraphResponse]:
        """Execute multiple GET requests concurrently."""
        tasks = [self.get(ep) for ep in endpoints]
        return await asyncio.gather(*tasks, return_exceptions=False)
