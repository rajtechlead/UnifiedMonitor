"""Abstract base class for all report generators."""

from __future__ import annotations

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

    @staticmethod
    def _hex_to_rgb(hex_colour: str) -> tuple[float, float, float]:
        """Convert ``#RRGGBB`` to a ReportLab/0-1 RGB tuple."""
        raw = hex_colour.lstrip("#")
        return tuple(int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]

    def _provider_breakdown(self) -> list[dict[str, Any]]:
        """Group findings by cloud provider for multi-cloud report sections.

        Returns one entry per provider that actually reported findings, in the
        registry's display order. The aggregate figures elsewhere in the report
        are unchanged — this is an additional breakdown, not a replacement.
        """
        from unimonitor.grc.providers import PROVIDERS, provider_for_service
        from unimonitor.grc.scoring import compute_score

        grouped: dict[str, list[Any]] = {pid: [] for pid in PROVIDERS}
        for f in self.findings:
            provider = provider_for_service(self._get_finding_attr(f, "service"))
            if provider is not None:
                grouped[provider.id].append(f)

        breakdown: list[dict[str, Any]] = []
        for pid, provider in PROVIDERS.items():
            rows = grouped[pid]
            if not rows:
                continue

            severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFORMATIONAL": 0}
            states = {"implemented": 0, "partially_implemented": 0, "not_implemented": 0, "not_applicable": 0}
            raw: list[dict[str, Any]] = []
            for f in rows:
                sev = (self._get_finding_attr(f, "severity") or "INFORMATIONAL").upper()
                severity[sev] = severity.get(sev, 0) + 1
                state = self._get_finding_attr(f, "state") or "not_implemented"
                states[state] = states.get(state, 0) + 1
                raw.append({"severity": sev, "state": state})

            total = len(rows)
            passed = states["implemented"] + states["not_applicable"]
            breakdown.append(
                {
                    "id": pid,
                    "name": provider.name,
                    "short_name": provider.short_name,
                    "description": provider.description,
                    "colour": provider.colour,
                    "rgb": self._hex_to_rgb(provider.colour),
                    "findings": rows,
                    "total": total,
                    "severity_counts": severity,
                    "state_counts": states,
                    "pass_rate": round(passed / total * 100, 1) if total else 0.0,
                    "security_score": compute_score(raw),
                }
            )
        return breakdown

    def _summary_stats(self) -> dict[str, Any]:
        """Return a dict of summary statistics across findings."""
        counts: dict[str, int] = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "INFORMATIONAL": 0,
        }
        state_counts: dict[str, int] = {
            "implemented": 0,
            "partially_implemented": 0,
            "not_implemented": 0,
            "not_applicable": 0,
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
