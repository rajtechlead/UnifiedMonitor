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
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.core.logging import get_logger
from unimonitor.db.models.assessment import AssessmentRun, AssessmentStatus
from unimonitor.db.models.finding import Finding, FindingEvidence, FindingSeverity, FindingState
from unimonitor.graph.collector_registry import CollectorRegistry
from unimonitor.grc.control_loader import ControlDefinition, ControlLoader
from unimonitor.grc.scoring import calculate_scores

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
            run_id=run.id,
            tenant_id=self.tenant_id,
            frameworks=frameworks,
        )

        # Mark as running
        run.status = AssessmentStatus.RUNNING.value
        await self.db.commit()

        try:
            # 1. Load controls via new ControlLoader (new list-format YAML)
            loader = ControlLoader()
            all_ctrl_defs = loader.load_all()
            # Filter by framework if specified
            if frameworks:
                fw_set = {f.lower() for f in frameworks}
                controls: list[ControlDefinition] = [
                    c for c in all_ctrl_defs
                    if any(fw.lower() in fw_set for fw in c.compliance_mapping.keys())
                ]
                if not controls:
                    controls = all_ctrl_defs  # fallback: run all if none match
            else:
                controls = all_ctrl_defs
            logger.info("Controls loaded", count=len(controls), run_id=run.id)

            # 2. Collect data from Graph API
            collector_registry = CollectorRegistry(
                tenant_id=self.entra_tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            collector_names = collectors or list(CollectorRegistry.ALL_COLLECTORS)
            collected_data = await collector_registry.collect_all(collector_names)
            logger.info("Data collected", collectors=len(collected_data), run_id=run.id)

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
                        control=control_def.id,
                        error=str(exc),
                        run_id=run.id,
                    )
                    return None

            tasks = [evaluate_one(c) for c in controls]
            results = await asyncio.gather(*tasks)
            findings = [f for f in results if f is not None]

            # 4. Persist findings
            for finding in findings:
                self.db.add(finding)
            await self.db.flush()

            # 5. Score the run
            scores = calculate_scores(findings)
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

            await self.db.commit()
            logger.info(
                "Assessment run completed",
                run_id=run.id,
                security_score=run.security_score,
                compliance_score=run.compliance_score,
                findings=len(findings),
            )
            return run

        except Exception as exc:
            logger.error("Assessment run failed", run_id=run.id, error=str(exc))
            run.status = AssessmentStatus.FAILED.value
            run.error_message = str(exc)[:2000]
            run.completed_at = datetime.now(UTC)
            await self.db.commit()
            raise

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

        state = FindingState.NOT_IMPLEMENTED.value
        evidence_text: str | None = None

        try:
            raw = control_def.run_evaluate(eval_data)
            # Normalise the return value
            status_map = {
                "implemented": FindingState.IMPLEMENTED.value,
                "pass": FindingState.IMPLEMENTED.value,
                "partially_implemented": FindingState.PARTIALLY_IMPLEMENTED.value,
                "warning": FindingState.PARTIALLY_IMPLEMENTED.value,
                "not_implemented": FindingState.NOT_IMPLEMENTED.value,
                "fail": FindingState.NOT_IMPLEMENTED.value,
                "not_applicable": FindingState.NOT_APPLICABLE.value,
            }
            state = status_map.get(str(raw).lower(), FindingState.NOT_IMPLEMENTED.value)
        except Exception as exc:
            logger.debug(
                "Control eval error",
                control=control_id,
                error=str(exc),
            )
            state = FindingState.NOT_IMPLEMENTED.value
            evidence_text = f"Evaluation error: {exc}"

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

        # Risk score (0 when implemented; proportional otherwise)
        severity_risk_map = {
            FindingSeverity.CRITICAL.value: 10,
            FindingSeverity.HIGH.value: 8,
            FindingSeverity.MEDIUM.value: 5,
            FindingSeverity.LOW.value: 3,
            FindingSeverity.INFORMATIONAL.value: 1,
        }
        base_risk = severity_risk_map.get(severity, 5)
        if state == FindingState.IMPLEMENTED.value:
            risk_score = 0
        elif state == FindingState.NOT_APPLICABLE.value:
            risk_score = 0
        elif state == FindingState.PARTIALLY_IMPLEMENTED.value:
            risk_score = base_risk // 2
        else:
            risk_score = base_risk

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

        if evidence_text:
            evidence = FindingEvidence(
                evidence_type="api_evaluation",
                source=f"control:{control_id}",
                content=evidence_text[:10000],
            )
            finding.evidence = [evidence]

        return finding
