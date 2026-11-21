"""Rule engine shared by the posture analysers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# A check receives the resources grouped by type and returns
# ``(state, detail)`` where state is True (pass), False (fail) or None (not applicable).
CheckResult = tuple[bool | None, str]
Check = Callable[[dict[str, list[dict[str, Any]]]], CheckResult]

# A rule whose resources were absent is "not_applicable", never a pass.
_RULE_STATE = {True: "pass", False: "fail", None: "not_applicable"}


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    severity: str
    check: Check
    remediation: str = ""
    benchmark: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


def evaluate_rules(rules: list[Rule], resources: dict[str, list[dict[str, Any]]], *, benchmark: str = "") -> dict[str, Any]:
    """Evaluate a rule pack and return per-rule results with a benchmark score.

    ``None`` results are excluded from the score: a rule whose resources were not
    in the snapshot is not evidence of compliance or of failure.
    """
    results = []
    for rule in rules:
        try:
            state, detail = rule.check(resources)
        except Exception as exc:  # noqa: BLE001 — one malformed resource must not stop the pack
            state, detail = None, f"could not evaluate: {exc}"
        results.append(
            {
                "id": rule.id,
                "title": rule.title,
                "severity": rule.severity,
                "state": _RULE_STATE[state],
                "detail": detail,
                "remediation": rule.remediation,
                "tags": list(rule.tags),
            }
        )

    evaluated = [result for result in results if result["state"] != "not_applicable"]
    passed = sum(1 for result in evaluated if result["state"] == "pass")
    failed = len(evaluated) - passed
    score = round((passed / len(evaluated)) * 100, 2) if evaluated else None
    return {
        "benchmark": benchmark,
        "score": score,
        "rules_total": len(results),
        "evaluated": len(evaluated),
        "passed": passed,
        "failed": failed,
        "results": results,
    }


def pass_if(condition: bool, detail: str, failure: str) -> CheckResult:
    return (True, detail) if condition else (False, failure)


def no_resources(what: str) -> CheckResult:
    return None, f"no {what} in the snapshot"
