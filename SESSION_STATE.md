# SESSION_STATE.md

Project: UnifiedMonitor
Repository: https://github.com/rajtechlead/UnifiedMonitor
Last Updated: 2026-11-19 UTC

## Current Session Commits (2026-11-18)

- `fix(onboarding): sign in with a client Entra preauthorizes for app registration`

### Session 2026-11-18 — sign-in fix, Settings parity, SonarQube blockers

A real tenant answered `AADSTS65002` at the device-code sign-in: Azure CLI's client is only
preauthorized for its own cmdlet surface, so the wizard could not request
`Application.ReadWrite.All`.

- `m365.PUBLIC_CLIENT_ID` is now Microsoft Graph PowerShell (`14d82eec-…`), which Entra
  preauthorizes for app-registration work. `ENTRA_SIGNIN_CLIENT_ID` lets a locked-down tenant
  point the wizard at its own app; `_friendly()` appends that instruction whenever Entra answers
  `AADSTS65002`/`65001`/`700016`.
- `client_credentials_token()` is the one token-minting path shared by verification and rotation.
- Settings → Platform connections now offers the **Google Cloud + Workspace — one service
  account** connector (`POST /connections/google-service-account`), so the option is no longer
  wizard-only.
- Certificate lifecycle in Settings: `connect_microsoft` records `certificate_expires_at`;
  the row shows thumbprint + expiry and warns within 30 days; **Rotate certificate** calls
  `POST /microsoft/certificate/rotate` → `service.rotate_microsoft_certificate()` (app-only token
  → `addKey` → verify → `removeKey` of the previous key → new vault entries → settings hydrated).
  `m365.find_app_object_id()` fills in the object id for connections made by hand.
- SonarQube blockers fixed: notification tasks were calling the dispatcher with `settings=`/
  `findings=` names that do not exist (`settings_obj=`), so no digest or alert was ever sent;
  `cli smoke-test` passed `base_url` to a function that took no arguments; CORS middleware is
  added last so it wraps error responses; `scripts/smoke_test.py` gained a `base_url` argument and
  a real exit status; the Fernet key is a domain-separated SHA-256 of the install secret instead
  of PBKDF2 over a literal salt; the e2e control test no longer asserts inside its own
  `except`; Kubernetes manifests disable the unused service-account token mount and set
  ephemeral-storage requests/limits; suppression comments no longer carry prose after the rule id.

## Previous Commits (2026-11-17)

- `feat: certificate credentials for the Entra app and shared cloud service accounts`
- `feat: first-run setup wizard that asks which platforms to monitor`
- `fix(ci): put makensis on PATH after installing NSIS`

### Session 2026-11-17 — certificate credentials and one service account

Microsoft 365 onboarding now defaults to certificate authentication and the cloud connectors
accept a single shared identity:

- `unimonitor/onboarding/certificates.py` — generates a self-signed RSA certificate with a
  caller-chosen validity (365 days default, 1–1095), returns PEM/DER, computes the Entra
  thumbprint and signs the `client_assertion` JWT used for client-credentials auth.
- `m365.provision_app(auth_method=...)` — certificate is the default: the public certificate is
  uploaded with `/applications/{id}/addKey`. `add_certificate()` is a separate step so a refused
  upload is reported, not fatal: the result carries the certificate, the portal steps and
  `certificate_uploaded=False`. `verify_client_credentials()` accepts a certificate or a secret.
- Fallback flow: the connection is stored as `pending_certificate_upload`, which does **not**
  count as configured, so the wizard cannot finish. The UI offers the certificate files for
  download, the Entra portal steps and **Check certificate connectivity**
  (`POST /microsoft/verify`), which re-tests and promotes the connection.
- Runtime: `ENTRA_CLIENT_CERTIFICATE` + `ENTRA_CLIENT_PRIVATE_KEY` are hydrated from the vault and
  MSAL authenticates with them; the secret is cleared in certificate mode.
- AWS can connect as an assumed IAM role (`validate_aws_role`, `assume_role_credentials`); no
  long-lived keys are stored and the collector assumes the role at collection time.
