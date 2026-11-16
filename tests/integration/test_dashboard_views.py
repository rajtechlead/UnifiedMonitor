"""Integration tests for the Risk, SOC and Audit dashboard views."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestDashboardViews:
    async def test_risk_view_shape(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/dashboard/risk", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "overall_risk_score" in data
        assert isinstance(data["heatmap"], list)

    async def test_soc_view_shape(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/dashboard/soc", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "active_alerts" in data
        assert "alerts_by_severity" in data

    async def test_audit_view_empty(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/dashboard/audit", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["entries"] == []
        assert data["total"] == 0

    async def test_audit_view_lists_entries(self, client: AsyncClient, auth_headers: dict, db_session):
        from unimonitor.db.models.audit_log import AuditLog

        db_session.add(AuditLog(action="assessment.started", resource_type="assessment", user_id=None))
        await db_session.flush()

        r = await client.get("/api/v1/dashboard/audit", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["entries"][0]["action"] == "assessment.started"

    async def test_audit_view_requires_auth(self, client: AsyncClient):
        r = await client.get("/api/v1/dashboard/audit")
        assert r.status_code == 401
