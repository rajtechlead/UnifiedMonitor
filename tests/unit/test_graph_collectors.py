"""
Unit tests for graph/collectors/entra_id.py and graph/collectors/intune.py.
All GraphClient calls are mocked; we verify the data is wired to the right fields.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _ok(data):
    """Return a successful GraphResponse mock."""
    from unimonitor.graph.client import GraphResponse

    return GraphResponse(data=data, success=True)


def _fail():
    """Raise a generic exception to simulate a Graph error."""
    raise RuntimeError("Graph API unavailable")


def _make_client(**overrides):
    """Return a MagicMock that mimics GraphClient.get / get_all_pages."""
    client = MagicMock()
    client.get = AsyncMock(return_value=_ok([]))
    client.get_all_pages = AsyncMock(return_value=[])
    for k, v in overrides.items():
        setattr(client, k, v)
    return client


# ---------------------------------------------------------------------------
# EntraIdCollector
# ---------------------------------------------------------------------------


class TestEntraIdDataclass:
    def test_defaults_are_empty(self):
        from unimonitor.graph.collectors.entra_id import EntraIdData

        d = EntraIdData()
        assert d.conditional_access_policies == []
        assert d.users == []
        assert d.errors == {}

    def test_errors_are_independent(self):
        from unimonitor.graph.collectors.entra_id import EntraIdData

        a, b = EntraIdData(), EntraIdData()
        a.errors["x"] = "fail"
        assert "x" not in b.errors


class TestEntraIdCollector:
    def test_collect_returns_entra_id_data(self):
        from unimonitor.graph.collectors.entra_id import EntraIdCollector, EntraIdData

        client = _make_client()
        collector = EntraIdCollector(client)
        result = _run(collector.collect())
        assert isinstance(result, EntraIdData)

    def test_conditional_access_populated(self):
        from unimonitor.graph.collectors.entra_id import EntraIdCollector

        policies = [{"id": "p1", "displayName": "Block legacy auth"}]
        locations = [{"id": "loc1"}]
        client = _make_client()

        # Route first two calls for conditional access
        async def _get(endpoint, **kw):
            if "conditionalAccess/policies" in endpoint:
                return _ok(policies)
            if "namedLocations" in endpoint:
                return _ok(locations)
            return _ok([])

        client.get = _get
        collector = EntraIdCollector(client)
        result = _run(collector.collect())
        assert result.conditional_access_policies == policies
        assert result.named_locations == locations

    def test_auth_methods_populated(self):
        from unimonitor.graph.collectors.entra_id import EntraIdCollector

        policy = {"id": "amp1", "registrationRequirement": "mfaRequired"}
        regs = [{"userId": "u1", "isMfaRegistered": True}]
        client = _make_client()

        async def _get(endpoint, **kw):
            if "authenticationMethodsPolicy" in endpoint:
                return _ok(policy)
            if "userRegistrationDetails" in endpoint:
                return _ok(regs)
            return _ok([])

        client.get = _get
        collector = EntraIdCollector(client)
        result = _run(collector.collect())
        assert result.auth_methods_policy == policy
        assert result.auth_method_registrations == {"users": regs}

    def test_risky_users_populated(self):
        from unimonitor.graph.collectors.entra_id import EntraIdCollector

        risky = [{"id": "u1", "riskLevel": "high"}]
        client = _make_client()

        async def _get(endpoint, **kw):
            if "riskyUsers" in endpoint:
                return _ok(risky)
            return _ok({})

        client.get = _get
        collector = EntraIdCollector(client)
        result = _run(collector.collect())
        assert result.risky_users == risky

    def test_pim_role_assignments_populated(self):
        from unimonitor.graph.collectors.entra_id import EntraIdCollector

        assignments = [{"id": "ra1", "roleDefinition": {"displayName": "Global Admin"}}]
        client = _make_client()

        async def _get(endpoint, **kw):
            if "roleAssignments" in endpoint:
                return _ok(assignments)
            return _ok([])

        client.get = _get
        collector = EntraIdCollector(client)
        result = _run(collector.collect())
        assert result.pim_role_assignments == assignments

    def test_users_and_guests_populated(self):
        from unimonitor.graph.collectors.entra_id import EntraIdCollector

        all_users = [
            {"id": "u1", "userPrincipalName": "alice@contoso.com"},
            {"id": "u2", "userPrincipalName": "bob#EXT#@contoso.com"},
        ]
        client = _make_client()
        client.get_all_pages = AsyncMock(side_effect=[all_users, []])  # users, then apps
        collector = EntraIdCollector(client)
        result = _run(collector.collect())
        assert len(result.users) == 2
        assert len(result.guest_users) == 1
        assert result.guest_users[0]["id"] == "u2"

    def test_app_registrations_populated(self):
        from unimonitor.graph.collectors.entra_id import EntraIdCollector

        apps = [{"id": "app1", "displayName": "My App"}]
        sps = [{"id": "sp1", "displayName": "My SP"}]
        client = _make_client()
        client.get_all_pages = AsyncMock(side_effect=[[], apps, sps])  # users, apps, sps
        collector = EntraIdCollector(client)
        result = _run(collector.collect())
        assert result.app_registrations == apps
        assert result.service_principals == sps

    def test_errors_recorded_on_exception(self):
        from unimonitor.graph.collectors.entra_id import EntraIdCollector

        client = _make_client()

        async def _get(endpoint, **kw):
            raise RuntimeError("network failure")

        client.get = _get
        client.get_all_pages = AsyncMock(side_effect=RuntimeError("network failure"))
        collector = EntraIdCollector(client)
        result = _run(collector.collect())
        # At least one error should be recorded
        assert len(result.errors) > 0

    def test_non_list_data_becomes_empty_list(self):
        from unimonitor.graph.collectors.entra_id import EntraIdCollector

        # Graph returns a dict (unexpected) instead of list for policies
        client = _make_client()

        async def _get(endpoint, **kw):
            if "conditionalAccess/policies" in endpoint:
                return _ok({"unexpected": "dict"})  # not a list
            return _ok([])

        client.get = _get
        collector = EntraIdCollector(client)
        result = _run(collector.collect())
        assert result.conditional_access_policies == []


# ---------------------------------------------------------------------------
# IntuneCollector
# ---------------------------------------------------------------------------


class TestIntuneDataclass:
    def test_defaults_empty(self):
        from unimonitor.graph.collectors.intune import IntuneData

        d = IntuneData()
        assert d.managed_devices == []
        assert d.errors == {}


class TestIntuneCollector:
    def test_collect_returns_intune_data(self):
        from unimonitor.graph.collectors.intune import IntuneCollector, IntuneData

        client = _make_client()
        collector = IntuneCollector(client)
        result = _run(collector.collect())
        assert isinstance(result, IntuneData)

    def test_managed_devices_populated(self):
        from unimonitor.graph.collectors.intune import IntuneCollector

        devices = [{"id": "d1", "operatingSystem": "Windows", "complianceState": "compliant"}]
        client = _make_client()
        client.get_all_pages = AsyncMock(return_value=devices)
        collector = IntuneCollector(client)
        result = _run(collector.collect())
        assert result.managed_devices == devices

    def test_compliance_policies_populated(self):
        from unimonitor.graph.collectors.intune import IntuneCollector

        policies = [{"id": "cp1", "displayName": "Windows Compliance"}]
        client = _make_client()

        # _collect_compliance uses get_all_pages for policies
        async def _get_all_pages(endpoint, **kw):
            if "deviceCompliancePolicies" in endpoint:
                return policies
            return []

        client.get_all_pages = _get_all_pages
        collector = IntuneCollector(client)
        result = _run(collector.collect())
        assert result.device_compliance_policies == policies

    def test_app_protection_ios_populated(self):
        from unimonitor.graph.collectors.intune import IntuneCollector

        ios_policies = [{"id": "ios1", "displayName": "iOS MAM"}]
        client = _make_client()

        # _collect_apps uses get_all_pages for MAM policies
        async def _get_all_pages(endpoint, **kw):
            if "iosManagedAppProtections" in endpoint:
                return ios_policies
            return []

        client.get_all_pages = _get_all_pages
        collector = IntuneCollector(client)
        result = _run(collector.collect())
        assert result.app_protection_policies_ios == ios_policies

    def test_errors_recorded_on_exception(self):
        from unimonitor.graph.collectors.intune import IntuneCollector

        client = _make_client()

        async def _get(endpoint, **kw):
            raise RuntimeError("intune down")

        client.get = _get
        client.get_all_pages = AsyncMock(side_effect=RuntimeError("intune down"))
        collector = IntuneCollector(client)
        result = _run(collector.collect())
        assert len(result.errors) > 0

    def test_non_list_response_handled(self):
        from unimonitor.graph.collectors.intune import IntuneCollector

        client = _make_client()

        async def _get(endpoint, **kw):
            return _ok({"oops": "dict"})  # unexpected shape

        client.get = _get
        collector = IntuneCollector(client)
        result = _run(collector.collect())
        # None of the list fields should be a dict
        assert isinstance(result.device_compliance_policies, list)
