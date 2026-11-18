# Gap Analysis — UniMonitor against M365 Sheppard, Vigil365 and the Microsoft Zero Trust Assessment

Last updated: 2026-11-18
Companion document: [Comparison.MD](Comparison.MD)

## 1. Method

Each reference repository was cloned and read at directory, model and entry-point level
(control definitions, API surface, pages, background tasks). Each capability was then checked
against UniMonitor's actual code — control library, `unimonitor/api/v1/*`, `unimonitor/db/models/*`,
`unimonitor/worker/tasks/*` and `frontend/src/pages/*` — not against its README claims.

A gap is recorded when the reference implementation offers a capability a user would notice and
UniMonitor has no equivalent. Gaps that describe a different product shape (a terminal UI, a .NET
service host, a PowerShell check body) are recorded as **Not applicable** with the reason, not
silently dropped.

Dispositions:

- **Merged** — implemented in UniMonitor in this change, with a test.
- **Partially merged** — the useful model is merged; the reference's bulk data/checks are not.
- **Deferred** — real gap, deliberately not built now; reason recorded.
- **Not applicable** — conflicts with UniMonitor's architecture or adds no user value.
- **Fixed** — a UniMonitor defect that the comparison exposed.

---

## 2. Gap register

| ID | Source | Capability | UniMonitor before | Severity | Disposition |
|---|---|---|---|---|---|
| GAP-01 | Vigil365 (working MSAL) | "Sign in with Microsoft" on the login page | Button hit a 404 route, the callback's token fragment was never read, and the provisioned app had no web redirect URI | **Critical** | **Fixed** |
| GAP-02 | all three | Reports actually generate | Worker `await`ed a synchronous generator, so every build was marked failed | **Critical** | **Fixed** |
| GAP-03 | Vigil365 | Findings list usable end-to-end | Page sent `limit`/`offset`, filtered on states the API never returns, and rendered fields the API does not send | **High** | **Fixed** |
| GAP-04 | Sheppard | ROI remediation ranking (impact ÷ effort) | Findings sortable by risk only; no effort model | Medium | **Merged** |
| GAP-05 | Sheppard, ZT | Single-file HTML report | PDF/DOCX/Excel/CSV/JSON only | Medium | **Merged** |
| GAP-06 | Vigil365 | Alert policy engine (metric, activity, anomaly rules with thresholds) | Notification severity threshold + digests only; no rule objects, no evaluation loop | High | **Merged** |
| GAP-07 | Vigil365 | Alert lifecycle: acknowledge, snooze, assign, resolve, notes | Compliance state only (`implemented` …), no handler workflow | High | **Merged** |
| GAP-08 | Vigil365 | Entity investigation timeline | Finding history endpoint existed; no merged timeline in the UI | Medium | **Merged** |
| GAP-09 | Vigil365 | Licence posture page (paid-but-unused, needs-another-licence) | Copilot controls only; no `subscribedSkus` view | Medium | **Merged** |
| GAP-10 | Vigil365 | Service health and M365 connectivity pages | No `serviceHealth` collector or page | Medium | **Merged** |
| GAP-11 | Vigil365 | Global search palette (Ctrl+K) and saved filter presets | Findings text search only | Low | **Merged** (search; filter presets not built) |
| GAP-12 | ZT Assessment | 364 Microsoft-authored assessment checks, seven pillars | 180 controls; Zero Trust mappings present but no pillar roll-up | High | **Partially merged** |
| GAP-13 | Sheppard | Interactive terminal UI | Web UI only | Low | **Not applicable** |
| GAP-14 | Sheppard | OSINT threat-intelligence controls (2) | No external feed ingestion | Low | **Deferred** |
| GAP-15 | ZT Assessment | Pillar coverage view | No pillar view despite mappings existing | Medium | **Merged** |
| GAP-16 | Vigil365 | Tamper-evident (SHA-256 hash-chained) audit trail | `audit_logs` table and Audit page, no chain | Medium | **Merged** |
| GAP-17 | Vigil365 | MSP staff scoping and per-client rollup | Tenant isolation and aggregate views exist; no per-staff scoping | Low | **Deferred** |
| GAP-18 | Vigil365 | SQL Server **and** PostgreSQL providers | SQLAlchemy supports both; only SQLite/PostgreSQL are exercised | Low | **Not applicable** |
| GAP-19 | Vigil365 | Auto-starting Windows service installer | Existing NSIS installer + optional service | — | **Already present** |
| GAP-20 | Vigil365 | Conditional Access gap analysis / recommendations hub | CA controls and `/grc/gap-analysis` exist; no combined recommendations page | Low | **Partially merged** (covered by existing GRC gap analysis) |