- Google Cloud and Google Workspace can share one service account:
  `POST /connections/google-service-account` validates both and stores one key for both.
- UI: `PlatformConnector` gained an auth-method picker, a certificate validity field, the
  fallback panel and a `GoogleSharedConnector` the wizard shows when both Google platforms are
  selected.
- Docs: INSTALL.md §6 (certificate default, fallback, SSO/shared service account), README quick
  start, `docs/SECRET_MANAGEMENT.md` (vault entries and rotation).

### Session 2026-11-17 — first-run onboarding

The Windows installer finished without asking anything: it wrote a `.env` with an empty
`UNIMONITOR_SECRET_KEY`, an unusable `SECRETS_PROVIDER=local`, and then opened a dashboard with
no data. Setup is now a wizard the installer launches:

- `GET/POST /api/v1/onboarding/*` — status, first admin, platform connection, list, delete. The
  unauthenticated window closes when the first administrator is created; afterwards an admin
  token is required for every change.
- `SetupPage` + `PlatformConnector` (React) — administrator, platform multi-select (at least one
  of Microsoft 365 / AWS / GCP / Google Workspace), then a per-platform connection step. The same
  connector is embedded in Settings → Platform connections so platforms can be added later.
- Microsoft 365 is automated: device-code sign-in as a Global Administrator, then Graph creates
  the app registration with the read-only app roles in `unimonitor/onboarding/permissions.py`,
  grants admin consent per role and mints a client secret. Manual credentials remain available
  when tenant policy blocks the automated path, and are validated before saving.
- AWS / GCP / Workspace credentials are validated against the live API at connect time; secrets go
  to the configured secret provider and the database keeps only references
  (`cloud_connections`). GCP and Workspace tokens are now minted from the stored service-account
  key instead of a static `*_ACCESS_TOKEN`.
- `UNIMONITOR_SECRET_KEY` is generated once and persisted in `UNIMONITOR_DATA_DIR/secret.key`, so a
  fresh install starts without a manual key step.
- `scripts/setup_wizard.py` and `scripts/setup.py` deleted: they duplicated this flow and were not
  bundled into the frozen executable.
- Windows workflows install `.[production]` so boto3 is present in the frozen bundle.

Prior session commits:

- `fix: align dashboard views with API contracts and add Risk, SOC, Audit views`
- `fix: resolve ruff/mypy failures introduced since 1de7bcd`
- `docs: sync trackers with actual repository state`

Prior session commit chain (2026-11-13 → 2026-11-15):

```
1eab565 feat: implement 7 stub collectors + tests for entra_id/intune/collectors
a2b8ebb tests: add api/v1/auth (15 tests) and graph/client (23 tests)
0349823 tests: add auth/jwt, auth/oauth, cli unit tests (36 tests)
5cff5bb tests: add ai_remediation (24) and collector_registry (22) unit tests
18f046c tests: add control_loader (43) and secrets resolver (27) unit tests
3da05d8 tests: add 26 tests for core/logging.py and core/cache.py
79dfb98 test: add crosswalk and scoring tests — coverage 60% → 62%
c83da97 test: add GRC engine tests — coverage 58% → 60%
0315f83 test: add secrets backend and notification dispatcher tests — coverage 53% → 58%
deaa82f test: add core security and worker task unit tests — coverage 47% → 53%
417ad87 feat: upgrade 4 frontend major versions — lucide-react, typescript-eslint, zustand, recharts
8eaf719 chore: add coverage artifacts to .gitignore
1de7bcd chore: bump GitHub Actions to latest versions + eslint-plugin-react-refresh patch
edbe3f3 docs: add Phase 6 production guides and fix PyInstaller spec
11f5309 fix: resolve remaining CI failures — ruff F401 and Playwright strict mode
49e5f14 fix: resolve all CI failures — Docker, ruff, mypy, ESLint, Playwright
0b98fc3 fix: ruff lint auto-fixes, starlette deprecation, and code quality
afe46fc chore: initial recovery from legacy ZIP with critical fixes
```

