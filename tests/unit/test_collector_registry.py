"""
Unit tests for graph/collector_registry.py

Tests CollectorRegistry.collect_all, _run_collector,
_safe_get, and all individual _collect_* functions.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_gc(success=True, data=None):
    """Create a mock GraphClient with configurable responses."""
    gc = MagicMock()
    if success:
        resp = MagicMock()
        resp.success = True
        resp.usable = True
        resp.stale = False
        resp.data = data or {"value": []}
        gc.get = AsyncMock(return_value=resp)
    else:
        gc.get = AsyncMock(side_effect=RuntimeError("Graph error"))
    return gc


# ---------------------------------------------------------------------------
# _safe_get
# ---------------------------------------------------------------------------


class TestSafeGet:
    def test_success_returns_key_data(self):
        from unimonitor.graph.collector_registry import _safe_get

        gc = _make_gc(success=True, data={"value": ["item"]})
        result = _run(_safe_get(gc, "/some/endpoint", "myKey"))
        assert result == {"myKey": {"value": ["item"]}}

    def test_failure_response_returns_empty(self):
        from unimonitor.graph.collector_registry import _safe_get

        gc = MagicMock()
        resp = MagicMock()
        resp.success = False
        resp.usable = False
        resp.stale = False
        gc.get = AsyncMock(return_value=resp)
        result = _run(_safe_get(gc, "/endpoint", "myKey"))
        assert result == {}

    def test_stale_response_still_returns_key_data(self):
        """A Graph outage answered from last-good data is evidence, not a gap."""
        from unimonitor.graph.collector_registry import _safe_get

        gc = MagicMock()
        resp = MagicMock()
        resp.success = False
        resp.usable = True
        resp.stale = True
        resp.data = {"value": ["cached"]}
        gc.get = AsyncMock(return_value=resp)
        result = _run(_safe_get(gc, "/endpoint", "myKey"))
        assert result == {"myKey": {"value": ["cached"]}}

    def test_exception_returns_empty(self):
        from unimonitor.graph.collector_registry import _safe_get

        gc = MagicMock()
        gc.get = AsyncMock(side_effect=RuntimeError("Network error"))
        result = _run(_safe_get(gc, "/endpoint", "myKey"))
        assert result == {}


# ---------------------------------------------------------------------------
# Individual collectors (_collect_* functions)
# ---------------------------------------------------------------------------


class TestIndividualCollectors:
    def _run_collector(self, collector_fn, success=True, data=None):
        gc = _make_gc(success=success, data=data)
        return _run(collector_fn(gc))

    def test_collect_entra_id_returns_dict(self):
        from unimonitor.graph.collector_registry import _collect_entra_id

        result = self._run_collector(_collect_entra_id)
        assert isinstance(result, dict)

    def test_collect_intune_returns_dict(self):
        from unimonitor.graph.collector_registry import _collect_intune

        result = self._run_collector(_collect_intune)
        assert isinstance(result, dict)

    def test_collect_defender_returns_dict(self):
        from unimonitor.graph.collector_registry import _collect_defender

        result = self._run_collector(_collect_defender)
        assert isinstance(result, dict)

    def test_collect_purview_returns_dict(self):
        from unimonitor.graph.collector_registry import _collect_purview

        result = self._run_collector(_collect_purview)
        assert isinstance(result, dict)

    def test_collect_exchange_returns_dict(self):
        from unimonitor.graph.collector_registry import _collect_exchange

        result = self._run_collector(_collect_exchange)
        assert isinstance(result, dict)

    def test_collect_sharepoint_returns_dict(self):
        from unimonitor.graph.collector_registry import _collect_sharepoint

        result = self._run_collector(_collect_sharepoint)
        assert isinstance(result, dict)

    def test_collect_teams_returns_dict(self):
        from unimonitor.graph.collector_registry import _collect_teams

        result = self._run_collector(_collect_teams)
        assert isinstance(result, dict)

    def test_collect_copilot_returns_dict(self):
        from unimonitor.graph.collector_registry import _collect_copilot

        result = self._run_collector(_collect_copilot)
        assert isinstance(result, dict)

    def test_collect_azure_security_returns_dict(self):
        from unimonitor.graph.collector_registry import _collect_azure_security

        result = self._run_collector(_collect_azure_security)
        assert isinstance(result, dict)

    def test_collect_secure_score_returns_dict(self):
        from unimonitor.graph.collector_registry import _collect_secure_score

        result = self._run_collector(_collect_secure_score)
        assert isinstance(result, dict)

    def test_collect_entra_id_with_data(self):
        from unimonitor.graph.collector_registry import _collect_entra_id

        gc = _make_gc(success=True, data={"value": [{"id": "policy-1"}]})
        result = _run(_collect_entra_id(gc))
        # At least one of the keys should be populated
        assert any(v for v in result.values())

    def test_collect_intune_error_swallowed(self):
        from unimonitor.graph.collector_registry import _collect_intune

        gc = _make_gc(success=False)
        result = _run(_collect_intune(gc))
        # Errors should be swallowed via _safe_get; result is empty dict
        assert result == {}


# ---------------------------------------------------------------------------
# CollectorRegistry._run_collector
# ---------------------------------------------------------------------------


class TestRunCollector:
    def test_known_collector_runs(self):
        from unimonitor.graph.collector_registry import CollectorRegistry

        registry = CollectorRegistry("tid", "cid", "csec")
        gc = _make_gc(success=True)
        result = _run(registry._run_collector("entra_id", gc))
        assert isinstance(result, dict)

    def test_unknown_collector_returns_empty(self):
        from unimonitor.graph.collector_registry import CollectorRegistry

        registry = CollectorRegistry("tid", "cid", "csec")
        gc = _make_gc(success=True)
        result = _run(registry._run_collector("nonexistent_collector", gc))
        assert result == {}

    def test_all_known_collectors_run(self):
        from unimonitor.graph.collector_registry import CollectorRegistry

        registry = CollectorRegistry("tid", "cid", "csec")
        gc = _make_gc(success=True)
        for name in CollectorRegistry.ALL_COLLECTORS:
            result = _run(registry._run_collector(name, gc))
            assert isinstance(result, dict), f"Collector {name} should return dict"


# ---------------------------------------------------------------------------
# CollectorRegistry.collect_all
# ---------------------------------------------------------------------------


class TestCollectAll:
    def test_collect_all_merges_results(self):
        from unimonitor.graph.collector_registry import CollectorRegistry

        registry = CollectorRegistry("tid", "cid", "csec")
        # Mock GraphClient context manager
        mock_gc = _make_gc(success=True, data={"value": []})
        mock_gc.__aenter__ = AsyncMock(return_value=mock_gc)
        mock_gc.__aexit__ = AsyncMock(return_value=None)

        with patch("unimonitor.graph.collector_registry.GraphClient", return_value=mock_gc):
            result = _run(registry.collect_all(collector_names=["entra_id"]))
        assert isinstance(result, dict)

    def test_collect_all_subset(self):
        from unimonitor.graph.collector_registry import CollectorRegistry

        registry = CollectorRegistry("tid", "cid", "csec")
        mock_gc = _make_gc(success=True)
        mock_gc.__aenter__ = AsyncMock(return_value=mock_gc)
        mock_gc.__aexit__ = AsyncMock(return_value=None)

        with patch("unimonitor.graph.collector_registry.GraphClient", return_value=mock_gc):
            result = _run(registry.collect_all(collector_names=["entra_id", "intune"]))
        assert isinstance(result, dict)

    def test_collect_all_handles_collector_exception(self):
        """Failed collector adds _error_<name> key but doesn't abort the rest."""
        from unimonitor.graph.collector_registry import CollectorRegistry

        registry = CollectorRegistry("tid", "cid", "csec")
        mock_gc = MagicMock()
        mock_gc.__aenter__ = AsyncMock(return_value=mock_gc)
        mock_gc.__aexit__ = AsyncMock(return_value=None)

        # Make get() raise an exception so _safe_get swallows it → empty dict returned
        mock_gc.get = AsyncMock(side_effect=RuntimeError("Auth failed"))

        with patch("unimonitor.graph.collector_registry.GraphClient", return_value=mock_gc):
            result = _run(registry.collect_all(collector_names=["entra_id"]))
        # Either empty dict or error key — should not raise
        assert isinstance(result, dict)

    def test_collect_all_uses_all_collectors_by_default(self):
        from unimonitor.graph.collector_registry import CollectorRegistry

        registry = CollectorRegistry("tid", "cid", "csec")
        mock_gc = _make_gc(success=True)
        mock_gc.__aenter__ = AsyncMock(return_value=mock_gc)
        mock_gc.__aexit__ = AsyncMock(return_value=None)

        called_names = []

        async def mock_run_collector(name, gc):
            called_names.append(name)
            return {}

        with patch("unimonitor.graph.collector_registry.GraphClient", return_value=mock_gc):
            with patch.object(registry, "_run_collector", side_effect=mock_run_collector):
                _run(registry.collect_all())

        assert set(called_names) == set(CollectorRegistry.ALL_COLLECTORS)
