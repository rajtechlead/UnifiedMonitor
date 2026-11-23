# Owner observations — 2026-11-23

Working tracker for the twelve observations raised against the installed build.
Each item records the root cause found in this repository (or in the reference
projects `sameerk27/vigil365` and `microsoft/zerotrustassessment`), the change
made, and the verification that was actually possible without a live tenant.

Status keys: ✅ implemented and covered by a test · 🟡 implemented, needs a live
tenant/PowerShell host to verify end to end · ⬜ not started.

## Reference material

- `sameerk27/vigil365` — sign-in, Graph service-health/licence endpoints and the
  `graph-permissions.json` list.
- `microsoft/zerotrustassessment` — the PowerShell Zero Trust assessment module
  and its HTML report output.

## 1. "Microsoft sign-in is not configured" 🟡

**Root cause.** The setup wizard stores the Entra app in `cloud_connections` and
the vault, not in `.env`. `/auth/sso` correctly reports the button as enabled
from the database, but `/auth/login` built its MSAL app from
`settings.ENTRA_CLIENT_ID`, which is only hydrated at startup. On a fresh
install the button therefore redirected with `error=sso_unavailable`.

**Change.** Sign-in resolves the app id, directory and credential from the saved
Microsoft connection (certificate or secret) through one helper shared with the
Graph client; `connect_microsoft` hydrates the settings singleton immediately.
The local administrator stays as the break-glass account and the setup step is
untouched.

**Verification.** `tests/integration/test_microsoft_app_credentials.py` (6 tests)
covers DB-only app resolution, certificate preference and the login redirect.

## 2. Service health unavailable (502) 🟡

**Root cause.** Two problems in one path: the Graph request was built from the
startup settings (empty on a DB-configured app), and every failure — expired
credential, missing permission, Graph 5xx — collapsed into a 502. The app's real
error body was discarded, so "permission granted" could not be distinguished
from "wrong app".

**Change.** `/monitoring/service-health` now resolves the app through the same
`microsoft_app` helper as sign-in, encodes the `$filter`, and maps errors:
not connected → 503, missing permission/consent → 403 with the permission name,
credential/Graph failure → 502 with the Graph error code and message. The page
renders that `errorDetail`.

## 3. Licence posture unavailable (502) 🟡

**Root cause.** Same credential source bug as item 2; `subscribedSkus` was also
requested without pagination handling and all failures became 502.

**Change.** Licensing uses the shared resolver and error mapping, and reports the
`Organization.Read.All` requirement explicitly. Frontend surfaces the detail
instead of a generic banner.

## 4. Plug-n-play onboarding for every platform under Managed tenants ✅

**Root cause.** "Add client" only collected Microsoft fields (`entra_tenant_id`,
client id, secret). AWS/GCP/Workspace credentials could only be entered on the
platform-connections page.

**Change.** Client creation now needs only a name (the identifier is generated)
and optional Microsoft fields; every platform is connected on the client's own
page through `PlatformConnector` and
`POST /tenants/{id}/connections/{platform}`. The Microsoft secret is written to
the vault, with only `client_secret_ref` in the database.

**Verification.** `tests/integration/test_onboarding_api.py` (existing) plus the
tenant-connection tests; `tsc`/`eslint` for the new page.

## 5. Per-tenant settings for the primary administrator ✅

