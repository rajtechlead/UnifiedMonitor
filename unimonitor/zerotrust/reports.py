"""Zero Trust assessment reports.

Every platform's assessment is written to an interactive HTML file under the install
directory's ``ZT assessments`` folder (override with ``UNIMONITOR_ZT_DIR``). The report
is self-contained — no CDN, no external font — so it opens from a file share or an
email attachment and still filters by pillar, status and text.
"""

from __future__ import annotations

import html
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from unimonitor.core.logging import get_logger

logger = get_logger(__name__)

REPORT_FOLDER = "ZT assessments"
REPORT_PREFIX = "ZT-Assessment"
MAX_REPORTS = 200


def zt_directory() -> Path:
    """The report folder: explicit override, then install directory, then data dir."""
    override = os.environ.get("UNIMONITOR_ZT_DIR", "").strip()
    if override:
        candidates = [Path(override)]
    else:
        install = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
        candidates = [install / REPORT_FOLDER, Path.home() / ".unimonitor" / REPORT_FOLDER]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError as exc:  # Program Files is often read-only for the service account
            logger.warning("zt_report_directory_unwritable", path=str(candidate), error=str(exc))
    raise OSError("No writable directory for Zero Trust reports")


def report_name(platform: str, when: datetime | None = None) -> str:
    stamp = (when or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    safe = "".join(char for char in platform if char.isalnum() or char in "-_") or "platform"
    return f"{REPORT_PREFIX}-{safe}-{stamp}.html"


def _status_class(status: str) -> str:
    return {"pass": "pass", "warn": "warn", "fail": "fail", "not_applicable": "na"}.get(status, "notrun")


def _rows(checks: list[dict[str, Any]]) -> str:
    rows = []
    for check in checks:
        remediation = "".join(f"<li>{html.escape(str(step))}</li>" for step in check.get("remediation") or [])
        rows.append(
            "<tr class='row' data-status='{status}' data-pillar='{pillar}'>"
            "<td class='id'>{cid}</td><td>{title}</td><td>{pillar}</td>"
            "<td><span class='badge {cls}'>{status}</span></td><td>{category}</td>"
            "<td>{remediation}</td></tr>".format(
                status=html.escape(str(check.get("status") or "not_run")),
                cls=_status_class(str(check.get("status") or "not_run")),
                pillar=html.escape(str(check.get("pillar") or "identity")),
                cid=html.escape(str(check.get("check_id") or "")),
                title=html.escape(str(check.get("title") or "")),
                category=html.escape(str(check.get("category") or "")),
                remediation=f"<ul>{remediation}</ul>" if remediation else "—",
            )
        )
    return "\n".join(rows)


def render_html(
    *,
    platform: str,
    catalogue: str,
    summary: dict[str, Any],
    checks: list[dict[str, Any]],
    tenant_name: str = "",
    engine: str = "python",
    generated_at: datetime | None = None,
) -> str:
    """A standalone, interactive report (filter by status, pillar or text)."""
    generated = (generated_at or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M UTC")
    pillars = sorted({str(check.get("pillar") or "identity") for check in checks})
    statuses = ["pass", "warn", "fail", "not_run", "not_applicable"]
    pillar_options = "".join(f"<option value='{html.escape(p)}'>{html.escape(p)}</option>" for p in pillars)
    status_options = "".join(f"<option value='{s}'>{s.replace('_', ' ')}</option>" for s in statuses)
    payload = json.dumps(summary.get("pillars", {}), sort_keys=True)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(REPORT_PREFIX)} · {html.escape(platform)}</title>
<style>
:root {{ color-scheme: light dark; --bg:#f6f7f9; --card:#fff; --text:#101828; --muted:#667085; --line:#e4e7ec; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0b1220; --card:#111a2c; --text:#e6e9ef; --muted:#98a2b3; --line:#22304a; }} }}
body {{ margin:0; font:14px/1.45 system-ui,Segoe UI,Roboto,sans-serif; background:var(--bg); color:var(--text); }}
header {{ padding:24px 28px; border-bottom:1px solid var(--line); background:var(--card); }}
h1 {{ margin:0 0 4px; font-size:20px; }}
.sub {{ color:var(--muted); font-size:12px; }}
.wrap {{ padding:20px 28px 48px; }}
.cards {{ display:flex; gap:12px; flex-wrap:wrap; margin:16px 0; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 16px; min-width:110px; }}
.card b {{ display:block; font-size:22px; }}
.card span {{ color:var(--muted); font-size:12px; }}
.controls {{ display:flex; gap:8px; flex-wrap:wrap; margin:12px 0 16px; }}
select,input {{ padding:7px 10px; border:1px solid var(--line); border-radius:7px; background:var(--card); color:var(--text); fontSize:13px; }}
table {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); border-radius:10px; overflow:hidden; }}
th,td {{ text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top; font-size:12px; }}
th {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.03em; }}
td.id {{ font-family:ui-monospace,Consolas,monospace; white-space:nowrap; }}
ul {{ margin:0; padding-left:16px; }}
.badge {{ padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; }}
.pass {{ background:#d1fadf; color:#05603a; }} .warn {{ background:#fef0c7; color:#93370d; }}
.fail {{ background:#fee4e2; color:#b42318; }} .notrun {{ background:#eaecf0; color:#475467; }}
.na {{ background:#e0eaff; color:#1d4ed8; }}
</style></head><body>
<header>
  <h1>{html.escape(catalogue)}</h1>
  <div class="sub">{html.escape(platform)} · {html.escape(tenant_name or "tenant")} · generated {generated} · engine {html.escape(engine)}</div>
</header>
<div class="wrap">
  <div class="cards">
    <div class="card"><b>{summary.get("score", 0):.1f}%</b><span>score</span></div>
    <div class="card"><b>{summary.get("passed", 0)}</b><span>pass</span></div>
    <div class="card"><b>{summary.get("warned", 0)}</b><span>warn</span></div>
    <div class="card"><b>{summary.get("failed", 0)}</b><span>fail</span></div>
    <div class="card"><b>{summary.get("not_run", 0)}</b><span>not run</span></div>
    <div class="card"><b>{summary.get("total", 0)}</b><span>tests</span></div>
  </div>
  <div class="controls">
    <input id="q" placeholder="Filter by test id or title" aria-label="Filter tests" style="min-width:240px">
    <select id="pillar" aria-label="Filter by pillar"><option value="">All pillars</option>{pillar_options}</select>
    <select id="status" aria-label="Filter by status"><option value="">All statuses</option>{status_options}</select>
  </div>
  <table><thead><tr><th>Test</th><th>Title</th><th>Pillar</th><th>Status</th><th>Category</th><th>Remediation</th></tr></thead>
  <tbody id="rows">{_rows(checks)}</tbody></table>
  <p class="sub">Pillar scores: <code>{html.escape(payload)}</code></p>
</div>
<script>
(function () {{
  var q = document.getElementById('q'), p = document.getElementById('pillar'), s = document.getElementById('status');
  function apply() {{
    var text = (q.value || '').toLowerCase(), pillar = p.value, status = s.value;
    document.querySelectorAll('#rows .row').forEach(function (row) {{
      var haystack = row.textContent.toLowerCase();
      var ok = (!text || haystack.indexOf(text) !== -1) && (!pillar || row.dataset.pillar === pillar) && (!status || row.dataset.status === status);
      row.style.display = ok ? '' : 'none';
    }});
  }}
  [q, p, s].forEach(function (el) {{ el.addEventListener('input', apply); el.addEventListener('change', apply); }});
}})();
</script>
</body></html>"""


def write_report(content: str, platform: str, when: datetime | None = None) -> Path:
    """Write the report atomically and return its path."""
    name = report_name(platform, when)
    target = zt_directory() / name
    temporary = target.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, target)
    logger.info("zt_report_written", path=str(target), platform=platform)
    return target


def list_reports() -> list[dict[str, Any]]:
    """Newest first, bounded so a long-lived install cannot return unbounded rows."""
    directory = zt_directory()
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob(f"{REPORT_PREFIX}-*.html"), key=lambda item: item.stat().st_mtime, reverse=True)[:MAX_REPORTS]:
        stat = path.stat()
        rows.append(
            {
                "name": path.name,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC),
                "platform": path.name.removeprefix(f"{REPORT_PREFIX}-").rsplit("-", 2)[0],
            }
        )
    return rows


def resolve_report(name: str) -> Path:
    """Only a file this module wrote, inside the report folder — never a path."""
    if "/" in name or "\\" in name or ".." in name or not name.startswith(REPORT_PREFIX):
        raise ValueError("Unknown report")
    path = zt_directory() / name
    if not path.is_file():
        raise ValueError("Unknown report")
    return path


__all__ = ["REPORT_FOLDER", "list_reports", "render_html", "report_name", "resolve_report", "write_report", "zt_directory"]
