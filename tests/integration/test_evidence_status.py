"""Evidence status: evaluated, stale, never evaluated."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from unimonitor.grc.evidence_status import (
    EVALUATED,
    NEVER_EVALUATED,
    STALE,
    classify,
    summarise,
)

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


class TestClassify:
    def test_no_evidence_is_never_evaluated(self):
        status = classify(None)
        assert status.status == NEVER_EVALUATED
        assert status.evaluated_at is None
        assert status.age_days is None
        assert not status.counts_towards_score

    def test_recent_evidence_is_evaluated(self):
        status = classify(NOW - timedelta(days=2), now=NOW, source_run_id="run-1")
        assert status.status == EVALUATED
        assert status.age_days == 2.0
        assert status.source_run_id == "run-1"
        assert status.counts_towards_score

    def test_old_evidence_is_stale(self):
        status = classify(NOW - timedelta(days=30), now=NOW, stale_after_days=7)
        assert status.status == STALE
        assert not status.counts_towards_score

    def test_the_boundary_is_inclusive(self):
        assert classify(NOW - timedelta(days=7), now=NOW, stale_after_days=7).status == EVALUATED
        assert classify(NOW - timedelta(days=7, seconds=1), now=NOW, stale_after_days=7).status == STALE

    def test_a_naive_timestamp_is_treated_as_utc(self):
        naive = (NOW - timedelta(hours=1)).replace(tzinfo=None)
        assert classify(naive, now=NOW).status == EVALUATED

    def test_a_future_timestamp_does_not_produce_a_negative_age(self):
        assert classify(NOW + timedelta(days=1), now=NOW).age_days == 0.0


class TestSummarise:
    def test_counts_and_coverage(self):
        statuses = [
            classify(NOW - timedelta(days=1), now=NOW),
            classify(NOW - timedelta(days=2), now=NOW),
            classify(NOW - timedelta(days=60), now=NOW),
            classify(None),
        ]
        summary = summarise(statuses)
        assert summary["total_controls"] == 4
        assert summary[EVALUATED] == 2
        assert summary[STALE] == 1
        assert summary[NEVER_EVALUATED] == 1
        assert summary["coverage_pct"] == 50.0

    def test_an_empty_framework_is_zero_coverage_not_full(self):
        summary = summarise([])
        assert summary["total_controls"] == 0
        assert summary["coverage_pct"] == 0.0


class TestFrameworkCoverageApi:
    @pytest.mark.asyncio
    async def test_an_unknown_framework_is_404(self, client, auth_headers):
        r = await client.get("/api/v1/grc/frameworks/nope/evidence-coverage", headers=auth_headers)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_a_framework_without_runs_reports_no_current_evidence(self, client, auth_headers, tenant):
        from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS

        framework_id = SUPPORTED_FRAMEWORKS[0]["id"]
        r = await client.get(
            f"/api/v1/grc/frameworks/{framework_id}/evidence-coverage",
            params={"tenant_id": tenant.id},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["framework_id"] == framework_id
        assert body["coverage_pct"] == 0.0
        assert body["never_evaluated"] == body["total_controls"]

    @pytest.mark.asyncio
    async def test_a_snapshot_makes_one_control_count_as_evaluated(self, client, auth_headers, tenant):
        from datetime import UTC, datetime

        from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS
        from unimonitor.db.models.control_snapshot import ControlSnapshot

        framework_id = SUPPORTED_FRAMEWORKS[0]["id"]
        controls = (
            await client.get(
                f"/api/v1/grc/frameworks/{framework_id}/controls",
                params={"tenant_id": tenant.id},
                headers=auth_headers,
            )
        ).json()
        control = controls[0]

        # The endpoints open their own session, so the snapshot must be committed.
        from unimonitor.db.base import async_session_factory

        async with async_session_factory() as session:
            session.add(
                ControlSnapshot(
                    tenant_id=tenant.id,
                    assessment_run_id=None,
                    control_id=control["control_id"],
                    external_control_id=control["external_id"],
                    severity=control["severity"],
                    state="implemented",
                    checked_at=datetime.now(UTC),
                )
            )
            await session.commit()

        coverage = (
            await client.get(
                f"/api/v1/grc/frameworks/{framework_id}/evidence-coverage",
                params={"tenant_id": tenant.id},
                headers=auth_headers,
            )
        ).json()
        assert coverage["evaluated"] == 1
        assert coverage["coverage_pct"] > 0

        listed = (
            await client.get(
                f"/api/v1/grc/frameworks/{framework_id}/controls",
                params={"tenant_id": tenant.id},
                headers=auth_headers,
            )
        ).json()
        assessed = next(item for item in listed if item["control_id"] == control["control_id"])
        assert assessed["evidence_status"] == "evaluated"
        assert assessed["evaluated_at"] is not None

        # The snapshot is committed for the endpoints to see it; remove it so other
        # tests counting snapshots are not affected.
        from sqlalchemy import delete

        async with async_session_factory() as session:
            await session.execute(
                delete(ControlSnapshot).where(
                    ControlSnapshot.tenant_id == tenant.id,
                    ControlSnapshot.control_id == control["control_id"],
                )
            )
            await session.commit()
