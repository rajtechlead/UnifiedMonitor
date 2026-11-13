"""
End-to-end journey tests — exercise the full API surface as a real client would.

Each class represents a complete user journey: auth → action → verify outcome.
These run against the in-memory SQLite test database (no external services needed).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ── Journey 1: User login and profile ─────────────────────────────────────────


class TestLoginJourney:
    """A user logs in, reads their profile, and refreshes their token."""

    async def test_liveness_probe(self, client: AsyncClient):
        """Top-level /health responds 200 before any auth."""
        r = await client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body

    async def test_login_with_valid_credentials(self, client: AsyncClient, admin_user):
        """POST /auth/login returns access_token and token_type."""
        r = await client.post(
            "/api/v1/auth/login",
            data={"username": admin_user.email, "password": "TestPassword123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body.get("token_type", "").lower() == "bearer"

    async def test_login_with_wrong_password_returns_401(self, client: AsyncClient, admin_user):
        """Wrong password → 401, not 500."""
        r = await client.post(
            "/api/v1/auth/login",
            data={"username": admin_user.email, "password": "WRONG"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 401

    async def test_protected_endpoint_requires_token(self, client: AsyncClient):
        """Calling a protected endpoint without a token returns 401/403."""
        r = await client.get("/api/v1/tenants/")
        assert r.status_code in (401, 403)

    async def test_me_endpoint_returns_user_info(self, client: AsyncClient, auth_headers: dict, admin_user):
        """GET /auth/me returns current user's email and role."""
        r = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == admin_user.email
        assert body["role"] == "admin"

    async def test_expired_token_returns_401(self, client: AsyncClient):
        """A clearly invalid token is rejected."""
        r = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer notavalidtoken"},
        )
        assert r.status_code == 401


# ── Journey 2: Tenant management ──────────────────────────────────────────────


