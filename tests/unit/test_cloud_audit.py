"""Cloud audit fan-out: a failed platform must explain itself, never blank."""

from __future__ import annotations

import asyncio

import pytest

from unimonitor.core import cloud_audit


@pytest.mark.asyncio
async def test_failed_platform_keeps_a_readable_reason(monkeypatch) -> None:
    async def connected(_db, _tenant_id=None):
        return {"microsoft"}

    async def boom(_db, _limit, _tenant_id=None):
        raise RuntimeError("Graph refused the audit log (403): missing AuditLog.Read.All")

    monkeypatch.setattr("unimonitor.onboarding.service.connected_providers", connected)
    monkeypatch.setattr(cloud_audit, "_microsoft", boom)

    failures: dict[str, str] = {}
    events = await cloud_audit.cloud_events(None, failures=failures)

    assert events == []
    assert "AuditLog.Read.All" in failures["microsoft"]


@pytest.mark.asyncio
async def test_timeout_reason_names_the_limit(monkeypatch) -> None:
    async def connected(_db, _tenant_id=None):
        return {"aws"}

    async def slow(_db, _limit, _tenant_id=None):
        await asyncio.sleep(2)
        return []

    monkeypatch.setattr("unimonitor.onboarding.service.connected_providers", connected)
    monkeypatch.setattr(cloud_audit, "_aws", slow)
    monkeypatch.setattr(cloud_audit, "PER_SOURCE_TIMEOUT_SECONDS", 0.05)

    failures: dict[str, str] = {}
    await cloud_audit.cloud_events(None, failures=failures)

    assert failures["aws"] == "timed out after 0.05s"


def test_setup_registers_the_origin_it_runs_on() -> None:
    from unimonitor.onboarding.m365 import _redirect_uris

    uris = _redirect_uris(["https://monitor.contoso.com/api/v1/auth/callback"])

    assert "https://monitor.contoso.com/api/v1/auth/callback" in uris
    assert len(uris) == len(set(uris))
