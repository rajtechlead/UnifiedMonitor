"""Abstract base class for all report generators."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from unimonitor.config import get_settings


class BaseReportGenerator(ABC):
    """Base class all report generators inherit from.

    Accepts both ORM model instances and plain dicts for `run` and `findings`.
    ``output_dir`` overrides the default REPORTS_DIR from settings.
    """

    def __init__(
        self,
        run: Any,
        findings: list[Any],
        tenant_id: str = "",
        output_dir: str | None = None,
    ) -> None:
        self.run = run
        self.findings = findings
        self.tenant_id = tenant_id
        self._output_dir = output_dir
        self.settings = get_settings()

    @abstractmethod
    def generate(self, report_type: str = "full") -> str:
        """Generate the report and return the absolute file path."""

    def _get_run_id(self) -> str:
        """Return the run ID regardless of whether run is a dict or ORM object."""
        if isinstance(self.run, dict):
            return self.run.get("id", "unknown")
        return getattr(self.run, "id", "unknown")

    def _get_run_attr(self, key: str, default: Any = None) -> Any:
        """Get an attribute from run regardless of whether it's a dict or ORM object."""
        if isinstance(self.run, dict):
            return self.run.get(key, default)
        return getattr(self.run, key, default)

    def _get_finding_attr(self, finding: Any, key: str, default: Any = None) -> Any:
        """Get an attribute from a finding regardless of type."""
        if isinstance(finding, dict):
            return finding.get(key, default)
        return getattr(finding, key, default)

    def _get_output_path(self, ext: str) -> Path:
        """Return a unique output path for this run."""
        if self._output_dir:
            base = Path(self._output_dir)
        else:
            base = Path(self.settings.REPORTS_DIR) / self.tenant_id
        base.mkdir(parents=True, exist_ok=True)
        run_id = self._get_run_id()
        return base / f"{run_id}.{ext}"

    def _summary_stats(self) -> dict[str, Any]:
        """Return a dict of summary statistics across findings."""
        counts: dict[str, int] = {
            "CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFORMATIONAL": 0,
        }
        state_counts: dict[str, int] = {
            "implemented": 0, "partially_implemented": 0,
            "not_implemented": 0, "not_applicable": 0,
        }
        for f in self.findings:
            sev = (self._get_finding_attr(f, "severity") or "INFORMATIONAL").upper()
            counts[sev] = counts.get(sev, 0) + 1
            st = self._get_finding_attr(f, "state") or "not_implemented"
            state_counts[st] = state_counts.get(st, 0) + 1

        total = len(self.findings)
        passed = state_counts.get("implemented", 0) + state_counts.get("not_applicable", 0)
        return {
            "total_findings": total,
            "severity_counts": counts,
            "state_counts": state_counts,
            "pass_rate": round(passed / total * 100, 1) if total else 0.0,
            "security_score": self._get_run_attr("security_score"),
            "compliance_score": self._get_run_attr("compliance_score"),
            "risk_score": self._get_run_attr("risk_score"),
        }