## Current Phase

Status: 🟢 Green locally — Release Candidate blocked only on Windows validation and tag push
Phase: 6 — Production Release, plus Phase 7 (requirement completion) opened

The four trackers were stale as of 2026-11-13: they described HEAD `1de7bcd` and 105 tests.
The repository was actually 10 commits further ahead with 462 tests and the majority of the
frontend dependency migrations already merged. Trackers have now been reconciled.

## Completed This Session (2026-11-16)

- Reconciled trackers against HEAD `1eab565` (doc drift: +10 commits, 105 → 462 tests).
- Verified baseline: all 467 tests pass; ruff, ruff format, mypy, ESLint, tsc, vite build all clean.
- Fixed two dashboard pages that were rendering nothing real:
  - `ExecutiveDashboard` read `scores.security` / `severity_counts` / `trend` which the API never
    returned, so it silently displayed hard-coded demo values. Now reads `scores.security_score`,
    `score_trends`, `framework_coverage`, `top_risks`, asset/remediation percentages.
  - `ComplianceDashboard` expected `{framework, score, implemented…}` while the API returns
    `{framework_id, framework_name, coverage_pct, controls_total, controls_passed}`. Aligned.
  - Both pages dropped their fake demo fallbacks — an empty assessment now shows an empty state.
- Added the three missing required dashboard views (requirement: Executive, Security, SOC,
  Compliance, Risk, Audit):
  - `RiskDashboard` — 5×5 likelihood/impact heatmap + critical risk list.
  - `SocDashboard` — alert KPIs, severity breakdown, incident trend.
  - `AuditPage` — audit trail table.
  - New `GET /api/v1/dashboard/audit` endpoint (audit trail was previously DB-only, no API).
  - Routes + sidebar navigation for Risk, SOC, Audit.
- Added `tests/integration/test_dashboard_views.py` (5 tests).
- Expanded the control library from 100 to 158 controls, closing the named monitoring gaps:
  Intune security baselines (+8), application inventory (+6), Defender for Office (+8),
  Defender for Identity (+7), Defender for Cloud Apps (+7), Insider Risk (+8), eDiscovery (+6),
  Copilot Studio (+8). Added `tests/unit/test_control_library.py` guarding unique ids, valid
  severities, registered framework keys, required-area coverage and evaluator safety.
- Fixed 12 pre-existing controls that mapped to the unregistered key `nist_csf` instead of
  `nist_csf_2`, so their NIST CSF mapping never resolved.
- Made the 58 new controls actually evaluate: `graph/collectors/extended.py` normalises Graph
  payloads into the keys they read (Intune baselines/app inventory, Defender for Office/Identity/
  Cloud Apps from Secure Score, eDiscovery cases and role groups, OAuth consent grants), and
  `graph/collectors/snapshot.py` merges a posture snapshot (`UNIMONITOR_POSTURE_SNAPSHOT`) for areas
  with no Graph endpoint. 19 tests drive sample payloads through collector → control.
- Closed L-009: CTRL-PUR-006 is now a distinct departing-employee scenario control.
- Added multi-cloud support (Phase 8): AWS (boto3), Google Cloud and Google Workspace (REST with an
  access token) collectors, with 8 AWS / 8 GCP / 6 Workspace controls and 12 payload-driven tests.
  Provider collectors return {} without credentials, so controls report `not_implemented`.
- Scope is multi-cloud, not Microsoft-only: `grc/providers.py` is the provider registry
  (Microsoft 365, AWS, GCP, Workspace) that maps control/finding `service` values to a cloud,
  so provider roll-ups are a grouping operation rather than a parallel code path.
- New dashboards: `GET /dashboard/clouds` (aggregate across providers) and
  `GET /dashboard/clouds/{provider}` (scores, control states, category/framework coverage,
  top findings), plus React pages `/clouds` and `/clouds/:providerId` and a Clouds nav entry.
