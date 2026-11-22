# Platform observations — 2026-11-22

Owner review of the running platform, top to bottom. Each observation has a stable
id (`OBS-nn`), the root cause where one was established from the code, the change
made in this session, and what is still open. Status values:

- **Fixed** — changed, covered by a test or a passing build, behaviour verified by the checks listed in `NEXT_ACTIONS.md`.
- **Partial** — the reported symptom is addressed but part of the request remains.
- **Open** — diagnosed or not, no code change yet.
- **Works as intended** — the behaviour observed is the correct behaviour.

Nothing here claims a live-tenant verification that did not happen. Graph and
Entra items stay open until they are exercised against a real tenant.

---

## Summary

| ID | Observation | Status |
|---|---|---|
| OBS-01 | Executive dashboard: choose which frameworks the coverage widget shows | **Fixed** |
| OBS-02 | CISO dashboard: show strongest frameworks too; make the state counts clickable | **Fixed** |
| OBS-03 | Cloud platform dashboard: framework coverage lists every framework | Open |
| OBS-04 | Cloud posture should update automatically instead of demanding a snapshot upload | Open |
| OBS-05 | Zero Trust: "Evaluated 450 checks — score 0%" while every test says "not run" | Open |
| OBS-06 | Risk page shows open risks for AWS when AWS is not connected | **Fixed** |
| OBS-07 | SOC severity links open an empty findings page | **Fixed** |
| OBS-08 | Audit page only shows UniMonitor's own audit trail | Open |
| OBS-09 | Direct navigation to Findings shows all identified data | **Works as intended** |
| OBS-10 | New assessment offers only a short framework list, not all 33 | **Fixed** |
| OBS-11 | Manual assessment of a framework fails | Open |
| OBS-12 | Auditor portal: other frameworks show no requirement table and Level 1 is the only level | Open |
| OBS-13 | Managed tenants: add, suspend, delete a tenant and its data | Open |
| OBS-14 | Licences page: `Organization.Read.All` 502 | Open |
| OBS-15 | Service health: `ServiceHealth.Read.All` 502 | Open |
| OBS-16 | User management: set a password, not only name and email | **Fixed** |
| OBS-17 | Settings: no way to configure SIEM/ticket connectors from the UI | Partial |
| OBS-18 | SMTP: no password field; offer the registered UniMonitor Entra app for mail | Partial |
| OBS-19 | Delegated tenant access: blank dropdowns | **Fixed** |

---

## Fixed in this session

### OBS-01 — Executive dashboard framework selection

`frontend/src/pages/ExecutiveDashboard.tsx` always charted `framework_coverage.slice(0, 8)`.
The widget now renders a toggle chip per framework; the selection filters the bars and
"Show all" clears it. An empty selection means every framework, so the widget opens
complete. Up to twelve bars are drawn at once to keep labels readable.

### OBS-02 — CISO strongest frameworks and clickable counts

- `GET /dashboard/ciso` now returns `strongest_frameworks` (top five by coverage,
  descending) alongside `weakest_frameworks`, from the same computed coverage map.
- `CisoDashboard` renders both lists through one `FrameworkCoverageList` component;
  each framework name links to its framework page.
- The control-state footer (Implemented / Partially implemented / Not implemented /
  Not applicable) is now a link per count to `/findings?state=…`, which the findings
  page honours through its `state` search param.

Covered by `tests/integration/test_ciso_dashboard.py::test_strongest_frameworks_sorted`
and `::test_strongest_frameworks_mirror_weakest`.

### OBS-06 — Risk page counted findings from unconnected clouds

`GET /dashboard/risk` selected every open finding regardless of whether its provider
was connected. The CISO board already filtered through `connected_providers`; the risk
view now does the same, and its heatmap is rebuilt from the surviving finding ids so
the cells and the list cannot disagree.

Covered by `test_dashboard_views.py::test_risk_view_hides_an_unconnected_provider`.

### OBS-07 — SOC severity links landed on an empty findings page

Severities are stored lowercase (`FindingSeverity.CRITICAL == "critical"`), but the SOC
tiles linked with `severity=CRITICAL` and the list endpoint compared the raw string to
the column, so every link returned zero rows. The findings list now normalises severity
to lowercase before querying, and the SIEM export's `severity` filter (which uppercased
and therefore matched nothing) is fixed with it.

Covered by `test_dashboard_views.py::test_findings_severity_filter_is_case_insensitive`.

### OBS-10 — New assessment offered ten hard-coded frameworks

`AssessmentsPage` carried a `FRAMEWORK_OPTIONS` constant. It now reads
`GET /grc/frameworks`, so every registered framework is selectable and labels come from
the registry. The default pre-selection was removed so an assessment never starts with
ids the registry does not know.

### OBS-16 — User management could not set a password

The create form only sent email, name and role, although `POST /users` already accepted
`password` (minimum 12 characters, bcrypt-hashed). The form now has an optional password
field, and the helper text explains that leaving it empty keeps the account
Microsoft-sign-in only.

### OBS-18 (first half) — SMTP password

The Settings page posted to `/settings/notifications`, which did not exist; the request
404'd and the panel silently kept its local state. A flat notification-preferences API
now lives in `unimonitor/api/v1/settings.py` and stores the document in
`Tenant.settings_json` (no migration needed):