---

## 3. Detail

### GAP-01 — Microsoft sign-in (Critical, fixed)

Three independent faults meant the button could never work:

1. `frontend/src/pages/LoginPage.tsx` navigated to `/api/v1/auth/entra/login`; the route is
   `GET /api/v1/auth/login`. Every attempt was a 404.
2. `unimonitor/api/v1/auth.py` returned the tokens in the URL **fragment**
   (`#access_token=…`), and neither `main.tsx` nor `authStore` read it. Even a successful
   round-trip landed the user back on the login page.
3. `unimonitor/onboarding/m365.py` created the app registration without a `web.redirectUris`
   entry, so Entra rejected the callback with `AADSTS50011` (redirect URI mismatch).

Fixes: correct route; `main.tsx` consumes and clears the fragment and loads `/auth/me` before
first render; provisioning registers `ENTRA_REDIRECT_URI` on the app; `GET /auth/sso` reports
whether SSO is configured so the button is disabled with an explanation instead of failing; the
callback redirects to `UNIMONITOR_FRONTEND_URL` (or the same origin) rather than depending on a
CORS entry.

Remaining prerequisite: the tenant's administrator must consent to the delegated scopes
(`User.Read`, `Organization.Read.All`) on first use. This is a tenant policy step, not a code gap.

### GAP-02 — Report generation (Critical, fixed)

`unimonitor/worker/tasks/reporting.py` called `await gen.generate(...)`. All five generators are
synchronous and return a `str`, so the await raised `TypeError`, the exception was swallowed per
format, and the report row was set to `failed`. The call is now synchronous, and HTML was added to
the same registry.

Three more faults in the same pipeline: the download endpoint looked for
`REPORT_STORAGE_PATH/{report_id}.{ext}` while generators wrote
`REPORT_STORAGE_PATH/{tenant_id}/{run_id}.{ext}`; the UI asked for
`/reports/{id}/download/{format}` while the API served only `/reports/{id}/download`; and both
status and delete imported a `ReportRepository` that does not exist, so those paths always fell
through to their fallbacks. Download now serves the per-format file map stored on the report,
status and delete query the `Report` model directly, and delete removes the generated files.

### GAP-03 — Findings page (High, fixed)

The page assumed `control_id`, `framework`, `created_at`, `evidence_summary`, `remediation_summary`
and a `PATCH /findings/{id}` endpoint. None exist. It also defaulted the state filter to `open`,
which is not a finding state, so the default view was always empty. The page now uses
`external_control_id`, `category`, `first_detected_at`, `ai_remediation`, pagination
(`page`/`page_size`) and `PATCH /findings/{id}/state`.

### GAP-04 — ROI ranking (merged)

`GET /api/v1/findings/priority` returns open, unsuppressed findings ranked by
`(impact × 10 + risk_score) ÷ effort`. `impact` defaults to the severity weight and `effort` to 3
(1 = trivial, 5 = major project); both are optional per-control YAML keys now parsed by
`ControlLoader`. This mirrors Sheppard's severity ÷ complexity ordering without importing its
scoring module. The Findings page shows the top five as "Fix first".

### GAP-05 — HTML report (merged)

`unimonitor/reporting/html_generator.py` writes one self-contained file: summary cards, provider
breakdown, findings sorted by severity. All interpolated values are HTML-escaped (tested with a
`<script>` title). Registered in the report API (`html` format, `text/html` download), the worker
registry and the Reports page.

### GAP-06 — Alert policy engine (merged)

`AlertPolicy` carries a metric, comparator, threshold, window, severity and kind
(`metric`, `activity`, `anomaly`); `Alert` is one triggered occurrence with assignee, notes, snooze
and resolve timestamps. Six metrics are supported: unresolved critical/high/all findings, average
finding risk, findings first seen in the window, and security-score drop over the window. Five
ready-made templates (critical findings, high-findings spike, new findings, score drop, risk spike)
are exposed by `GET /alerts/templates` and copyable with one call.

`unimonitor/alerts/engine.py` evaluates per tenant, does not raise a second alert for a policy that
already has an unresolved alert inside its window, writes an audit entry and dispatches through the
existing notification channels (`NotificationDispatcher.send_alert`). Evaluation runs from the beat
schedule and on demand (`POST /alerts/evaluate`). The UI is the **Alerts** page: summary tiles,
policy list with enable/delete, and Ack / Snooze / Resolve on each alert.

### GAP-07 — Triage workflow (merged)

