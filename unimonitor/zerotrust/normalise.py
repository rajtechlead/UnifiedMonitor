"""Turn a Zero Trust Assessment export into UniMonitor's check shape.

Microsoft's export has changed shape between releases, so this accepts a list, a
report object, or an object mapping ids to checks, and looks each field up under
the names every release has used. Unknown results become ``not_run`` rather than
a pass: an assessment that could not evaluate a test must not look green.
"""

from __future__ import annotations

from typing import Any

from unimonitor.grc.pillars import PILLAR_IDS, PILLARS, pillar_for

PLATFORMS: dict[str, str] = {
    "microsoft": "Microsoft 365",
    "aws": "Amazon Web Services",
    "gcp": "Google Cloud",
    "google_workspace": "Google Workspace",
}

SEVERITIES = frozenset({"critical", "high", "medium", "low", "informational"})

_ID_KEYS = ("TestId", "testId", "TestID", "Id", "id", "CheckId", "checkId", "controlId", "ControlId")
_TITLE_KEYS = ("Title", "title", "Name", "name", "TestTitle")
_STATUS_KEYS = ("Result", "result", "Status", "status", "TestResult", "Outcome", "outcome")
_SEVERITY_KEYS = ("Risk", "risk", "RiskLevel", "riskLevel", "Severity", "severity")
_PILLAR_KEYS = ("Pillar", "pillar", "ZeroTrustPillar")
_REMEDIATION_KEYS = ("Remediation", "remediation", "RemediationSteps", "remediationSteps", "RecommendedAction")
_REFERENCE_KEYS = ("Reference", "reference", "Link", "link", "Url", "url", "DocUrl")
_CATEGORY_KEYS = ("Category", "category", "Service", "service")

_STATUS_MAP: dict[str, str] = {
    "pass": "pass",
    "passed": "pass",
    "succeeded": "pass",
    "success": "pass",
    "true": "pass",
    "ok": "pass",
    "fail": "fail",
    "failed": "fail",
    "failure": "fail",
    "false": "fail",
    "warn": "warn",
    "warning": "warn",
    "warned": "warn",
    "investigate": "warn",
    "partial": "warn",
    "skipped": "not_run",
    "skip": "not_run",
    "notrun": "not_run",
    "not_run": "not_run",
    "not started": "not_run",
    "error": "not_run",
    "unknown": "not_run",
    "n/a": "not_applicable",
    "na": "not_applicable",
    "notapplicable": "not_applicable",
    "not_applicable": "not_applicable",
}

# Text that identifies a pillar when a check does not declare one. Ordered: the
# first match wins, so "device compliance" is Devices, not Identity.
_PILLAR_WORDS: tuple[tuple[str, str], ...] = (
    ("copilot", "ai"),
    ("openai", "ai"),
    ("artificial intelligence", "ai"),
    ("ai ", "ai"),
    ("siem", "secops"),
    ("sentinel", "secops"),
    ("incident", "secops"),
    ("alert", "secops"),
    ("detection", "secops"),
    ("monitoring", "secops"),
    ("device", "devices"),
    ("intune", "devices"),
    ("endpoint", "devices"),
    ("firewall", "network"),
    ("network", "network"),
    ("vpn", "network"),
    ("segmentation", "network"),
    ("private access", "network"),
    ("dns", "network"),
    ("label", "data"),
    ("dlp", "data"),
    ("data loss", "data"),
    ("sensitivity", "data"),
    ("sharepoint", "data"),
    ("retention", "data"),
    ("storage", "infrastructure"),
    ("bucket", "infrastructure"),
    ("infrastructure", "infrastructure"),
    ("subscription", "infrastructure"),
    ("virtual machine", "infrastructure"),
    ("patching", "infrastructure"),
    ("logging", "infrastructure"),
    ("cloudtrail", "infrastructure"),
    ("guardduty", "infrastructure"),
    ("config", "infrastructure"),
    ("mfa", "identity"),
    ("multi-factor", "identity"),
    ("authentication", "identity"),
    ("sign-in", "identity"),
    ("conditional access", "identity"),
    ("privilege", "identity"),
    ("admin", "identity"),
    ("guest", "identity"),
    ("password", "identity"),
    ("application", "identity"),
)