- Fixed a latent bug: `compute_framework_coverage` was imported by the dashboard and GRC APIs but
  never existed, so framework coverage silently returned empty. It now exists, and it normalises the
  hyphenated API framework ids (`iso27001-2022`) against the underscored control-mapping keys.
- Compliance reports break down by cloud: the aggregate single-org summary is unchanged and comes
  first, then a colour-coded “Cloud Provider Coverage” table and one section per provider (own score,
  control states, findings) follow. PDF and DOCX emit these sections for **every** report type
  (full, executive, compliance, board, audit, operational); DOCX did not exist before (README claimed
  it), so `reporting/docx_generator.py` was added with `python-docx`.
- CISO dashboard (`GET /dashboard/ciso`, `/ciso`): residual risk across every cloud, exposure table
  per provider, top risks with provider labels, weakest frameworks (real framework display names, not
  title-cased ids) and a 30-day posture trend.
- Dependency audit repaired: the CI "Python Security Audit" job failed on python-jose 3.5.0
  (PYSEC-2026-4298) and its `ecdsa` dependency (PYSEC-2026-1325), neither with an upstream fix.
  JWT handling moved to PyJWT (already present via msal), python-jose removed from `pyproject.toml`,
  and a clean `pip install -e .` now audits with no known vulnerabilities.
- Added `.github/workflows/windows-installer.yml`: a dispatch-only workflow that builds the NSIS
  `.exe` plus a portable zip on `windows-latest`, independent of the release pipeline.
- First real Windows runner run (dispatch on `961ccb0`): pip install, frontend build, PyInstaller
  freeze (1134 files) and the `UniMonitor.exe --help` smoke test all passed. The build then failed
  at `makensis /VERSION` with "The term 'makensis' is not recognized": `choco install nsis` updates
  the *machine* PATH, which the already-running PowerShell process never re-reads. Both installer
  workflows now resolve `makensis.exe` explicitly (`C:\Program Files (x86)\NSIS`) and append its
  folder to `$env:GITHUB_PATH` before use, failing loudly if it is absent;
  `tests/unit/test_windows_build_assets.py` guards the export.
- Both Docker images now copy `unimonitor/` before `pip install`: without the package hatchling
  still exits 0 and writes an empty 5 KB wheel, so the old ordering only worked because the source
  was copied in afterwards. `tests/unit/test_windows_build_assets.py` asserts the ordering.
- New CI job `Bundled UI Serves` builds the frontend, stages it in `unimonitor/static`, then runs
  `scripts/verify_bundled_ui.py`, which starts the real server and asserts the shell, hashed assets,
  a deep link, the JSON health route, a 401 on a collection route and a 404 for unknown API paths.
- The SPA fallback had to move out of routing: an `APIRoute` matching `/{path}` competes with
  FastAPI's lazily included sub-routers and shadowed routes declared with an empty path
  (`GET /api/v1/tenants`, `/findings`, `/reports`, `/assessments`, `/controls`). It is now ASGI
  middleware (`SpaFallbackMiddleware`) that only rewrites 404s for navigation requests, so API
  routes and trailing-slash redirects are untouched — covered by a parametrised regression test.
- Verified the packaged UI end to end after the audit/workflow commit: nothing served the built SPA, so
  `/` was a 404 in the Docker image and in the Windows installer. `create_app()` now mounts
  `unimonitor/static` at `/` with an index fallback for client-side routes (API routes still win),
  `UNIMONITOR_STATIC_DIR` overrides the location for tests, and the Docker image copies `dist` to the
  path the app actually reads. Checked against a real `npm run build`: `/`, `/clouds`, hashed assets
  and `/api/v1/health` all behave.
- Code review (2026-11-17) found three integration defects beyond the audit failure, all fixed with
  tests: `unimonitor/worker/tasks/__init__.py` exported nothing, so every API report request hit the
  “Celery unavailable” branch and the task never ran; `POST /reports/generate` required
  `tenant_id`/`report_type`/`report_format` while the UI sends `run_id`/`formats` (422 on every
  click), and it passed kwargs the worker task does not accept; the CISO severity tiles counted
  implemented findings as open risk. Also cached the per-provider control library lookup, which was
  re-reading all control YAML four times per dashboard request.
