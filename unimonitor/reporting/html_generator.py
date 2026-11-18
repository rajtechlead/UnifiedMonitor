"""Self-contained HTML report generator.

Mirrors the HTML reports M365 Sheppard and the Microsoft Zero Trust Assessment
produce: one file that opens in any browser, no assets or network, suitable for
emailing to a customer. Data is escaped, so a finding title cannot inject markup.
"""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape

from unimonitor.reporting.base import BaseReportGenerator

_SEVERITY_ORDER = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL")
_SEVERITY_COLOUR = {
    "CRITICAL": "#b91c1c",
    "HIGH": "#c2410c",
    "MEDIUM": "#a16207",
    "LOW": "#1d4ed8",
    "INFORMATIONAL": "#475569",
}


class HtmlReportGenerator(BaseReportGenerator):
    """Generates a single-file HTML report with summary, providers and findings."""

    def generate(self, report_type: str = "full") -> str:
        output_path = self._get_output_path("html")
        stats = self._summary_stats()
        providers = self._provider_breakdown()
        g = self._get_finding_attr

        cards = "".join(
            f'<div class="card"><span class="label">{escape(str(name.title()))}</span>'
            f'<span class="value" style="color:{_SEVERITY_COLOUR[name]}">{count}</span></div>'
            for name, count in stats["severity_counts"].items()
        )
        provider_rows = "".join(
            f"<tr><td><span class='dot' style='background:{escape(p['colour'])}'></span>"
            f"{escape(p['name'])}</td><td>{p['total']}</td><td>{p['pass_rate']}%</td>"
            f"<td>{p['security_score']}</td></tr>"
            for p in providers
        )
        findings_rows = "".join(
            "<tr>"
            f"<td class='mono'>{escape(str(g(f, 'external_control_id') or g(f, 'control_id') or ''))}</td>"
            f"<td>{escape(str(g(f, 'title', '')))}</td>"
            f"<td><span class='sev' style='color:{_SEVERITY_COLOUR.get((g(f, 'severity') or '').upper(), '#475569')}'>"
            f"{escape(str(g(f, 'severity', '')).upper())}</span></td>"
            f"<td>{escape(str(g(f, 'category', '')))}</td>"
            f"<td>{escape(str(g(f, 'state', '')).replace('_', ' '))}</td>"
            "</tr>"
            for f in sorted(
                self.findings,
                key=lambda f: (
                    _SEVERITY_ORDER.index((g(f, "severity") or "INFORMATIONAL").upper())
                    if (g(f, "severity") or "").upper() in _SEVERITY_ORDER
                    else len(_SEVERITY_ORDER)
                ),
            )
        )

        def score_card(label: str, value: float | None) -> str:
            shown = value if value is not None else "—"
            return f'<div class="card"><span class="label">{label}</span><span class="value">{shown}</span></div>'

        document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>UniMonitor — {escape(report_type.title())} report</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;padding:32px;background:#f8fafc;color:#0f172a}}
h1{{margin:0 0 4px;font-size:24px}} .muted{{color:#64748b;font-size:13px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px;min-width:110px}}
.card .label{{display:block;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#64748b}}
.card .value{{font-size:24px;font-weight:700}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e2e8f0;
border-radius:10px;overflow:hidden;font-size:13px;margin-bottom:24px}}
th{{text-align:left;padding:10px 12px;background:#f1f5f9;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#475569}}
td{{padding:9px 12px;border-top:1px solid #eef2f7;vertical-align:top}}
.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;white-space:nowrap}}
.sev{{font-weight:700;font-size:11px}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px}}
h2{{font-size:15px;margin:24px 0 8px}}
</style></head><body>
<h1>UniMonitor {escape(report_type.title())} Report</h1>
<div class="muted">Generated {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")} ·
{stats["total_findings"]} findings · pass rate {stats["pass_rate"]}%</div>
<div class="cards">
{score_card("Security", stats["security_score"])}
{score_card("Compliance", stats["compliance_score"])}
{score_card("Risk", stats["risk_score"])}
{cards}
</div>
<h2>Cloud providers</h2>
<table><thead><tr><th>Provider</th><th>Findings</th><th>Pass rate</th><th>Score</th></tr></thead>
<tbody>{provider_rows or "<tr><td colspan='4' class='muted'>No provider data</td></tr>"}</tbody></table>
<h2>Findings</h2>
<table><thead><tr><th>Control</th><th>Title</th><th>Severity</th><th>Category</th><th>State</th></tr></thead>
<tbody>{findings_rows or "<tr><td colspan='5' class='muted'>No findings</td></tr>"}</tbody></table>
</body></html>
"""
        output_path.write_text(document, encoding="utf-8")
        return str(output_path)
