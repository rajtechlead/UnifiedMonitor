"""
GRC Engine — orchestrates assessment runs:
  1. Load controls for the requested frameworks
  2. Execute Graph collectors to gather tenant data
  3. Evaluate each control against collected data
  4. Score the run (security, compliance, risk)
  5. Persist findings and evidence
  6. Trigger AI remediation for high/critical findings
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger
from unimonitor.db.models.assessment import AssessmentRun, AssessmentStatus
from unimonitor.db.models.control_snapshot import ControlSnapshot
from unimonitor.db.models.finding import Finding, FindingEvidence, FindingSeverity, FindingState
from unimonitor.graph.collector_registry import CollectorRegistry
from unimonitor.grc.control_loader import ControlDefinition, ControlLoader
from unimonitor.grc.control_trends import prune_control_snapshots
from unimonitor.grc.scoring import calculate_scores
from unimonitor.zerotrust.coverage import expected_keys

logger = get_logger(__name__)

# Controls checked per semaphore slot
MAX_CONCURRENT_EVALUATIONS = 10


class AssessmentEngine:
    """Runs a complete assessment for a tenant."""

    def __init__(
        self,
        db: AsyncSession,
        tenant_id: str,
        entra_tenant_id: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.entra_tenant_id = entra_tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_EVALUATIONS)

    async def run(
        self,
        run: AssessmentRun,
        frameworks: list[str],
        collectors: list[str] | None = None,
        progress_callback: Any = None,
    ) -> AssessmentRun:
        """Execute an assessment run end-to-end."""
        logger.info(
            "Assessment run started",
            extra={"run_id": run.id, "tenant_id": self.tenant_id, "frameworks": frameworks},
        )

        # Mark as running
        run.status = AssessmentStatus.RUNNING.value
        await self.db.commit()

        try:
            # 1. Load controls via new ControlLoader (new list-format YAML)
            all_ctrl_defs = ControlLoader().load_all()
            controls = _select_controls(all_ctrl_defs, frameworks)
            logger.info("Controls loaded", extra={"count": len(controls), "run_id": run.id})

            # 2. Collect data from Graph API
            collector_registry = CollectorRegistry(
                tenant_id=self.entra_tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            collector_names = collectors or list(CollectorRegistry.ALL_COLLECTORS)
            collected_data = await collector_registry.collect_all(collector_names)
            logger.info("Data collected", extra={"collectors": len(collected_data), "run_id": run.id})

            # 3. Evaluate controls
            findings: list[Finding] = []
            evaluated = 0
            passed = 0

            async def evaluate_one(control_def: ControlDefinition) -> Finding | None:
                nonlocal evaluated, passed
                try:
                    async with self._semaphore:
                        finding = await self._evaluate_control(
                            control_def=control_def,
                            collected_data=collected_data,
                            run_id=run.id,
                        )
                        evaluated += 1
                        if finding.state == FindingState.IMPLEMENTED.value:
                            passed += 1
                        if progress_callback:
                            await progress_callback(evaluated, len(controls))
                        return finding
                except Exception as exc:
                    logger.error(
                        "Control evaluation error",
                        extra={"control": control_def.id, "error": str(exc), "run_id": run.id},
                    )
                    return None

            tasks = [evaluate_one(c) for c in controls]
            results = await asyncio.gather(*tasks)
            findings = [f for f in results if f is not None]

            # 4. Persist findings
            for finding in findings:
                self.db.add(finding)
            await self.db.flush()

            # 4b/4c. Append the immutable per-control state used by the trend series
            # and prune past the retention window in the same transaction.
            await self._record_snapshots(findings, run.id)

            # 5. Score the run
            _apply_scores(run, calculate_scores(findings), evaluated, passed)

            await self.db.commit()
            logger.info(
                "Assessment run completed",
                extra={
                    "run_id": run.id,
                    "security_score": run.security_score,
                    "compliance_score": run.compliance_score,
                    "findings": len(findings),
                },
            )
            return run

        except Exception as exc:
            logger.error("Assessment run failed", extra={"run_id": run.id, "error": str(exc)})
            run.status = AssessmentStatus.FAILED.value
            run.error_message = str(exc)[:2000]
            run.completed_at = datetime.now(UTC)
            await self.db.commit()
            raise

    async def _record_snapshots(self, findings: list[Finding], run_id: str) -> None:
        """Write the per-control history and prune it in one transaction.

        Findings are overwritten in place on later runs, so without these rows the
        history of a control cannot be reconstructed.
        """
        for finding in findings:
            self.db.add(
                ControlSnapshot(
                    tenant_id=self.tenant_id,
                    assessment_run_id=run_id,
                    control_id=finding.control_id or finding.external_control_id,
                    external_control_id=finding.external_control_id,
                    severity=finding.severity,
                    state=finding.state,
                )
            )
        retention_days = get_settings().CONTROL_SNAPSHOT_RETENTION_DAYS
        pruned = await prune_control_snapshots(self.db, self.tenant_id, retention_days)
        if pruned:
            logger.info("Control snapshots pruned", extra={"rows": pruned, "retention_days": retention_days})

    async def _evaluate_control(
        self,
        control_def: ControlDefinition,
        collected_data: dict[str, Any],
        run_id: str,
    ) -> Finding:
        """Evaluate a single ControlDefinition against collected data.

        The ``evaluate`` function in the YAML takes ``data`` (the full collected
        snapshot) and returns one of:
            - "implemented" / "pass"
            - "partially_implemented" / "warning"
            - "not_implemented" / "fail"
            - "not_applicable"
        """
        control_id = control_def.id
        service = control_def.service or "unknown"
        category = control_def.category or "general"

        # Build the data dict scoped to this control's service (pass everything
        # so evaluate functions can access any key they need)
        eval_data = dict(collected_data)

        state: str
        evidence_text: str | None = None

        # What the collector supplied for this control. A control whose entire
        # expected data set is absent has no evidence: it is not_applicable, never
        # a fabricated failure (and never a pass).
        keys = sorted(expected_keys(control_def))
        missing = [key for key in keys if eval_data.get(key) in (None, "", [], {})]
        coverage_text = json.dumps({"keys": keys, "missing": missing}) if keys else None

        if keys and len(missing) == len(keys):
            state = FindingState.NOT_APPLICABLE.value
            evidence_text = f"No collected data for: {', '.join(missing)}"
        else:
            state, evidence_text = _evaluate_state(control_def, eval_data, control_id)

        # Determine severity (YAML uses uppercase; model stores lowercase)
        raw_sev = (control_def.severity or "MEDIUM").upper()
        sev_map = {
            "CRITICAL": FindingSeverity.CRITICAL.value,
            "HIGH": FindingSeverity.HIGH.value,
            "MEDIUM": FindingSeverity.MEDIUM.value,
            "LOW": FindingSeverity.LOW.value,
            "INFORMATIONAL": FindingSeverity.INFORMATIONAL.value,
        }
        severity = sev_map.get(raw_sev, FindingSeverity.MEDIUM.value)

        risk_score = _risk_score(state, severity)

        finding = Finding(
            tenant_id=self.tenant_id,
            assessment_run_id=run_id,
            external_control_id=control_id,
            title=control_def.title,
            description=getattr(control_def, "description", "") or "",
            severity=severity,
            state=state,
            category=category,
            service=service,
            risk_score=risk_score,
        )

        if coverage_text:
            finding.evidence.append(
                FindingEvidence(
                    evidence_type="data_coverage",
                    source=f"control:{control_id}",
                    content=coverage_text[:10000],
                )
            )
        if evidence_text:
            finding.evidence.append(
                FindingEvidence(
                    evidence_type="api_evaluation",
                    source=f"control:{control_id}",
                    content=evidence_text[:10000],
                )
            )

        return finding


_STATUS_MAP = {
    "implemented": FindingState.IMPLEMENTED.value,
    "pass": FindingState.IMPLEMENTED.value,
    "partially_implemented": FindingState.PARTIALLY_IMPLEMENTED.value,
    "warning": FindingState.PARTIALLY_IMPLEMENTED.value,
    "not_implemented": FindingState.NOT_IMPLEMENTED.value,
    "fail": FindingState.NOT_IMPLEMENTED.value,
    "not_applicable": FindingState.NOT_APPLICABLE.value,
}

# Risk contribution of a finding at each severity when it is not implemented.
_SEVERITY_RISK = {
    FindingSeverity.CRITICAL.value: 10,
    FindingSeverity.HIGH.value: 8,
    FindingSeverity.MEDIUM.value: 5,
    FindingSeverity.LOW.value: 3,
    FindingSeverity.INFORMATIONAL.value: 1,
}


def _select_controls(all_controls: list[ControlDefinition], frameworks: list[str]) -> list[ControlDefinition]:
    """Controls mapped to any requested framework, or all of them if none match."""
    if not frameworks:
        return all_controls
    wanted = {name.lower() for name in frameworks}
    matched = [control for control in all_controls if any(fw.lower() in wanted for fw in control.compliance_mapping)]
    return matched or all_controls


def _evaluate_state(control_def: ControlDefinition, eval_data: dict[str, Any], control_id: str) -> tuple[str, str | None]:
    """Run the control's evaluate function, mapping its answer to a finding state."""
    try:
        raw = control_def.run_evaluate(eval_data)
    except Exception as exc:  # noqa: BLE001 - a broken control must not abort the run
        logger.debug("Control eval error", extra={"control": control_id, "error": str(exc)})
        return FindingState.NOT_IMPLEMENTED.value, f"Evaluation error: {exc}"
    return _STATUS_MAP.get(str(raw).lower(), FindingState.NOT_IMPLEMENTED.value), None


def _risk_score(state: str, severity: str) -> int:
    """Risk weight of a finding: zero when implemented or not applicable."""
    if state in (FindingState.IMPLEMENTED.value, FindingState.NOT_APPLICABLE.value):
        return 0
    base = _SEVERITY_RISK.get(severity, 5)
    return base // 2 if state == FindingState.PARTIALLY_IMPLEMENTED.value else base


def _apply_scores(run: AssessmentRun, scores: dict[str, Any], evaluated: int, passed: int) -> None:
    run.security_score = scores["security_score"]
    run.compliance_score = scores["compliance_score"]
    run.risk_score = scores["risk_score"]
    run.total_controls_checked = evaluated
    run.controls_passed = passed
    run.critical_count = scores["critical_count"]
    run.high_count = scores["high_count"]
    run.medium_count = scores["medium_count"]
    run.low_count = scores["low_count"]
    run.informational_count = scores["informational_count"]
    run.status = AssessmentStatus.COMPLETED.value
    run.completed_at = datetime.now(UTC)