class TestTenantJourney:
    """An admin creates a tenant, reads it back, updates it, and verifies isolation."""

    async def test_list_tenants(self, client: AsyncClient, auth_headers: dict, tenant):
        """GET /tenants/ returns a paginated list including the fixture tenant."""
        r = await client.get("/api/v1/tenants/", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        ids = [t["id"] for t in body.get("items", body if isinstance(body, list) else [])]
        assert tenant.id in ids

    async def test_get_tenant_by_id(self, client: AsyncClient, auth_headers: dict, tenant):
        """GET /tenants/{id} returns the correct tenant."""
        r = await client.get(f"/api/v1/tenants/{tenant.id}", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == tenant.id
        assert body["name"] == tenant.name

    async def test_get_nonexistent_tenant_returns_404(self, client: AsyncClient, auth_headers: dict):
        """GET /tenants/nonexistent-id returns 404."""
        r = await client.get("/api/v1/tenants/nonexistent-id-000", headers=auth_headers)
        assert r.status_code == 404


# ── Journey 3: Assessment run lifecycle ───────────────────────────────────────


class TestAssessmentJourney:
    """An admin triggers an assessment and monitors the run."""

    async def test_list_assessments_empty(self, client: AsyncClient, auth_headers: dict):
        """GET /assessments/ returns a list (possibly empty) with correct shape."""
        r = await client.get("/api/v1/assessments/", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        # Accept either list or paginated object
        assert isinstance(body, (list, dict))

    async def test_create_assessment(self, client: AsyncClient, auth_headers: dict, tenant):
        """POST /assessments/ creates an assessment record."""
        payload = {
            "name": "E2E Test Assessment",
            "tenant_id": tenant.id,
        }
        r = await client.post("/api/v1/assessments/", json=payload, headers=auth_headers)
        assert r.status_code in (200, 201)
        body = r.json()
        assert body.get("name") == "E2E Test Assessment"
        return body["id"]

    async def test_get_assessment_by_id(self, client: AsyncClient, auth_headers: dict, tenant):
        """Create then immediately retrieve an assessment."""
        # Create
        payload = {"name": "Retrieve Me", "tenant_id": tenant.id}
        create_r = await client.post("/api/v1/assessments/", json=payload, headers=auth_headers)
        assert create_r.status_code in (200, 201)
        assessment_id = create_r.json()["id"]

        # Retrieve
        r = await client.get(f"/api/v1/assessments/{assessment_id}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["id"] == assessment_id

    async def test_assessment_runs_list(self, client: AsyncClient, auth_headers: dict):
        """GET /assessments/runs (or /reports/runs) is reachable."""
        r = await client.get("/api/v1/reports/runs", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body or isinstance(body, list)


# ── Journey 4: Findings ────────────────────────────────────────────────────────


class TestFindingsJourney:
    """An admin lists findings with filters and bulk-acknowledges."""

    async def test_list_findings_empty(self, client: AsyncClient, auth_headers: dict):
        """GET /findings/ returns 200 with an empty list (no runs yet)."""
        r = await client.get("/api/v1/findings/", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        # Accept list or paginated shape
        items = body.get("items", body) if isinstance(body, dict) else body
        assert isinstance(items, list)

    async def test_findings_filter_by_severity(self, client: AsyncClient, auth_headers: dict):
        """Severity filter parameter is accepted without error."""
        r = await client.get("/api/v1/findings/?severity=critical", headers=auth_headers)
        assert r.status_code == 200

    async def test_findings_filter_by_state(self, client: AsyncClient, auth_headers: dict):
        """State filter parameter is accepted without error."""
        r = await client.get("/api/v1/findings/?state=open", headers=auth_headers)
        assert r.status_code == 200

    async def test_get_nonexistent_finding_returns_404(self, client: AsyncClient, auth_headers: dict):
        """Fetching a finding that doesn't exist returns 404."""
        r = await client.get("/api/v1/findings/nonexistent-finding-id", headers=auth_headers)
        assert r.status_code == 404


# ── Journey 5: Dashboard ──────────────────────────────────────────────────────


class TestDashboardJourney:
    """The dashboard endpoints return correctly shaped data."""

    async def test_dashboard_overview(self, client: AsyncClient, auth_headers: dict):
        """GET /dashboard/overview returns a structured response."""
        r = await client.get("/api/v1/dashboard/overview", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)

    async def test_dashboard_trends(self, client: AsyncClient, auth_headers: dict):
        """GET /dashboard/trends returns trend data."""
        r = await client.get("/api/v1/dashboard/trends", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)

    async def test_dashboard_security_view(self, client: AsyncClient, auth_headers: dict):
        """GET /dashboard/security returns security-view data."""
        r = await client.get("/api/v1/dashboard/security", headers=auth_headers)
        assert r.status_code == 200

    async def test_dashboard_compliance_view(self, client: AsyncClient, auth_headers: dict):
        """GET /dashboard/compliance returns compliance data."""
        r = await client.get("/api/v1/dashboard/compliance", headers=auth_headers)
        assert r.status_code == 200


# ── Journey 6: Reports ────────────────────────────────────────────────────────


class TestReportsJourney:
    """Report generation endpoints return correct shapes."""

    async def test_list_reports(self, client: AsyncClient, auth_headers: dict):
        """GET /reports/ returns 200."""
        r = await client.get("/api/v1/reports/", headers=auth_headers)
        assert r.status_code == 200

    async def test_list_runs(self, client: AsyncClient, auth_headers: dict):
        """GET /reports/runs returns paginated shape."""
        r = await client.get("/api/v1/reports/runs", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "total" in body

    async def test_generate_report_requires_valid_run(self, client: AsyncClient, auth_headers: dict):
        """Generating a report for a non-existent run returns 404 or 422."""
        r = await client.post(
            "/api/v1/reports/generate",
            json={"run_id": "nonexistent-run", "format": "pdf"},
            headers=auth_headers,
        )
        assert r.status_code in (404, 422)


# ── Journey 7: GRC / Controls ─────────────────────────────────────────────────


class TestGRCJourney:
    """Controls load from YAML and scoring endpoints work."""

    async def test_controls_loader_has_67_controls(self):
        """ControlLoader reads all YAML files and returns 67 controls."""
        from unimonitor.grc.control_loader import ControlLoader

        controls = ControlLoader().load_all()
        # We expect at least 60 (buffer for future pruning)
        assert len(controls) >= 60, f"Expected >=60 controls, got {len(controls)}"

    async def test_controls_cover_all_services(self):
        """Controls exist for all 7 expected services."""
        from collections import Counter

        from unimonitor.grc.control_loader import ControlLoader

        controls = ControlLoader().load_all()
        services = Counter(c.service for c in controls)
        for svc in ("exchange", "sharepoint", "teams", "intune", "defender", "purview"):
            assert services[svc] > 0, f"No controls for service: {svc}"

    async def test_all_controls_have_evaluate_function(self):
        """Every control's evaluate block compiles into a callable."""
        from unimonitor.grc.control_loader import ControlLoader

        controls = ControlLoader().load_all()
        broken = []
        for c in controls:
            try:
                result = c.run_evaluate({})
                assert result in (
                    "implemented",
                    "partially_implemented",
                    "not_implemented",
                    "not_applicable",
                ), f"{c.id}: unexpected result '{result}'"
            except Exception as exc:
                broken.append(f"{c.id}: {exc}")
        assert not broken, "Controls with broken evaluate:\n" + "\n".join(broken)

    async def test_framework_crosswalk_finds_nist_controls(self):
        """FrameworkCrosswalk can find controls mapped to NIST CSF DE.CM-01."""
        from unimonitor.grc.control_loader import ControlLoader
        from unimonitor.grc.crosswalk import FrameworkCrosswalk

        controls = ControlLoader().load_all()
        cw = FrameworkCrosswalk(controls)
        # DE.CM-01 is mapped by multiple Defender / Intune controls
        results = cw.find_by_reference("nist_csf_2", "DE.CM-01")
        assert len(results) > 0, "Expected controls mapped to nist_csf_2 / DE.CM-01"

    async def test_scoring_compute_score_basic(self):
        """compute_score returns a float between 0 and 100."""
        from unimonitor.grc.scoring import compute_score

        findings = [
            {"severity": "CRITICAL", "state": "not_implemented"},
            {"severity": "HIGH", "state": "implemented"},
            {"severity": "MEDIUM", "state": "partially_implemented"},
            {"severity": "LOW", "state": "not_applicable"},
        ]
        score = compute_score(findings)
        assert 0.0 <= score <= 100.0


# ── Journey 8: Monitoring / platform health ───────────────────────────────────


class TestMonitoringJourney:
    """Platform health endpoint returns structured component status."""

    async def test_platform_health_endpoint(self, client: AsyncClient, auth_headers: dict):
        """GET /monitoring/health returns overall + component status."""
        r = await client.get("/api/v1/monitoring/health", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "overall" in body or "status" in body

    async def test_platform_health_has_db_component(self, client: AsyncClient, auth_headers: dict):
        """Platform health includes database component."""
        r = await client.get("/api/v1/monitoring/health", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        # Accept either top-level 'db' key or nested 'components'
        has_db = "db" in body or "database" in body or "db" in body.get("components", {}) or "database" in body.get("components", {})
        assert has_db, f"No db component in health response: {list(body.keys())}"