- Windows packaging repaired: `pyinstaller==6.10.0` pinned in README never existed for modern
  Pythons (now `>=6.16,<7`), the spec listed a removed `unimonitor.secrets.factory` hidden import and
  shipped without python-docx data, the PyInstaller hook crashed on production settings validation,
  NSIS aborted on the missing `branding/icon.ico`, and it relied on the EnVar plugin that stock NSIS
  does not ship. Icon is now committed (regenerable via `scripts/make_icon.py`) and the release
  workflow builds on demand (`workflow_dispatch`), smoke-tests the packaged exe and fails if the
  installer is missing. `tests/unit/test_windows_build_assets.py` guards each regression.
- Fixed 157 ruff + 2 mypy errors that existed on HEAD (CI would have been red): import sorting,
  line length, unused imports/variables, `print` in CLI scripts, dummy-credential false positives.

## Completed Previously (Phases 1–5, unchanged)

- Phase 1 Repository Recovery ✅ (PROJECT_AUDIT.md still deferred, L-001)
- Phase 2 Stabilisation ✅ — all Critical/High resolved (see GAP_REGISTER.md)
- Phase 3 Architecture ✅ — unified secrets framework done; setup wizard script exists
  (`scripts/setup_wizard.py`, wired into `unimonitor/cli.py setup`)
- Phase 4 Build Validation ✅ — tests, lint, mypy, ESLint, Playwright, Docker (CI)
- Phase 5 Packaging 🟡 — Docker ✅ CI, PyInstaller ✅ Windows runner, NSIS 🟡 PATH fix awaiting a green run
- Phase 6 Release 🟡 — all four production guides written; release tag not pushed

## In Progress

None.

## Blocking Issues

1. **NSIS / Windows validation** — the PyInstaller half now runs on a real `windows-latest` runner,
   but a fully green installer build and a fresh install/upgrade are still unproven; neither this
   Linux workspace nor scripting can substitute for a Windows host. Covers P5-003…P5-006.
2. **Docker Compose local validation** — no Docker daemon in this workspace. CI builds the image,
   but `docker compose up` end-to-end has never been run.
3. **Release tag** — no tags exist in any clone. `v1.0.0-rc1` must be recreated and pushed by a
   session/identity with tag-push permission (previous sessions got HTTP 403).

## Known Remaining Work

1. Windows installer build, fresh install, upgrade and rollback validation.
2. Docker Compose end-to-end validation.
3. Remaining frontend majors: `react` 18 → 19, `@vitejs/plugin-react` 4 → 6.
4. ~~Control library depth~~ — closed 2026-11-16 (100 → 158 controls); the remaining need is
   collector data coverage for the new controls, not definitions. PIM depth stays thin (4 controls).
5. ~~`ecdsa` / `python-jose` CVEs~~ — closed 2026-11-17: migrated to PyJWT, both packages removed; `pip-audit` clean.
6. `PROJECT_AUDIT.md` (L-001, deferred by owner decision).
7. Test coverage re-measurement (last measurement 62% at `79dfb98`).

## Tooling

`graphify` 0.9.111 is installed and the code knowledge graph is committed under `graphify-out/`
(2938 nodes, 6129 edges, 177 communities, AST-only, markdown excluded via `.graphifyignore`).
Query it with `graphify explain "X"`, `graphify path "A" "B"` or `graphify query` before grepping.
The graph is refreshed by `graphify update .`; `.gitattributes` union-merges `graph.json`.
The pre-commit refresh hook is deliberately *not* installed in this workspace: `.git` is a linked
worktree sharing `/workspace/repo.git`, and modifying shared Git hooks would affect other
worktrees. Install the hook per clone (see the setup-graphify skill) when the repo is checked out
as a normal main tree.

## Active Technology Baseline

