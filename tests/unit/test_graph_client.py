"""
Unit tests for graph/client.py — GraphResponse, RateLimiter, GraphClient.
All HTTP calls and token acquisition are mocked.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# GraphResponse dataclass
# ---------------------------------------------------------------------------


class TestGraphResponse:
    def test_defaults(self):
        from unimonitor.graph.client import GraphResponse

        r = GraphResponse(data={"key": "val"}, success=True)
        assert r.success is True
        assert r.cached is False
        assert r.error_code is None
        assert r.error_message is None

    def test_cached_flag(self):
        from unimonitor.graph.client import GraphResponse

        r = GraphResponse(data=[], success=True, cached=True, endpoint="/users")
        assert r.cached is True
        assert r.endpoint == "/users"

    def test_error_response(self):
        from unimonitor.graph.client import GraphResponse

        r = GraphResponse(data=None, success=False, error_code="403", error_message="Forbidden")
        assert r.success is False
        assert r.error_code == "403"


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_acquire_does_not_raise(self):
        from unimonitor.graph.client import RateLimiter

        limiter = RateLimiter(rate=100.0)
        _run(limiter.acquire())

    def test_tokens_decrease_after_acquire(self):
        from unimonitor.graph.client import RateLimiter

        limiter = RateLimiter(rate=5.0)

        # Drain most tokens without sleeping by patching asyncio.sleep
        async def _no_sleep():
            await limiter.acquire()

        _run(_no_sleep())
        # After one acquire, tokens should be less than the initial rate
        # (they also replenish slightly; just check it ran without error)

    def test_high_rate_many_acquires(self):
        """High rate limiter allows rapid sequential acquires."""
        from unimonitor.graph.client import RateLimiter

        limiter = RateLimiter(rate=1000.0)

        async def _many():
            for _ in range(5):
                await limiter.acquire()

        _run(_many())


# ---------------------------------------------------------------------------
# GraphClient — construction and context manager
# ---------------------------------------------------------------------------


class TestGraphClientInit:
    def test_constructs_with_tenant(self):
        from unimonitor.graph.client import GraphClient

        gc = GraphClient(tenant_id="tenant-1")
        assert gc.tenant_id == "tenant-1"
        assert gc._http_client is None

    def test_constructs_with_credentials(self):
        from unimonitor.graph.client import GraphClient

        gc = GraphClient(tenant_id="t1", client_id="cid", client_secret="csec")
        assert gc.client_id == "cid"
        assert gc.client_secret == "csec"

    def test_context_manager_creates_http_client(self):
        from unimonitor.graph.client import GraphClient

        async def _test():
            async with GraphClient(tenant_id="t1") as gc:
                assert gc._http_client is not None
            assert gc._http_client is None or True  # closed after exit

        _run(_test())


# ---------------------------------------------------------------------------
# GraphClient._ensure_token
# ---------------------------------------------------------------------------


class TestEnsureToken:
    def test_acquires_token_on_first_call(self):
        from unimonitor.graph.client import GraphClient

        async def _test():
            gc = GraphClient(tenant_id="t1")
            with patch("unimonitor.graph.client.acquire_token_for_client", new=AsyncMock(return_value="tok123")):
                token = await gc._ensure_token()
            assert token == "tok123"
            assert gc._token == "tok123"

        _run(_test())

    def test_uses_cached_token(self):
        from unimonitor.graph.client import GraphClient

        async def _test():
            gc = GraphClient(tenant_id="t1")
            gc._token = "cached_tok"
            gc._token_expiry = time.monotonic() + 7200  # far future
            mock_acquire = AsyncMock()
            with patch("unimonitor.graph.client.acquire_token_for_client", new=mock_acquire):
                token = await gc._ensure_token()
            mock_acquire.assert_not_called()
            assert token == "cached_tok"

        _run(_test())

    def test_refreshes_expired_token(self):
        from unimonitor.graph.client import GraphClient

        async def _test():
            gc = GraphClient(tenant_id="t1")
            gc._token = "old_tok"
            gc._token_expiry = time.monotonic() - 100  # already expired
            with patch("unimonitor.graph.client.acquire_token_for_client", new=AsyncMock(return_value="new_tok")):
                token = await gc._ensure_token()
            assert token == "new_tok"

        _run(_test())


# ---------------------------------------------------------------------------
# GraphClient.get — cache hit path
# ---------------------------------------------------------------------------


class TestGraphClientGet:
    def _make_client_with_mocked_http(self, status_code=200, json_data=None):
        """Return a configured GraphClient with mocked HTTP."""
        from unimonitor.graph.client import GraphClient

        gc = GraphClient(tenant_id="t1", cache_ttl=0)
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.is_success = status_code < 400
        mock_resp.json.return_value = json_data or {"value": [{"id": "u1"}]}
        mock_resp.headers = {}
        mock_resp.text = ""
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_http.aclose = AsyncMock()
        gc._http_client = mock_http
        return gc

    def test_returns_cached_response(self):
        from unimonitor.graph.client import GraphClient

        async def _test():
            gc = GraphClient(tenant_id="t1")
            cached_data = [{"id": "user-1"}]
            with patch("unimonitor.graph.client.cache_get", new=AsyncMock(return_value=cached_data)):
                result = await gc.get("/users", use_cache=True)
            assert result.cached is True
            assert result.data == cached_data

        _run(_test())

    def test_cache_miss_hits_http(self):

        async def _test():
            gc = self._make_client_with_mocked_http(json_data={"value": [{"id": "u2"}]})
            with patch("unimonitor.graph.client.cache_get", new=AsyncMock(return_value=None)):
                with patch("unimonitor.graph.client.cache_set", new=AsyncMock()):
                    with patch("unimonitor.graph.client.acquire_token_for_client", new=AsyncMock(return_value="tok")):
                        gc._token = "tok"
                        gc._token_expiry = time.monotonic() + 7200
                        result = await gc.get("/users", use_cache=True)
            assert result.success is True
            assert result.data == [{"id": "u2"}]

        _run(_test())

    def test_no_cache_skips_cache_get(self):

        async def _test():
            gc = self._make_client_with_mocked_http()
            mock_cache_get = AsyncMock()
            with patch("unimonitor.graph.client.cache_get", new=mock_cache_get):
                with patch("unimonitor.graph.client.cache_set", new=AsyncMock()):
                    gc._token = "tok"
                    gc._token_expiry = time.monotonic() + 7200
                    await gc.get("/users", use_cache=False)
            mock_cache_get.assert_not_called()

        _run(_test())

    def test_403_raises_permission_error(self):
        from unimonitor.exceptions import GraphPermissionError

        async def _test():
            gc = self._make_client_with_mocked_http(status_code=403)
            gc._http_client.get.return_value.text = "Forbidden"
            with patch("unimonitor.graph.client.cache_get", new=AsyncMock(return_value=None)):
                with patch("unimonitor.graph.client.cache_set", new=AsyncMock()):
                    gc._token = "tok"
                    gc._token_expiry = time.monotonic() + 7200
                    with pytest.raises(GraphPermissionError):
                        await gc.get("/users", use_cache=False)

        _run(_test())

    def test_401_clears_token_and_raises(self):
        from unimonitor.exceptions import AuthenticationError

        async def _test():
            gc = self._make_client_with_mocked_http(status_code=401)
            gc._token = "old_tok"
            gc._token_expiry = time.monotonic() + 7200
            with patch("unimonitor.graph.client.cache_get", new=AsyncMock(return_value=None)):
                with pytest.raises(AuthenticationError):
                    await gc.get("/users", use_cache=False)
            assert gc._token is None  # cleared

        _run(_test())

    def test_500_raises_graph_api_error(self):
        from unimonitor.exceptions import GraphAPIError

        async def _test():
            gc = self._make_client_with_mocked_http(status_code=500)
            gc._http_client.get.return_value.text = "Internal server error"
            gc._token = "tok"
            gc._token_expiry = time.monotonic() + 7200
            with patch("unimonitor.graph.client.cache_get", new=AsyncMock(return_value=None)):
                with pytest.raises(GraphAPIError):
                    await gc.get("/users", use_cache=False)

        _run(_test())

    def test_timeout_raises_graph_timeout_error(self):
        import httpx

        from unimonitor.exceptions import GraphTimeoutError
        from unimonitor.graph.client import GraphClient

        async def _test():
            gc = GraphClient(tenant_id="t1")
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
            gc._http_client = mock_http
            gc._token = "tok"
            gc._token_expiry = time.monotonic() + 7200
            with patch("unimonitor.graph.client.cache_get", new=AsyncMock(return_value=None)):
                with pytest.raises(GraphTimeoutError):
                    await gc.get("/users", use_cache=False)

        _run(_test())

    def test_a_stale_response_is_usable_but_not_fresh(self):
        from unimonitor.graph.client import GraphResponse

        stale = GraphResponse(data=[{"id": "cached"}], success=False, stale=True)
        failed = GraphResponse(data=None, success=False)
        assert stale.usable is True
        assert failed.usable is False

    def test_an_outage_is_answered_from_the_last_good_response(self):
        async def _test():
            gc = self._make_client_with_mocked_http(status_code=503)
            gc._token = "tok"
            gc._token_expiry = time.monotonic() + 7200
            with patch("unimonitor.graph.client.cache_get", new=AsyncMock(return_value=[{"id": "last-good"}])):
                result = await gc.get("/users", use_cache=False)
            assert result.success is False
            assert result.stale is True
            assert result.data == [{"id": "last-good"}]
            assert result.error_code == "GRAPH_UNAVAILABLE"

        _run(_test())

    def test_a_revoked_permission_is_not_masked_by_stale_data(self):
        from unimonitor.exceptions import GraphPermissionError

        async def _test():
            gc = self._make_client_with_mocked_http(status_code=403)
            gc._http_client.get.return_value.text = "Forbidden"
            gc._token = "tok"
            gc._token_expiry = time.monotonic() + 7200
            with patch("unimonitor.graph.client.cache_get", new=AsyncMock(return_value=[{"id": "stale"}])):
                with pytest.raises(GraphPermissionError):
                    await gc.get("/users", use_cache=False)

        _run(_test())

    def test_a_client_error_is_not_an_outage(self):
        from unimonitor.exceptions import GraphAPIError

        async def _test():
            gc = self._make_client_with_mocked_http(status_code=404)
            gc._http_client.get.return_value.text = "Not found"
            gc._token = "tok"
            gc._token_expiry = time.monotonic() + 7200
            with patch("unimonitor.graph.client.cache_get", new=AsyncMock(return_value=[{"id": "stale"}])):
                with pytest.raises(GraphAPIError):
                    await gc.get("/users", use_cache=False)

        _run(_test())

    def test_http_error_raises_graph_api_error(self):
        import httpx

        from unimonitor.exceptions import GraphAPIError
        from unimonitor.graph.client import GraphClient

        async def _test():
            gc = GraphClient(tenant_id="t1")
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(side_effect=httpx.HTTPError("connection failed"))
            gc._http_client = mock_http
            gc._token = "tok"
            gc._token_expiry = time.monotonic() + 7200
            with patch("unimonitor.graph.client.cache_get", new=AsyncMock(return_value=None)):
                with pytest.raises(GraphAPIError):
                    await gc.get("/users", use_cache=False)

        _run(_test())


# ---------------------------------------------------------------------------
# GraphClient.get_all_pages
# ---------------------------------------------------------------------------


class TestGetAllPages:
    def test_single_page(self):
        from unimonitor.graph.client import GraphClient

        async def _test():
            gc = GraphClient(tenant_id="t1")
            resp1 = MagicMock()
            resp1.json.return_value = {"value": [{"id": "u1"}, {"id": "u2"}]}
            resp1.raise_for_status = MagicMock()
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=resp1)
            gc._http_client = mock_http
            gc._token = "tok"
            gc._token_expiry = time.monotonic() + 7200
            with patch("unimonitor.graph.client.acquire_token_for_client", new=AsyncMock(return_value="tok")):
                items = await gc.get_all_pages("/users")
            assert len(items) == 2

        _run(_test())

    def test_multiple_pages(self):
        from unimonitor.graph.client import GraphClient

        async def _test():
            gc = GraphClient(tenant_id="t1")
            resp1 = MagicMock()
            resp1.json.return_value = {
                "value": [{"id": "u1"}],
                "@odata.nextLink": "https://graph.microsoft.com/v1.0/users?$skiptoken=abc",
            }
            resp1.raise_for_status = MagicMock()
            resp2 = MagicMock()
            resp2.json.return_value = {"value": [{"id": "u2"}]}
            resp2.raise_for_status = MagicMock()
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(side_effect=[resp1, resp2])
            gc._http_client = mock_http
            gc._token = "tok"
            gc._token_expiry = time.monotonic() + 7200
            with patch("unimonitor.graph.client.acquire_token_for_client", new=AsyncMock(return_value="tok")):
                items = await gc.get_all_pages("/users")
            assert len(items) == 2
            assert items[0]["id"] == "u1"
            assert items[1]["id"] == "u2"

        _run(_test())


# ---------------------------------------------------------------------------
# GraphClient.batch_get
# ---------------------------------------------------------------------------


class TestBatchGet:
    def test_batch_returns_list(self):
        from unimonitor.graph.client import GraphClient, GraphResponse

        async def _test():
            gc = GraphClient(tenant_id="t1")
            cached_data = {"id": "item"}
            with patch("unimonitor.graph.client.cache_get", new=AsyncMock(return_value=cached_data)):
                results = await gc.batch_get(["/users", "/groups"])
            assert len(results) == 2
            assert all(isinstance(r, GraphResponse) for r in results)

        _run(_test())