`findings.triage_status` (`open`, `acknowledged`, `snoozed`, `resolved`), `assignee_id` and
`snoozed_until` are new columns (migration `002`). `POST /findings/{id}/triage` validates the
status, defaults a snooze to 24 hours, records a `FindingHistory` row and writes an
`AuditLog` entry. Deliberately separate from `state`, which answers "is the control
implemented"; triage answers "who is handling it". The Findings page exposes it as a column and
filter.

### GAP-08 — Investigation timeline (merged)

`GET /findings/{id}/timeline` merges finding-history changes and collected evidence into one
time-ordered list; the Findings detail panel renders it. UniMonitor has no user/device entity
graph, so the timeline is per finding rather than Vigil365's per identity.

### GAP-12 / GAP-15 — Zero Trust model (pillar view merged, checks not ported)

Every UniMonitor control already declares `compliance_mapping.zero_trust` values such as
`identity.verify_explicitly` and `endpoints.threat_protection`. `unimonitor/grc/pillars.py` maps
those prefixes (with aliases `endpoints → devices`, `apps → data`) onto the seven Microsoft
pillars, and `GET /dashboard/zero-trust` computes coverage from persisted finding states. Pillars
with no mapped control report `uncovered` rather than a misleading 100%. The new Zero Trust page
shows all seven.

The 364 PowerShell checks were **not** copied. They duplicate control logic already expressed in
YAML for Microsoft services, are Microsoft-only, and importing them would create two competing
sources of truth with no test parity. Where the ZT checks cover a capability UniMonitor lacks
(licence posture, service health), that is tracked separately as GAP-09/GAP-10.

### GAP-14 — OSINT controls (deferred)

Sheppard's two OSINT controls depend on external reputation feeds. UniMonitor has no feed
ingestion contract, credentials or rate-limit handling; adding two YAML controls would produce
findings that are always `not_implemented`. Deferred until a feed is chosen.

### GAP-16 — Hash-chained audit (merged)

`audit_logs` gained `prev_hash` and `entry_hash` (migration `003`). `unimonitor/core/audit.py`
writes each entry as SHA-256 over the previous hash plus the row's content, and `verify_chain`
recomputes the chain, reporting the first break while tolerating rows written before the chain
existed. Writes now cover finding triage, alert trigger/status changes, policy creation and manual
collection. `GET /dashboard/audit/verify` powers the verified/broken badge on the Audit page.

### GAP-13 — Terminal UI (not applicable)

Sheppard's TUI is an interface for a single-operator CLI. UniMonitor is a multi-user web platform
with RBAC and tenant isolation; a TUI would duplicate the API without serving the same users.

### GAP-17 … GAP-20 (partial / not applicable)

- Staff scoping: tenants are isolated, but every admin sees every tenant. Acceptable for a
  single-org deployment; an MSP edition needs a `user_tenant` assignment table.
- SQL Server: SQLAlchemy would emit T-SQL, but only SQLite and PostgreSQL are in CI. Claiming
  SQL Server support would be untested, so it is not claimed.
- Windows service: already shipped by the existing installer path.
- Recommendations hub: `/grc/gap-analysis` already returns unimplemented controls per framework,
  which is the actionable content; a separate page is UI work, not a capability gap.

---

### GAP-09 / GAP-10 / GAP-11 — Licence, service health, search (merged)

- **Licence posture:** `GET /monitoring/licensing` reads `/subscribedSkus` and returns per-SKU
  purchased/assigned/available seats, utilisation and a status (`healthy`, `unused`, `over`,
  `suspended`). The **Licences** page shows the summary and the SKU table.
- **Service health:** `GET /monitoring/service-health` reads `healthOverviews` and unresolved
  `issues`; the **Service Health** page shows per-service status and open advisories. Requires the
  new optional `ServiceHealth.Read.All` permission.
- **Global search:** `GET /search?q=` returns findings, alerts and matching controls; the Ctrl+K
  palette in the layout merges those with a static page index. Saved filter presets were not
  built.

Both live endpoints use the tenant's Graph client with a 5-minute cache and fail with an actionable
message (missing permission vs unreachable tenant), not an empty page.

### Automatic and manual collection

`unimonitor.worker.tasks.assessment.collect_all_tenants` runs on the beat schedule at
`COLLECTION_INTERVAL_MINUTES` (default 15) and is gated by `AUTO_COLLECTION`. It creates a default
"Continuous monitoring" assessment for tenants that have none, so scheduling never silently does
nothing, and it replaces the previous assessment-only beat entry (which skipped those tenants and
would otherwise double-run). Manual paths are the **Data Collection** page (Collect now, per-collector
Run), `POST /monitoring/collect`, and the existing per-collector endpoint.