Python 3.12.x (enforced), FastAPI + SQLAlchemy + Alembic + Pydantic, PostgreSQL primary /
SQLite fallback, Redis + Celery, Microsoft Graph + Entra ID OAuth2, bcrypt (passlib removed),
Azure Key Vault / AWS Secrets Manager / local encrypted store, Docker Compose (secondary),
PyInstaller + NSIS (primary Windows), Vite 5 + React 18 + TypeScript + ESLint, OpenTelemetry +
structured logging, GitHub Actions.

No architecture drift detected this session. Pending majors (`react` 19, `plugin-react` 6) are
same-vendor upgrades within the approved stack, not substitutions.

## Current Build Status (measured 2026-11-16, local venv + node_modules)

| Component | Status | Notes |
|---|---|---|
| Python tests | ✅ 536/536 | 60s, 7 warnings (AsyncMock never-awaited in mocks) |
| Control library | ✅ 180 controls | 21 YAML files, all framework keys resolve |
| Multi-cloud collectors | ✅ AWS / GCP / Workspace | credential-dependent; payload tests only |
| Multi-cloud dashboards | ✅ aggregate + per provider | provider registry drives both; React build clean |
| CISO dashboard | ✅ API + UI | cross-cloud risk, weakest frameworks, 30-day trend |
| Windows packaging | ✅ static + CI guarded | local NSIS/PyInstaller run still needs a Windows host |
| Ruff check | ✅ CLEAN | 0 errors (was 157 on HEAD) |
| Ruff format | ✅ CLEAN | 132 files formatted |
| mypy | ✅ CLEAN | 87 source files |
| ESLint | ✅ CLEAN | 0 warnings, `--max-warnings 0` |
| tsc + vite build | ✅ PASSING | 2613 modules, 5.0s, charts chunk 437 kB |
| Coverage | 🟡 62% | last measured at `79dfb98`; not re-measured this session |
| Playwright E2E | ⬜ NOT RUN | browsers not installed in this workspace; CI job exists |
| Docker build | ⬜ NOT RUN | no daemon here; CI job green at `1de7bcd` |
| PyInstaller | ⬜ NOT RUN | last Linux success 2026-11-13 |
| Windows installer | ⬜ UNKNOWN | Windows environment required |

## 2026-11-18 — Reference-repository merge

- Analysed `mstanton/m365_sheppard`, `sameerk27/vigil365` and `microsoft/zerotrustassessment`
  against this codebase; wrote `Comparison.MD` and `gap_analysis.md` (GAP-01…GAP-20).
- Fixed the login page's Microsoft sign-in (wrong route, unread token fragment, no redirect URI),
  and the worker that awaited a synchronous report generator.
- Merged: HTML report, Zero Trust pillar view, ROI priority queue, finding triage
  (ack/snooze/assign/resolve), per-finding timeline. Migration `002` adds the triage columns.
- Deferred with reasons: alert-policy engine, licence posture, service health, global search,
  hash-chained audit, 364 PowerShell checks. See `gap_analysis.md` §3.
- Also repaired the rest of the report pipeline: per-format download, status and delete (a
  non-existent `ReportRepository` import made them fall through) — 630 tests.
- Checks: 630 tests, ruff, ruff format, mypy 103 files, `tsc && vite build`, ESLint all clean.

## 2026-11-18 — Deferred gaps closed

- Alert Center: `AlertPolicy`/`Alert`, six metrics, five templates, beat evaluation, ack/snooze/
  resolve, notification dispatch, policy CRUD.
- Licence posture and service health pages backed by live Graph (`/monitoring/licensing`,
  `/monitoring/service-health`); `ServiceHealth.Read.All` added to optional permissions.
- Ctrl+K global search across pages, findings, alerts and controls.
- Audit trail is now SHA-256 hash-chained with a verified badge; triage, alerts, policies and
  manual collection write to it.
- Automatic collection: `collect_all_tenants` beat task on `COLLECTION_INTERVAL_MINUTES`, creates a
  default assessment when a tenant has none; Data Collection page adds manual full/collector runs.
- Migrations: `003_alerts_and_audit_chain`. Checks: 639 tests, ruff, mypy 110 files, frontend
  build + ESLint clean.

