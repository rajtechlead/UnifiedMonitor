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

    async def test_risk_view_hides_an_unconnected_provider(self, client: AsyncClient, auth_headers: dict, db_session, tenant):
        """A finding left over from a cloud that is not connected is not open risk."""
        from unimonitor.db.models.finding import Finding

        db_session.add(
            Finding(
                tenant_id=tenant.id,
                external_control_id="CTRL-AWS-001",
                title="Root Account MFA Enabled",
                description="root mfa",
                severity="critical",
                state="not_implemented",
                category="cloud_security",
                service="aws",
                risk_score=10,
            )
        )
        await db_session.flush()

        r = await client.get("/api/v1/dashboard/risk", headers=auth_headers)
        data = r.json()

        assert data["risks"] == []
        assert data["critical_risks"] == []
        assert data["heatmap"] == []

    async def test_findings_severity_filter_is_case_insensitive(self, client: AsyncClient, auth_headers: dict, db_session, tenant):
        """SOC tiles link with uppercase severity; findings are stored lowercase."""
        from unimonitor.db.models.finding import Finding

        db_session.add(
            Finding(
                tenant_id=tenant.id,
                external_control_id="CTRL-ENT-001",
                title="MFA Enforced",
                description="mfa",
                severity="critical",
                state="not_implemented",
                category="identity",
                service="entra_id",
                risk_score=10,
            )
        )
        await db_session.flush()

        r = await client.get("/api/v1/findings", params={"severity": "CRITICAL"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

        r = await client.get("/api/v1/findings", params={"severity": "critical"}, headers=auth_headers)
        assert r.json()["total"] == 1