- `GET /settings/notifications` returns the preferences with `smtp_password` masked.
- `PUT /settings/notifications` stores them; a password equal to the mask keeps the
  stored value, and a new value replaces it.
- The page gained the SMTP password field and now seeds its form from the server
  response instead of ignoring it.

Covered by `tests/integration/test_settings_notifications.py` (store + mask, mask
round-trip, replacement, auth, port validation).

The password is stored in the tenant settings document, masked at the API boundary.
It should move into the secrets vault with the connector credentials in OBS-17 rather
than stay in a settings row; that is a migration, not a UI change.

### OBS-19 — Delegated tenant access dropdowns were empty

`DelegatedAccessPanel` requested `/tenants?page_size=200` (the endpoint caps at 100, so
the request was rejected with 422) and read `/users` as `{items: […]}` although it returns
a plain array. Both are normalised now, so the tenant and user lists populate.

---

## Open

### OBS-03 — Cloud platform dashboard shows every framework

`GET /dashboard/cloud/{provider}` (see `unimonitor/api/v1/dashboard.py`) reuses the
tenant-wide framework coverage, so a single cloud's page lists frameworks that cloud
contributes no controls to. The fix is to intersect coverage with the provider's control
set (`unimonitor/grc/providers.py` already maps services to providers). Needs a
per-provider coverage test.

### OBS-04 — Automatic posture

`GET /posture/analysis` analyses the file named by `UNIMONITOR_POSTURE_SNAPSHOT`, and
nothing writes that file from collected data. To make posture automatic the cloud
collectors' normalised output (already produced for AWS, GCP and Google Workspace
snapshots) has to be assembled into the inventory shape the posture engines read, then
handed to `unimonitor.posture.analysis.analyse` on each collection run — with the file
path kept as a manual override. This is a collector-to-engine bridge, not a UI change.

### OBS-05 — Zero Trust score says 0% while tests say "not run"

The run summary and the per-test table disagree. `zerotrust` scores are computed from
recorded checks; a run that records a total with no evaluated statuses will show 0%
while the table reports `not_run`. The investigation needs the specific platform run —
reproduce with a Microsoft 365 assessment, then confirm whether checks are persisted
without a status or read back from a different run id.

### OBS-08 — Audit page is UniMonitor-only

`GET /dashboard/audit` reads `audit_logs`, the platform's own hash-chained trail. It
cannot show Microsoft 365 / AWS / GCP / Workspace audit records because those are not
collected. Either ingest the providers' audit streams (new collectors plus a separate
table — the platform audit chain must stay immutable and separate) or relabel the page
to "Platform audit trail" and add per-provider collection status. Decide before building.

### OBS-09 — Direct findings navigation

This is correct behaviour and the control case for OBS-07: the page loads every finding
when no filter is present. No change.

### OBS-11 — Manual assessment fails

Needs the failing run's `error_message` from `assessment_runs`. The dispatch path commits
the run row before queueing and falls back to the in-process worker, so the failure is in
the engine or a collector rather than the queue. Reproduce with one framework and read
the run row before changing code.

### OBS-12 — Auditor portal requirement tables and levels

The portal only requests a requirement catalogue for CPCSC; every other framework gets
the "control-level evidence only" note, and the only level filter is "Level 1 only".

Plan: generalise the requirement catalogue. Frameworks with a native requirement set
(CPCSC, FedRAMP, NIST 800-171, CMMC) keep their requirement ids; the rest derive a
family/level row from the control metadata (`family`, `level` where present, else the
control's first mapped requirement). The level selector becomes the set of levels the
selected framework actually declares (1–3 for CPCSC, 1–2 for CMMC, "all" otherwise).
Evidence controls stay the mapped control list per row. This is an API change plus a
page change and needs a catalogue test per mapping family.

### OBS-13 — Managed tenant lifecycle

`POST /tenants`, `PUT /tenants/{id}` (with `is_active`) and `DELETE /tenants/{id}` already
exist and are admin-guarded; `MspPage` is read-only. The UI work is an add/suspend/delete
control set with the existing confirmation semantics, plus showing each tenant's
connection state. Deletion removes tenant-scoped rows by cascade — the dialog must say so.

### OBS-14 / OBS-15 — Licence posture and service health 502

Both pages surface the Graph request failure verbatim. `502` comes from the upstream
Graph call, not from UniMonitor's own gateway, and the pages already name the missing
permission. Remaining work: distinguish "permission not consented" from "Graph
unavailable" in the response, and add an admin action that re-checks consent. Cannot be
verified without the tenant.

### OBS-17 — SIEM and ticketing connectors in Settings

A panel exists that lists each connector, shows whether its deployment secrets are
present, and can test or send. What is missing is entering credentials in the product,
because connector secrets are read from the environment and never stored in the
database. The intended change is a secrets-backed form (vault entries per connector)
instead of plaintext settings.

### OBS-18 (second half) — Send mail with the registered Entra app

Today mail goes through SMTP only. Using the UniMonitor app registration requires
`Mail.Send` application permission with admin consent and a `sendMail` call in the
notification dispatcher, with SMTP kept as the fallback. Pending a tenant to consent and
test.