## 2026-11-18 — Zero Trust Assessment and multi-cloud remediation

- New **ZT Assessment** page (`/zero-trust/assessment`, side nav): imports Microsoft's
  `ZeroTrustAssessmentReport.json`, scores it per pillar, filters by status/pillar/text, and
  expands each check to Microsoft's remediation steps.
- `POST /zerotrust/import` (normaliser accepts list / pillar sections / id-keyed / nested),
  `POST /zerotrust/run` (AWS, GCP, Google Workspace from latest findings), `/summary`, `/runs`,
  `/checks`, `/script`. New tables `zerotrust_runs` / `zerotrust_checks` (migration `004`).
- All 22 AWS/GCP/Workspace controls now carry `remediation.summary` + steps; `ControlLoader`
  parses them into `remediation_summary` / `remediation_steps`.
- `scripts/zerotrust/Invoke-UniMonitorZeroTrust.ps1` installs/connects/runs the module and posts
  the report; bundled by the PyInstaller spec, downloadable from the page, parsed in the Windows
  installer and release workflows.
- Certificate rotation from Settings now asks for the lifetime (1–1095 days, default 365).
- API stays at v1: every new endpoint is additive, so a v2 would duplicate routes with no
  contract change.
- Checks: 656 tests, ruff, mypy 115 files, frontend build + ESLint clean.

## 2026-11-19 — Zero Trust retention, executive scores, installer fix

- Imported runs are pruned to the newest 5 per tenant and platform (`RETAIN_RUNS_PER_PLATFORM`,
  `service.prune_runs`), so scheduled imports no longer grow the table and their checks unbounded.
- `GET /dashboard/executive` now returns `zero_trust` (latest score, totals and run date per
  platform); the Executive Dashboard renders them as a score strip.
- Windows installer workflow failed on `8ac2860`: PyInstaller 6 collects datas into
  `dist/UniMonitor/_internal/`, not beside the exe. The check in both workflows now accepts either
  location, so the runner is found where it actually lands.
- Checks: 660 tests, ruff check/format, mypy 115 files, frontend build + ESLint clean.

## Resume Instructions

1. Read `SECTION_STATE.md`… i.e. this file, `NEXT_ACTIONS.md`, `GAP_REGISTER.md`,
   `BUILD_STATUS.md`, `TECHNOLOGY_BASELINE.md`, `PROJECT_REQUIREMENTS.md`.
2. Country-free first action: push the release tag if the session allows it.
3. Then the Windows validation block, or the control-library expansion if no Windows host exists.
4. Do NOT re-audit completed work. Do NOT regenerate the Phase 6 guides.

## Usage Limit Procedure

At ~95% context: update all four trackers, commit, push, stop. Never leave untracked work.

## 2026-11-19 (later) — collection without Celery, Entra 403, SonarQube pass

A Windows install runs one process and no Redis, so `.delay()` raised and every
collection button answered 503; the Security dashboard had no real data and fell back to
hardcoded demo cards.

- `worker/inline.py`: `dispatch()` queues on Celery when a broker answers and otherwise
  runs the same coroutine as a background asyncio task; `collect_periodically()` is the
  broker-less beat. `main.lifespan` starts it when `AUTO_COLLECTION_ENABLED` and no broker,
  so automatic collection works on a single node and still runs once in Celery when a
  worker exists. Task bodies moved to `run_assessment_now`, `run_collector_now`,
  `collect_all_tenants_now` and are shared by the Celery tasks and the API.
- `monitoring.collect` / `monitoring.run_collector` / `assessments.trigger_run` use
  `dispatch`, so they no longer answer 503 without a worker. `assessments.trigger_run`
  also stopped queuing with missing `tenant_id`/`frameworks`.
- Security dashboard: the fabricated M365 coverage cards are gone; it shows real open
  findings by severity plus the collector table. The collector list read
  `collectors.collectors` from an array endpoint, which is why it always said "No collector
  data"; the row now uses `last_status`/`last_duration_seconds`.
