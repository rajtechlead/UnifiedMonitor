"""Multi-cloud dashboards: aggregate view and per-provider views."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

EXPECTED_PROVIDERS = ["microsoft", "aws", "gcp", "google_workspace"]


class TestCloudAggregate:
    async def test_aggregate_lists_every_provider(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/dashboard/clouds", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert [p["provider_id"] for p in data["providers"]] == EXPECTED_PROVIDERS
        assert data["totals"]["providers_total"] == len(EXPECTED_PROVIDERS)
        assert data["totals"]["controls_total"] > 0
        assert "overall_scores" in data

    async def test_aggregate_controls_split_across_providers(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/dashboard/clouds", headers=auth_headers)
        data = r.json()
        by_id = {p["provider_id"]: p for p in data["providers"]}
        assert by_id["aws"]["controls_total"] == 14
        assert by_id["gcp"]["controls_total"] == 12
        assert by_id["google_workspace"]["controls_total"] == 6
        assert by_id["microsoft"]["controls_total"] > 100
        assert all(not p["connected"] for p in data["providers"])

    async def test_aggregate_counts_findings(self, client: AsyncClient, auth_headers: dict, db_session, tenant):
        from unimonitor.db.models.cloud_connection import CloudConnection
        from unimonitor.db.models.finding import Finding

        db_session.add_all(
            [
                CloudConnection(tenant_id=tenant.id, provider="aws", account="111", display_name="AWS", status="connected"),
                CloudConnection(tenant_id=tenant.id, provider="gcp", account="proj", display_name="GCP", status="connected"),
            ]
        )
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
        db_session.add(
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
            )
        )
        await db_session.flush()

        r = await client.get("/api/v1/dashboard/clouds", headers=auth_headers)
        data = r.json()
        by_id = {p["provider_id"]: p for p in data["providers"]}

        assert by_id["aws"]["connected"] is True
        assert by_id["aws"]["finding_counts"]["critical"] == 1
        assert by_id["aws"]["state_counts"]["not_implemented"] == 1
        assert by_id["gcp"]["state_counts"]["implemented"] == 1
        assert by_id["google_workspace"]["connected"] is False
        assert data["totals"]["critical"] == 1
        assert data["totals"]["providers_connected"] == 2


class TestCloudProviderDetail:
    async def test_provider_detail(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/dashboard/clouds/aws", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["provider"]["provider_id"] == "aws"
        assert data["provider"]["controls_total"] == 14
        assert data["provider"]["collectors"] == ["aws"]
        assert {s["service"] for s in data["services"]} == {"aws"}
        assert data["categories"]

    async def test_provider_alias_resolves(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/dashboard/clouds/m365", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["provider"]["provider_id"] == "microsoft"

    async def test_unknown_provider_404(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/v1/dashboard/clouds/oracle", headers=auth_headers)
        assert r.status_code == 404

    async def test_provider_detail_lists_findings(self, client: AsyncClient, auth_headers: dict, db_session, tenant):
        from unimonitor.db.models.cloud_connection import CloudConnection
        from unimonitor.db.models.finding import Finding

        db_session.add(CloudConnection(tenant_id=tenant.id, provider="aws", account="111", display_name="AWS", status="connected"))
        db_session.add(
            Finding(
                tenant_id=tenant.id,
                external_control_id="CTRL-AWS-004",
                title="S3 Public Access Blocked",
                description="bucket",
                severity="high",
                state="not_implemented",
                category="cloud_security",
                service="aws",
                risk_score=8,
            )
        )
        await db_session.flush()

        r = await client.get("/api/v1/dashboard/clouds/aws", headers=auth_headers)
        data = r.json()
        assert data["provider"]["connected"] is True
        assert data["top_findings"][0]["id"]
        assert data["top_findings"][0]["service"] == "aws"
        assert data["provider"]["scores"]["security_score"] == 0.0

    async def test_provider_requires_auth(self, client: AsyncClient):
        r = await client.get("/api/v1/dashboard/clouds/aws")
        assert r.status_code == 401


class TestFrameworkCoverage:
    async def test_framework_coverage_reports_controls(self, client: AsyncClient, auth_headers: dict):
        """compute_framework_coverage must resolve YAML mappings (hyphen/underscore ids)."""
        r = await client.get("/api/v1/grc/frameworks", headers=auth_headers)
        assert r.status_code == 200
        frameworks = r.json()
        assert frameworks
        assert any(fw["controls_total"] > 0 for fw in frameworks)