def _first(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def _as_status(value: Any) -> str:
    if isinstance(value, bool):
        return "pass" if value else "fail"
    text = str(value or "").strip().lower()
    return _STATUS_MAP.get(text, "not_run")


def _as_severity(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in SEVERITIES:
        return text
    if text in {"info", "informational", "none"}:
        return "informational"
    return "medium"


def _as_remediation(value: Any) -> list[str]:
    """Remediation arrives as a string, a list of strings, or a list of dicts."""
    if not value:
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    steps: list[str] = []
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, str) and entry.strip():
                steps.append(entry.strip())
            elif isinstance(entry, dict):
                text = _first(entry, ("action", "Action", "step", "Step", "text", "Text"))
                if text:
                    steps.append(str(text).strip())
    return steps


def pillar_for_text(text: str) -> str | None:
    """Best-effort pillar from free text, used when a check does not say."""
    lowered = text.lower()
    for word, pillar in _PILLAR_WORDS:
        if word in lowered:
            return pillar
    return None


def _extract(payload: Any) -> list[dict[str, Any]]:
    """Find the list of checks inside whatever container the export used."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("tests", "Tests", "results", "Results", "checks", "Checks", "items", "Items", "data", "Data", "value"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
        if isinstance(candidate, dict):
            nested = _extract(candidate)
            if nested:
                return nested
    # A report keyed by test id: {"21770": {...}, "21771": {...}}
    keyed = [(key, item) for key, item in payload.items() if isinstance(item, dict)]
    if keyed and any(_first(item, _TITLE_KEYS) for _, item in keyed):
        return [{"Id": key, **item} if _first(item, _ID_KEYS) is None else item for key, item in keyed]
    # Pillar sections, or any other nesting the release introduced: walk the tree
    # and collect every object that looks like one test row.
    found: list[dict[str, Any]] = []
    _walk(payload, found, depth=0)
    return found


def _looks_like_check(item: dict[str, Any]) -> bool:
    has_title = bool(_first(item, _TITLE_KEYS))
    has_status = _first(item, _STATUS_KEYS) is not None
    has_id = _first(item, _ID_KEYS) is not None
    return has_title and has_status and has_id


def _walk(node: Any, out: list[dict[str, Any]], depth: int) -> None:
    if depth > 6:
        return
    if isinstance(node, dict):
        if _looks_like_check(node):
            out.append(node)
            return
        for value in node.values():
            _walk(value, out, depth + 1)
    elif isinstance(node, list):
        for value in node:
            _walk(value, out, depth + 1)


def _pillar_for(item: dict[str, Any], title: str, category: str) -> str:
    """The pillar a test row belongs to; identity when it does not say."""
    declared = _first(item, _PILLAR_KEYS)
    pillar = pillar_for(str(declared)) if declared else None
    pillar = pillar or pillar_for_text(f"{title} {category}")
    if pillar is None or pillar not in PILLAR_IDS:
        return "identity"
    return pillar


def _check_from_item(item: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """One normalised check, or None when the row has neither a title nor an id."""
    title = str(_first(item, _TITLE_KEYS) or "").strip()
    raw_id = _first(item, _ID_KEYS)
    if not title and raw_id is None:
        return None
    check_id = str(raw_id).strip() if raw_id not in (None, "") else (title[:64] or "unknown")
    category = str(_first(item, _CATEGORY_KEYS) or "").strip()
    return check_id, {
        "check_id": check_id,
        "title": title or check_id,
        "pillar": _pillar_for(item, title, category),
        "severity": _as_severity(_first(item, _SEVERITY_KEYS)),
        "status": _as_status(_first(item, _STATUS_KEYS)),
        "category": category,
        "remediation": _as_remediation(_first(item, _REMEDIATION_KEYS)),
        "reference": str(_first(item, _REFERENCE_KEYS) or ""),
    }


def normalise_checks(payload: Any) -> list[dict[str, Any]]:
    """Normalise an assessment export into UniMonitor check dicts.

    Each check carries ``check_id``, ``title``, ``pillar``, ``severity``,
    ``status``, ``category``, ``remediation`` (list of steps) and ``reference``.
    """
    checks: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in _extract(payload):
        parsed = _check_from_item(item)
        if parsed is None:
            continue
        check_id, check = parsed
        if check_id in seen:
            continue
        seen.add(check_id)
        checks.append(check)

    return checks


def summarise(checks: list[dict[str, Any]]) -> dict[str, Any]:
    """Score a set of checks overall and per pillar.

    ``warn`` counts half and ``not_run`` / ``not_applicable`` are excluded, so a
    tenant cannot raise its score by making tests fail to execute.
    """
    counts = {"pass": 0, "fail": 0, "warn": 0, "not_run": 0, "not_applicable": 0}
    per_pillar: dict[str, dict[str, int]] = {pillar.id: {"pass": 0, "fail": 0, "warn": 0, "not_run": 0, "not_applicable": 0} for pillar in PILLARS}

    for check in checks:
        status = check.get("status", "not_run")
        counts[status] = counts.get(status, 0) + 1
        bucket = per_pillar.setdefault(check.get("pillar", "identity"), {"pass": 0, "fail": 0, "warn": 0, "not_run": 0, "not_applicable": 0})
        bucket[status] = bucket.get(status, 0) + 1

    def score_for(bucket: dict[str, int]) -> float:
        applicable = bucket["pass"] + bucket["fail"] + bucket["warn"]
        if not applicable:
            return 0.0
        return round((bucket["pass"] + bucket["warn"] * 0.5) / applicable * 100, 2)

    pillars = []
    for pillar in PILLARS:
        bucket = per_pillar[pillar.id]
        total = sum(bucket.values())
        pillars.append(
            {
                "id": pillar.id,
                "name": pillar.name,
                "total": total,
                "passed": bucket["pass"],
                "failed": bucket["fail"],
                "warned": bucket["warn"],
                "not_run": bucket["not_run"],
                "score": score_for(bucket),
            }
        )

    return {
        "total": len(checks),
        "passed": counts["pass"],
        "failed": counts["fail"],
        "warned": counts["warn"],
        "not_run": counts["not_run"],
        "not_applicable": counts["not_applicable"],
        "score": score_for(counts),
        "pillars": pillars,
    }