## 3.1 Still deferred after the second pass

| Gap | Why |
|---|---|
| GAP-12 | 364 PowerShell checks not ported; pillar model merged and the YAML catalogue remains the single source of truth |
| GAP-13 | Terminal UI conflicts with the multi-user web platform |
| GAP-14 | OSINT controls need an external feed contract that does not exist |
| GAP-17 | Per-staff tenant scoping needs a user↔tenant assignment model |
| GAP-18 | SQL Server is untested, so it is not claimed |
| Saved filter presets | UI sugar; global search covers lookup |

## 4. Implementation record

| Area | Files |
|---|---|
| Sign-in | `frontend/src/pages/LoginPage.tsx`, `frontend/src/main.tsx`, `unimonitor/api/v1/auth.py`, `unimonitor/onboarding/m365.py`, `unimonitor/config.py` |
| Reports | `unimonitor/reporting/html_generator.py`, `unimonitor/worker/tasks/reporting.py`, `unimonitor/api/v1/reports.py`, `frontend/src/pages/ReportsPage.tsx` |
| Zero Trust | `unimonitor/grc/pillars.py`, `unimonitor/api/v1/dashboard.py`, `frontend/src/pages/ZeroTrustPage.tsx`, `frontend/src/App.tsx`, `frontend/src/components/Layout.tsx` |
| Triage | `unimonitor/db/models/finding.py`, `alembic/versions/002_finding_triage.py`, `unimonitor/api/v1/findings.py`, `unimonitor/db/repositories/finding_repo.py`, `frontend/src/pages/FindingsPage.tsx`, `frontend/src/hooks/useApi.ts` |
| ROI | `unimonitor/grc/control_loader.py`, `unimonitor/api/v1/findings.py` |
| Alerts | `unimonitor/db/models/alert.py`, `unimonitor/alerts/engine.py`, `unimonitor/api/v1/alerts.py`, `unimonitor/worker/tasks/alerts.py`, `frontend/src/pages/AlertsPage.tsx` |
| Audit chain | `unimonitor/core/audit.py`, `unimonitor/db/models/audit_log.py`, `unimonitor/api/v1/dashboard.py`, `frontend/src/pages/AuditPage.tsx` |
| Collection | `unimonitor/worker/tasks/assessment.py`, `unimonitor/worker/celery_app.py`, `unimonitor/api/v1/monitoring.py`, `frontend/src/pages/CollectionPage.tsx` |
| Licence / health / search | `unimonitor/api/v1/monitoring.py`, `unimonitor/api/v1/search.py`, `frontend/src/pages/LicensesPage.tsx`, `frontend/src/pages/ServiceHealthPage.tsx`, `frontend/src/components/SearchPalette.tsx` |
| Migrations | `alembic/versions/003_alerts_and_audit_chain.py` |
| Tests | `tests/unit/test_merged_features.py`, `tests/unit/test_alerts_and_collection.py` |

## 5. Verification

Run on 2026-11-18:

| Check | Result |
|---|---|
| `pytest -q` | **639 passed** (20 new tests across the two merge passes) |
| `ruff check .` | clean |
| `ruff format --check .` | clean (176 files) |
| `mypy unimonitor` | clean (110 files) |
| `npm run build` (tsc + vite) | clean |
| `eslint --max-warnings 0` | clean |

Not verified, and therefore not claimed:

- No live Entra tenant was available, so Microsoft sign-in was fixed against the code paths and
  mocked Graph responses, not a real round-trip. The tenant must consent to the delegated scopes.
- No browser click-through of the new Zero Trust page, Findings triage or HTML report.
- No Windows installer rebuild; no Docker Compose run.
- Licensing, service health and the alert metrics were tested against mocked Graph/DB data, not a
  live tenant; `ServiceHealth.Read.All` must be consented for the health page to return data.
- The beat schedule was imported and the collection task's logic unit-tested; no Celery beat
  process was run here, so interval firing was not observed.
- The migration `002` was exercised by SQLAlchemy `create_all` in tests, not by `alembic upgrade`
  against a populated database.

## 6. Recommended next steps

1. Extend audit writes to assessments, logins and settings changes now that the chain exists.
2. Set `impact`/`effort` on the highest-risk controls so the ROI queue reflects real effort
   rather than the effort-3 default.
3. Import the Zero Trust checks that cover capabilities UniMonitor still lacks, as YAML controls
   rather than a second PowerShell library.
4. Live-tenant validation of the alert metrics (`security_score_drop` needs at least two runs in
   the window) and of the licence/service-health permissions.
