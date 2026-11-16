"""
Unit tests for unimonitor/core/logging.py and unimonitor/core/cache.py
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# core/logging.py
# ---------------------------------------------------------------------------


class TestCorrelationId:
    def test_get_set_correlation_id(self):
        from unimonitor.core.logging import get_correlation_id, set_correlation_id

        cid = set_correlation_id("test-123")
        assert cid == "test-123"
        assert get_correlation_id() == "test-123"

    def test_set_correlation_id_generates_uuid_when_none(self):
        from unimonitor.core.logging import set_correlation_id

        cid = set_correlation_id(None)
        assert len(cid) == 36  # UUID4 format

    def test_set_correlation_id_generates_uuid_when_empty(self):
        from unimonitor.core.logging import set_correlation_id

        cid = set_correlation_id("")
        assert len(cid) == 36

    def test_add_correlation_id_processor_adds_to_dict(self):
        from unimonitor.core.logging import add_correlation_id, set_correlation_id

        set_correlation_id("cid-456")
        event_dict = {"event": "test"}
        result = add_correlation_id(None, None, event_dict)
        assert result["correlation_id"] == "cid-456"

    def test_add_correlation_id_processor_skips_empty(self):
        from unimonitor.core.logging import _correlation_id, add_correlation_id

        _correlation_id.set("")
        event_dict = {"event": "test"}
        result = add_correlation_id(None, None, event_dict)
        assert "correlation_id" not in result


class TestConfigureLogging:
    def test_configure_logging_dev(self):
        """configure_logging should run without error in dev mode."""
        from unimonitor.core.logging import configure_logging

        with patch("unimonitor.core.logging.get_settings") as mock_settings:
            settings = MagicMock()
            settings.UNIMONITOR_DEBUG = True
            settings.is_production = False
            mock_settings.return_value = settings
            configure_logging()  # should not raise

    def test_configure_logging_production(self):
        """configure_logging should run without error in production mode."""
        from unimonitor.core.logging import configure_logging

        with patch("unimonitor.core.logging.get_settings") as mock_settings:
            settings = MagicMock()
            settings.UNIMONITOR_DEBUG = False
            settings.is_production = True
            mock_settings.return_value = settings
            configure_logging()  # should not raise


class TestGetLogger:
    def test_get_logger_returns_bound_logger(self):
        from unimonitor.core.logging import get_logger

        logger = get_logger("test.module")
        assert logger is not None

    def test_get_audit_logger_singleton(self):
        from unimonitor.core import logging as log_module

        log_module._audit_logger = None
        from unimonitor.core.logging import get_audit_logger

        l1 = get_audit_logger()
        l2 = get_audit_logger()
        assert l1 is l2

    def test_log_audit_event(self):
        """log_audit_event should not raise."""
        _run(
            __import__("unimonitor.core.logging", fromlist=["log_audit_event"]).log_audit_event(
                action="user.login",
                tenant_id="t1",
                user_id="u1",
                resource_type="user",
                resource_id="u1",
                ip_address="1.2.3.4",
            )
        )


# ---------------------------------------------------------------------------
# core/cache.py
# ---------------------------------------------------------------------------


class TestCacheGet:
    def test_cache_get_returns_parsed_json(self):
        import unimonitor.core.cache as cache_mod

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps({"x": 1}))
        cache_mod._redis_client = mock_redis
        result = _run(cache_mod.cache_get("key"))
        assert result == {"x": 1}

    def test_cache_get_returns_none_on_miss(self):
        import unimonitor.core.cache as cache_mod

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        cache_mod._redis_client = mock_redis
        result = _run(cache_mod.cache_get("key"))
        assert result is None

    def test_cache_get_swallows_exception(self):
        import unimonitor.core.cache as cache_mod

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=RuntimeError("conn error"))
        cache_mod._redis_client = mock_redis
        result = _run(cache_mod.cache_get("key"))
        assert result is None


class TestCacheSet:
    def test_cache_set_serialises_and_stores(self):
        import unimonitor.core.cache as cache_mod

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        cache_mod._redis_client = mock_redis
        _run(cache_mod.cache_set("key", {"a": 1}, ttl=60))
        mock_redis.set.assert_awaited_once()
        args = mock_redis.set.call_args
        assert args[0][0] == "key"
        assert json.loads(args[0][1]) == {"a": 1}
        assert args[1]["ex"] == 60

    def test_cache_set_swallows_exception(self):
        import unimonitor.core.cache as cache_mod

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=RuntimeError("conn error"))
        cache_mod._redis_client = mock_redis
        _run(cache_mod.cache_set("key", "value"))  # must not raise


class TestCacheDelete:
    def test_cache_delete_calls_redis(self):
        import unimonitor.core.cache as cache_mod

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        cache_mod._redis_client = mock_redis
        _run(cache_mod.cache_delete("my-key"))
        mock_redis.delete.assert_awaited_once_with("my-key")

    def test_cache_delete_swallows_exception(self):
        import unimonitor.core.cache as cache_mod

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(side_effect=RuntimeError("gone"))
        cache_mod._redis_client = mock_redis
        _run(cache_mod.cache_delete("my-key"))  # must not raise

    def test_cache_delete_pattern_returns_count(self):
        import unimonitor.core.cache as cache_mod

        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=["a", "b"])
        mock_redis.delete = AsyncMock(return_value=2)
        cache_mod._redis_client = mock_redis
        result = _run(cache_mod.cache_delete_pattern("prefix:*"))
        assert result == 2

    def test_cache_delete_pattern_no_keys(self):
        import unimonitor.core.cache as cache_mod

        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        cache_mod._redis_client = mock_redis
        result = _run(cache_mod.cache_delete_pattern("prefix:*"))
        assert result == 0

    def test_cache_delete_pattern_swallows_exception(self):
        import unimonitor.core.cache as cache_mod

        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(side_effect=RuntimeError("gone"))
        cache_mod._redis_client = mock_redis
        result = _run(cache_mod.cache_delete_pattern("prefix:*"))
        assert result == 0


class TestCacheKeyHelpers:
    def test_make_graph_cache_key(self):
        from unimonitor.core.cache import make_graph_cache_key

        key = make_graph_cache_key("t1", "/v1.0/users")
        assert key.startswith("graph:t1:")
        assert "/" not in key.split(":", 2)[2]

    def test_make_assessment_cache_key(self):
        from unimonitor.core.cache import make_assessment_cache_key

        key = make_assessment_cache_key("t1", "run-001")
        assert key == "assessment:t1:run-001"

    def test_make_dashboard_cache_key(self):
        from unimonitor.core.cache import make_dashboard_cache_key

        key = make_dashboard_cache_key("t1", "overview")
        assert key == "dashboard:t1:overview"


class TestCacheLifecycle:
    def test_init_cache_is_noop(self):
        from unimonitor.core.cache import init_cache

        _run(init_cache())  # no error

    def test_close_cache(self):
        import unimonitor.core.cache as cache_mod

        mock_redis = AsyncMock()
        mock_redis.close = AsyncMock()
        cache_mod._redis_client = mock_redis
        _run(cache_mod.close_cache())
        mock_redis.close.assert_awaited_once()

    def test_close_cache_swallows_exception(self):
        import unimonitor.core.cache as cache_mod

        mock_redis = AsyncMock()
        mock_redis.close = AsyncMock(side_effect=RuntimeError("gone"))
        cache_mod._redis_client = mock_redis
        _run(cache_mod.close_cache())  # must not raise