- Entra setup: `POST /applications` now carries `keyCredentials`, so the certificate is
  created with the app. The separate `addKey` call the signed-in administrator made was
  what answered `403 Authorization_RequestDenied / Insufficient privileges`; it remains as
  a fallback only.
- SonarQube: nested ternaries and template literals on the dashboards, unstable list keys,
  palette a11y (role + keyboard + ref focus instead of `autoFocus`), `dataset` over
  `setAttribute`, duplicated literals (`Finding not found`, `Assessment not found`, tenant
  query text, `Table Grid`, `SET NULL`), cognitive complexity in `normalise_checks`,
  `provision_app` and `dashboard_zero_trust`, the self-comparing test assertion, and the
  duplicated tenant resolver (`core/tenants.resolve_tenant`). FastAPI `Annotated`/
  `response_model`/`responses` style reminders were left alone: no behaviour, large churn.
- Checks: 662 pytest, ruff check + format, mypy (117 files), `npm run build`, ESLint.

## 2026-11-19 (installer + branding) — frozen-build fix, About page, 1.1.0

The packaged app broke `/setup` because the new startup path imported the Celery
broker probe, and PyInstaller's celery/kombu hooks left `celery.fixups`,
`celery.loaders.app` and the redis transport out of the bundle: the ImportError killed
the lifespan, so every page failed — exactly the reported "setup page erroring out".

- `main.lifespan`: the automatic-collection block is wrapped in try/except and logs a
  warning when it cannot start, so a collector-side import error can never stop the API
  booting. The first in-process run waits 120s (`INITIAL_COLLECTION_DELAY_SECONDS`) so
  setup and the dashboard get a responsive server first.
- `deploy/windows/unimonitor.spec`: collect all `celery` and `kombu` submodules plus
  `kombu.transport.redis`. Verified by building the frozen bundle on Linux and reading
  the startup log: `Automatic collection running in-process first_run_in_seconds=120`.
- `unimonitor/cli.py`: `--version` no longer looks up distribution metadata (which does
  not exist in a frozen build); it uses `unimonitor.__version__`, now 1.1.0.
- `/setup` when no frontend build exists answers with a 503 HTML page explaining
  `npm run build`, instead of a bare JSON 404 (source runs only; installers bundle it).
- Setup page: shows the API's error detail with a retry button, tolerates a missing
  `platforms`/`connections` array, and its route is wrapped in the error boundary.
- Zero Trust: Microsoft's 364 upstream PowerShell tests are ported into the Python
  catalogue (`unimonitor/zerotrust/microsoft_tests.py`, generated by
  `scripts/import_zt_tests.py` from the reference clone). A control declares
  `ms_zt_tests` to supply evidence for a test; 66 controls are mapped, the rest of the
  tests report `not_run` and the 92 unmapped controls keep their own check row, so a
  Microsoft run is 364 + 92 rows and never scores an unevaluated test as a pass.
- Zero Trust: the Python engine is the default for all four platforms (Microsoft is
  served from the test catalogue above; AWS 8, GCP 8, Workspace 6),
  `POST /zerotrust/run-all` scores every platform in one pass, and the page keeps the
  PowerShell download/import as a manual fallback.
- Branding: publisher/company is "Belle-Raja Corp" (installer, PE version info, package
  metadata, sidebar and About page), contact Contact@Belle-RajaCorp.com, new About & Help
  page crediting Raj Raja as designer/builder, logo at `frontend/public/belle-raja-corp.png`
  (the supplied `belle-raja-corp.jpg`, background knocked out).
- Version 1.1.0 across `pyproject.toml`, `main.APP_VERSION`, `unimonitor.__version__`,
  `install.nsi` and the installer workflow default.
- Reference clones: `reference/` (git-ignored) for vigil365, m365_sheppard and
  zerotrustassessment; `scripts/update-reference-repos.sh` clones or fast-forwards them;
  `docs/REFERENCE_REPOS.md` records what each one is for.
- Checks: 663 pytest, ruff check/format, mypy, `npm run build`, ESLint, frozen-bundle
  startup and `/setup` smoke test.
