"""SOC metrics come from real alerts, not constants."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _alert(tenant_id: str, status: str, triggered_hours_ago: int, ack_hours: int | None = None, resolved_hours: int | None = None):
    from unimonitor.db.models.alert import Alert

    now = datetime.now(UTC)
    alert = Alert(
        tenant_id=tenant_id,
        title=f"{status} alert",
        severity="HIGH",
        status=status,
        triggered_at=now - timedelta(hours=triggered_hours_ago),
        acknowledged_at=now - timedelta(hours=ack_hours) if ack_hours is not None else None,
        resolved_at=now - timedelta(hours=resolved_hours) if resolved_hours is not None else None,
    )
    return alert


class TestSocMetrics:
    async def test_empty_install_reports_zero_not_a_constant(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/v1/dashboard/soc", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["active_alerts"] == 0
        assert body["acknowledged_alerts"] == 0
        assert body["resolved_alerts_24h"] == 0
        assert body["mean_time_to_acknowledge_hours"] is None
        assert body["mean_time_to_resolve_hours"] is None
        assert body["incident_trend"] == []

    async def test_counts_and_durations_come_from_alerts(self, client: AsyncClient, auth_headers: dict, db_session, tenant):
        db_session.add_all(
            [
                _alert(tenant.id, "open", triggered_hours_ago=2),
                _alert(tenant.id, "acknowledged", triggered_hours_ago=10, ack_hours=8),
                _alert(tenant.id, "resolved", triggered_hours_ago=20, ack_hours=18, resolved_hours=4),
                # resolved outside the 24h window: counted in MTTR, not in resolved_24h
                _alert(tenant.id, "resolved", triggered_hours_ago=96, ack_hours=90, resolved_hours=48),
            ]
        )
        await db_session.flush()

        response = await client.get("/api/v1/dashboard/soc", headers=auth_headers)
        body = response.json()

        assert body["active_alerts"] == 2
        assert body["acknowledged_alerts"] == 1
        assert body["resolved_alerts_24h"] == 1
        # acknowledgements took 2h, 2h and 6h
        assert body["mean_time_to_acknowledge_hours"] == 3.33
        # resolutions took 16h and 48h
        assert body["mean_time_to_resolve_hours"] == 32.0
        assert sum(row["alerts"] for row in body["incident_trend"]) == 4

    async def test_incident_trend_uses_findings_when_no_alert_fired(self, client: AsyncClient, auth_headers: dict, db_session, tenant):
        """A fresh install has findings but no alert rows; the trend must still show them."""
        from datetime import UTC, datetime

        from unimonitor.db.models.finding import Finding

        db_session.add(
            Finding(
                tenant_id=tenant.id,
                external_control_id="CTRL-ENT-003",
                title="MFA enforced",
                description="mfa",
                severity="critical",
                state="not_implemented",
                category="identity",
                service="entra_id",
                risk_score=10,
                first_detected_at=datetime.now(UTC),
            )
        )
        await db_session.flush()

        body = (await client.get("/api/v1/dashboard/soc", headers=auth_headers)).json()

        assert len(body["incident_trend"]) == 7
        assert sum(row["findings"] for row in body["incident_trend"]) == 1
        assert sum(row["critical"] for row in body["incident_trend"]) == 1

    async def test_metrics_are_tenant_scoped(self, client: AsyncClient, auth_headers: dict, db_session, tenant):
        from unimonitor.db.models.tenant import Tenant

        other = Tenant(id="soc-other-tenant-000001", name="Other", tenant_id="soc-other", domain="soc.example.com", is_active=True)
        db_session.add(other)
        db_session.add(_alert(other.id, "open", triggered_hours_ago=1))
        await db_session.flush()

        response = await client.get("/api/v1/dashboard/soc", params={"tenant_id": other.id}, headers=auth_headers)
        body = response.json()
        assert body["active_alerts"] == 1

        own = await client.get("/api/v1/dashboard/soc", params={"tenant_id": tenant.id}, headers=auth_headers)
        assert own.json()["active_alerts"] == 0
