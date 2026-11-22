"""CISO dashboard: aggregate residual risk across every cloud provider."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

EXPECTED_CLOUDS = ["microsoft", "aws", "gcp", "google_workspace"]


class TestCisoDashboard:
    async def test_shape(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/dashboard/ciso", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert [c["provider_id"] for c in data["clouds"]] == EXPECTED_CLOUDS
        assert all(c["colour"].startswith("#") for c in data["clouds"])
        assert "scores" in data
        assert "weakest_frameworks" in data
        assert isinstance(data["top_risks"], list)
        assert data["open_findings"] == 0

    async def test_requires_auth(self, client: AsyncClient):
        r = await client.get("/api/v1/dashboard/ciso")
        assert r.status_code == 401

    async def test_top_risks_exclude_implemented_and_label_provider(self, client: AsyncClient, auth_headers: dict, db_session, tenant):
        from unimonitor.db.models.cloud_connection import CloudConnection
        from unimonitor.db.models.finding import Finding

        db_session.add_all(
            [
                CloudConnection(tenant_id=tenant.id, provider="aws", account="111", display_name="AWS", status="connected"),
                CloudConnection(tenant_id=tenant.id, provider="gcp", account="proj", display_name="GCP", status="connected"),
            ]
        )
        db_session.add_all(
            [
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
                ),
                Finding(
                    tenant_id=tenant.id,
                    external_control_id="CTRL-GCP-001",
                    title="Primitive IAM Roles",
                    description="iam",
                    severity="high",
                    state="implemented",
                    category="cloud_security",
                    service="gcp",
                    risk_score=0,
                ),
            ]
        )
        await db_session.flush()

        r = await client.get("/api/v1/dashboard/ciso", headers=auth_headers)
        data = r.json()

        assert data["open_findings"] == 1
        assert len(data["top_risks"]) == 1
        # severity tiles count open risk only — the implemented GCP control is not exposure
        assert data["severity_totals"]["critical"] == 1
        assert data["severity_totals"]["high"] == 0
        assert data["severity_totals"]["total"] == 1
        risk = data["top_risks"][0]
        assert risk["provider_id"] == "aws"
        assert risk["provider_name"] == "Amazon Web Services"
        assert risk["colour"] == "#FF9900"
        assert risk["severity"] == "critical"

        aws = next(c for c in data["clouds"] if c["provider_id"] == "aws")
        assert aws["connected"] is True
        assert aws["critical"] == 1

    async def test_weakest_frameworks_sorted(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/dashboard/ciso", headers=auth_headers)
        coverage = [fw["coverage_pct"] for fw in r.json()["weakest_frameworks"]]
        assert coverage == sorted(coverage)
        assert len(coverage) <= 5

    async def test_strongest_frameworks_sorted(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/dashboard/ciso", headers=auth_headers)
        strongest = [fw["coverage_pct"] for fw in r.json()["strongest_frameworks"]]
        assert strongest == sorted(strongest, reverse=True)
        assert len(strongest) <= 5

    async def test_strongest_frameworks_mirror_weakest(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/dashboard/ciso", headers=auth_headers)
        data = r.json()
        weakest = data["weakest_frameworks"]
        strongest = data["strongest_frameworks"]
        assert strongest[0]["coverage_pct"] >= weakest[0]["coverage_pct"]

    async def test_weakest_frameworks_use_display_names(self, client: AsyncClient, auth_headers: dict):
        from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS

        names = {fw["id"]: fw["name"] for fw in SUPPORTED_FRAMEWORKS}
        r = await client.get("/api/v1/dashboard/ciso", headers=auth_headers)
        frameworks = r.json()["weakest_frameworks"]

        assert frameworks, "expected framework coverage from the control library"
        for fw in frameworks:
            assert fw["framework_name"] == names[fw["framework_id"]]
        # a slugged id would have rendered as "Iso27001 2022" before the fix
        assert any("-" in fw["framework_id"] for fw in frameworks)