**Change.** `GET/PUT /tenants/{id}/settings` stores branding, notification
defaults and report preferences in the tenant's `settings_json`; `GET/POST/DELETE
/tenants/{id}/connections` manages each platform's connection. The MSP page links
to a new `TenantSettingsPage` (route `tenants/:tenantId`) that shows health,
connected platforms, per-platform connect forms and the settings document. Access
is limited to administrators and holders of a `tenant_access` grant.

## 6. Plug-n-play platform connections in Settings ✅

**Change.** `PlatformConnector` is reusable per tenant and gained an Okta
provider (hostname + SSWS token, validated in `onboarding/clouds.py`,
`grc/providers.py`). Connect flows are the platform's own admin-consent/OAuth or
credential entry, then a verification probe. The per-tenant page lists every
platform the deployment supports and marks the connected ones.

**Honest limit.** The live OAuth round-trip needs a real tenant; the validation,
secret storage and verification code paths are covered by fakes.

## 7. Plug-n-play SIEM and ticketing connectors ✅

**Root cause.** `unimonitor/integrations/siem.py` and `ticketing.py` read only
deployment environment variables, so Settings could show a connector as
"needs SPLUNK_HEC_TOKEN" with no way to supply it.

**Change.** New `unimonitor/integrations/credentials.py` stores each connector's
settings as one JSON document in the secret vault
(`unimonitor-connector-<kind>-<provider>`). `PUT /integrations/{kind}/{provider}/config`
and `DELETE` connect/disconnect from the UI; values are validated (known fields
only, length caps, http(s) for URL/endpoint fields, bare hostname for host
fields), merged on rotation, never returned, and the environment stays the
fallback. Settings renders a Connect/Update form per connector with password
inputs for token-like fields.

**Verification.** `tests/unit/test_connector_credentials.py` (8 tests): round
trip, merge, unknown field/provider rejection, scheme validation, blank values,
delete restores fallback, managed flag in both status lists.

## 8. AI provider connection and auto-switchover sequence ✅

**Change.** New `unimonitor/ai/builtin.py` catalogue with vault-stored keys
(`/ai/settings`, `/ai/providers/{name}/test`, `builtin` block in `/ai/status`).
The failover order is persisted per tenant in `settings_json["ai_builtin"]`;
`grc/ai_remediation.py` builds the chain custom providers → tenant built-ins →
environment built-ins, de-duplicated. Keys are masked on read and only ever
written to the vault; `BuiltinAiProviders` in Settings edits providers and the
switchover order.

## 9. Zero Trust assessment execution and HTML report 🟡

**Root cause.** The page rendered the 364-test catalogue from the YAML controls
but nothing ever executed them: there was no runner, no task and no report
writer. The upstream project runs a PowerShell module that writes an interactive
HTML file.

**Change.** `zerotrust/runner.py` runs the Microsoft assessment (Python engine by
default; the PowerShell module on Windows with app-only auth via the registered
Entra app, secret passed in `ZT_CLIENT_SECRET`, never argv) and falls back to
Python. `zerotrust/reports.py` writes a self-contained interactive HTML report
(no CDN) to the `ZT assessments` folder in the install directory
(`UNIMONITOR_ZT_DIR` override; writable fallback for Program Files). `POST
/zerotrust/assess` dispatches `worker.tasks.zerotrust.run_zt_assessment_task`,
`GET /zerotrust/reports` lists saved reports and `/zerotrust/reports/{name}`
serves one. The page has a run button, PowerShell checkbox and report list. The
same run/report path covers AWS, GCP and Google Workspace assessments.

**Honest limit.** The upstream module's `Connect-ZtAssessment -UseAppAuth`
parameter set could not be verified here (no Windows host, no PowerShell); the
wrapper is deliberately best-effort with the Python fallback. `ZT assessments`
is created by the NSIS installer and set in the service environment.

## 10. Audit page groups platform logs and keeps UniMonitor's own ✅

**Change.** `core/cloud_audit.py` now takes `(db, tenant_id, limit, failures)`,
resolves the Microsoft app from the database, filters by tenant, reads five
Workspace applications, and collects per-source failures instead of raising.
`/dashboard/audit` accepts `tenant_id` and returns `cloud_failures`; the Audit
page groups rows by platform, shows failures per source, and keeps the
UniMonitor audit log as its own group.

## 11. Reports run drop-down empty after a successful run ✅

**Root cause.** `/reports/runs` joined `Assessment` on a column that does not
exist (`AssessmentRun.tenant_id`) and filtered on `created_at`, which the model
does not have, so every query failed and the picker showed only "Select a run".
`generate_report` also returned success without persisting a `Report` row.

**Change.** The join uses `Assessment` for the tenant and `run.started_at` for
ordering; `Report` rows are created by `run_report_now` with `file_paths` JSON and
`requested_by`, and `ReportStatusResponse` exposes `id`, `formats`, `file_paths`,
`requested_by` and `run_id`.

**Verification.** `tests/integration/test_reports_api.py` includes the picker
regression with committed rows and the inline/dispatch failure paths.

## 12. Framework control/level coverage research ✅

**Change.** New `unimonitor/grc/framework_reference.py` records, for every one
of the 34 supported frameworks, the publisher, version, published control and
requirement totals, the levels with descriptions, how levels relate
(cumulative, separate baselines, maturity tiers, applicability classes, report
type), the source URL and notes; `modelled` marks a count this platform derived
rather than a published total.

`grc/requirements.py` now derives every framework's levels from that catalogue
(IG1–IG3, ML1–ML3, AL1–AL3, FedRAMP baselines, CMMC, …) and repeats cumulative
requirements at each level with unique ids so a level filter is complete; separate
baselines and applicability classes are not duplicated. The requirements
catalogue endpoint returns a `reference` block and the auditor portal shows the
publisher/version/control-count/level-count line above the table.

**Sources checked** (2026-11-23): CIS Controls v8.1 — 18 controls, 153 safeguards,
IG1 56 / IG2 130 / IG3 153 (cisecurity.org); NIST CSF 2.0 — 6 functions, 22
categories, 106 subcategories (nist.gov); ISO/IEC 27001:2022 — 93 controls
(37/8/14/34); SWIFT CSCF v2026 — 32 controls, 26 mandatory + 6 advisory, 3
objectives, 7 principles. Other counts are from the publishers' own pages,
linked in each reference entry.

**Verification.** `tests/unit/test_framework_reference.py` (12 tests): every
registered framework has a reference, sane counts/levels, published level names,
cumulative expansion with unique ids, separate baselines not duplicated, the
catalogue's reference block, conservative fallback for an unknown id.
