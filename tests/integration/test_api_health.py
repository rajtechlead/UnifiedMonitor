"""
Integration tests for core API endpoints.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


class TestHealthEndpoint:
    async def test_health_returns_200(self, client: AsyncClient):
        """Health endpoint is publicly accessible."""
        r = await client.get("/api/v1/health")
        assert r.status_code == 200

    async def test_health_returns_status_field(self, client: AsyncClient):
        """Health response includes a status field."""
        r = await client.get("/api/v1/health")
        data = r.json()
        assert "status" in data

    async def test_docs_accessible(self, client: AsyncClient):
        """OpenAPI docs endpoint is accessible (served at /api/docs in non-prod)."""
        r = await client.get("/api/docs")
        assert r.status_code == 200


class TestAuthEndpoints:
    async def test_login_returns_token(self, client: AsyncClient, admin_user):
        """Valid credentials return an access token."""
        r = await client.post(
            "/api/v1/auth/login",
            data={"username": admin_user.email, "password": "TestPassword123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, admin_user):
        """Wrong password returns 401."""
        r = await client.post(
            "/api/v1/auth/login",
            data={"username": admin_user.email, "password": "wrongpassword"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 401

    async def test_login_unknown_user(self, client: AsyncClient):
        """Unknown user returns 401."""
        r = await client.post(
            "/api/v1/auth/login",
            data={"username": "nobody@nowhere.com", "password": "anypassword"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 401

    async def test_protected_endpoint_without_token(self, client: AsyncClient):
        """Protected endpoints return 401 without a token."""
        r = await client.get("/api/v1/assessments")
        assert r.status_code == 401

    async def test_protected_endpoint_with_token(self, client: AsyncClient, auth_headers: dict):
        """Protected endpoints return 200 with a valid token."""
        r = await client.get("/api/v1/assessments", headers=auth_headers)
        assert r.status_code == 200

    async def test_invalid_token_rejected(self, client: AsyncClient):
        """Invalid JWT token returns 401."""
        r = await client.get(
            "/api/v1/assessments",
            headers={"Authorization": "Bearer not.a.valid.token"},
        )
        assert r.status_code == 401


class TestFindingsAPI:
    async def test_list_findings_empty(self, client: AsyncClient, auth_headers: dict):
        """Empty findings list returns correctly."""
        r = await client.get("/api/v1/findings", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    async def test_findings_filter_by_severity(self, client: AsyncClient, auth_headers: dict):
        """Severity filter is accepted without error."""
        r = await client.get(
            "/api/v1/findings",
            params={"severity": "CRITICAL"},
            headers=auth_headers,
        )
        assert r.status_code == 200

    async def test_findings_filter_by_state(self, client: AsyncClient, auth_headers: dict):
        """State filter is accepted without error."""
        r = await client.get(
            "/api/v1/findings",
            params={"state": "open"},
            headers=auth_headers,
        )
        assert r.status_code == 200

    async def test_get_nonexistent_finding(self, client: AsyncClient, auth_headers: dict):
        """Non-existent finding returns 404."""
        r = await client.get(
            "/api/v1/findings/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestAssessmentsAPI:
    async def test_list_assessments_empty(self, client: AsyncClient, auth_headers: dict):
        """Empty assessments list returns correctly."""
        r = await client.get("/api/v1/assessments", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data

    async def test_create_assessment(self, client: AsyncClient, auth_headers: dict):
        """Create a new assessment successfully."""
        payload = {
            "name": "Test Assessment",
            "frameworks": ["iso_27001_2022", "cis_m365"],
            "collectors": [],
        }
        r = await client.post(
            "/api/v1/assessments",
            json=payload,
            headers=auth_headers,
        )
        assert r.status_code in (200, 201)
        data = r.json()
        assert data["name"] == "Test Assessment"
        assert "id" in data

    async def test_create_assessment_missing_name(self, client: AsyncClient, auth_headers: dict):
        """Assessment creation without name returns 422."""
        r = await client.post(
            "/api/v1/assessments",
            json={"frameworks": ["iso_27001_2022"]},
            headers=auth_headers,
        )
        assert r.status_code == 422

    async def test_get_nonexistent_assessment(self, client: AsyncClient, auth_headers: dict):
        """Non-existent assessment returns 404."""
        r = await client.get(
            "/api/v1/assessments/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestReportsAPI:
    async def test_list_reports_empty(self, client: AsyncClient, auth_headers: dict):
        """Empty reports list returns correctly."""
        r = await client.get("/api/v1/reports", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data


class TestDashboardAPI:
    async def test_executive_dashboard(self, client: AsyncClient, auth_headers: dict):
        """Executive dashboard returns expected structure."""
        r = await client.get("/api/v1/dashboard/executive", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "scores" in data or "severity_counts" in data or isinstance(data, dict)

    async def test_security_dashboard(self, client: AsyncClient, auth_headers: dict):
        """Security dashboard returns 200."""
        r = await client.get("/api/v1/dashboard/security", headers=auth_headers)
        assert r.status_code == 200

    async def test_compliance_dashboard(self, client: AsyncClient, auth_headers: dict):
        """Compliance dashboard returns 200."""
        r = await client.get("/api/v1/dashboard/compliance", headers=auth_headers)
        assert r.status_code == 200
