# Changelog

All notable changes to UniMonitor are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — 2026-11-24 (owner observations, fourth round)

Tracker: `docs/TRACKER.md`.

### Fixed

- Microsoft sign-in builds the Entra authorization URL itself from the connected app,
  so a local MSAL/authority problem cannot show "sign-in is not configured". Missing
  apps and rejected callbacks return to the login page with the real reason, and the
  setup wizard registers the callback of the origin it is served from.
- Zero Trust for Microsoft: the upstream module now runs automatically on a Windows
  host with a certificate, and its `ZeroTrustAssessmentReport.json` is imported so
  every one of its tests shows its real status instead of "not run".
- Control scorecard PDF falls back to a valid minimal PDF when ReportLab is missing;
  the page shows the API's error detail.
- Microsoft cloud audit surfaces Graph's 403 body (the missing permission/consent) and
  retries once with a fresh token after a permission grant.
- About page no longer displays a version tag.

## [Unreleased] — 2026-11-24 (owner observations, third round)

Tracker: `docs/TRACKER.md`.

### Fixed

- Microsoft sign-in: the SPA now consumes the `#access_token` fragment, reads
  `/auth/me` and strips the token from the address bar; the callback URL is derived
  from the request origin unless explicitly configured. Delegated sign-in requests
  only `openid profile email offline_access User.Read` instead of also asking for the
  application-only `Organization.Read.All`, which forced admin consent at login.
- Re-login role: `POST /auth/login` returns the account profile (login and refresh),
  so the SPA no longer stores an undefined user and shows administrators as viewers.
- Risk heatmap: cells carry their real finding ids; the dashboard no longer drops
  every cell. SOC incident trend counts findings by first-seen day, not only alerts.
- Zero Trust report links are fetched with the bearer token and opened from a blob;
  the PowerShell runner now uses the upstream module's certificate app-auth
  (`-Certificate <thumbprint>`), since it has no client-secret switch. PFX lives in a
  private temp folder and its password travels only in the environment.
- Corrupt PDFs: the no-ReportLab fallback used to store a .txt file under the `pdf`
  format; it now writes a valid minimal PDF. The PyInstaller spec collects ReportLab
  and openpyxl data and submodules.
- Reports only include findings from connected providers; the table shows tenant id,
  tenant name, assessment name and the requester's name.
- Microsoft cloud audit errors carry Graph detail; a timeout now names itself instead
  of rendering an empty reason. Per-source timeout raised to 30 s.
- Service health shows per-service advisory counts, admin-center links, advisory
  ids/features/updates and operational/degraded severity coverage.
- Connector URL fields use the shared public-target validation (no loopback, private
  range or cloud-metadata host); reserved ranges were added to that validator.

### Added

- Graph `sendMail` through the connected Entra app as the default notification
  sender, with SMTP still available when enabled.
- Per-client external links (dedicated portal / sub-tenant) in tenant settings.

### Removed

- Okta from the onboarding platform picker and its unused validation: it is an SSO
  provider only, because UniMonitor has no Okta evidence collector.

---

## [Unreleased] — 2026-11-23 (owner observations)

Tracker: `docs/TRACKER.md`.

### Added

- Per-client settings and connections: `GET/PUT /tenants/{id}/settings`,
  `GET/POST/DELETE /tenants/{id}/connections` and a `TenantSettingsPage`, so a primary
  administrator can connect Microsoft 365, AWS, GCP, Google Workspace and Okta for each
  client. Client creation now needs only a name; Microsoft fields are optional.
- Okta as a first-class platform (provider metadata, onboarding validation and connect
  form) and per-client Graph secrets in the vault (`client_secret_ref` only in the DB).
- Vault-backed SIEM and ticketing connectors: `PUT/DELETE
  /integrations/{kind}/{provider}/config`, a Connect/Update form in Settings, validated
  fields, and the environment as fallback.
- Built-in AI providers with vault-stored keys, per-provider test and a persisted
  auto-switchover order (`/ai/settings`, `/ai/status`, remediation chain custom →
  tenant built-ins → environment built-ins).
- Zero Trust execution: background assessment task, PowerShell app-only wrapper with
  Python fallback, and a self-contained interactive HTML report written to
  `ZT assessments` (`POST /zerotrust/assess`, `GET /zerotrust/reports`).
- `grc/framework_reference.py`: publisher, version, control/requirement totals, levels
  and source link for all 34 frameworks; cumulative levels are expanded in the
  requirement catalogue and shown in the auditor portal.

### Fixed

- Microsoft sign-in, service health and licensing resolve the Entra app from the saved
  connection instead of startup settings; Graph errors map to 503/403/502 with the real
  Graph code instead of a blanket 502.
- `/reports/runs` used columns `AssessmentRun` does not have, so the run picker was
  always empty; report rows are now persisted by the worker with formats and paths.
- Audit page groups Microsoft 365, AWS, GCP and Workspace rows by platform, reports
  per-source failures, and keeps UniMonitor's own audit log.

### Packaging

- Windows spec hidden imports cover `zerotrust.reports`, `zerotrust.runner`,
  `worker.tasks.zerotrust`, `ai.builtin`, `grc.framework_reference` and the integration
  modules; the NSIS installer creates `ZT assessments` and sets `UNIMONITOR_ZT_DIR`.

---

## [Unreleased] — 2026-11-23

### Security

- Posture analysis is tenant-scoped. `/posture/analysis` reads only the inventory the
  caller's own tenant produced; it no longer falls back to the deployment-wide
  `latest.json`, which mixed every tenant's resources. Automatic inventories are written
  per tenant only, and nothing is written when no tenant is supplied.
- `/posture/analysis` accepts an optional `tenant_id` resolved through the shared
  tenant-scope dependency. Administrators and holders of a delegated `tenant_access`
  grant may read another tenant's collected inventory; everyone else stays pinned to
  their home tenant.

### Fixed

- Graph collectors keep a response answered from last-good cache during an outage.
  `GraphResponse.usable` is true for a fresh or a stale body, and every collector now
  checks it, so a transient Graph failure no longer empties the evidence a control
  evaluates. A 401/403 still raises instead of being masked by stale data.
- The stale flag is carried into the collected data (`_stale_keys`) and into finding
  evidence, so a control scored from last-good responses is visibly marked `stale`
  instead of looking like a fresh evaluation.
- Cleared the open Sonar findings from the 2026-11-23 scan: the nested ternaries in
  `AuditorPage` and `FrameworkPage` (S3358), the cognitive-complexity overruns in
  `custom._validate_target`, `cloud_providers.collect_google_workspace`,
  `requirements._derived_rows` and `posture.assemble._aws_resources` (S3776), and the
  intentionally blocked metadata addresses marked `NOSONAR` (S1313).

---

## [Unreleased] — 2026-11-22

### Security

- A tenant's custom AI provider URL may not target a cloud metadata service or a
  link-local address (`169.254.0.0/16`, `fe80::/10`, AWS/Azure/GCP/Alibaba/Oracle
  metadata hosts), and plain `http://` is accepted only for a loopback gateway.
  Credentials in the URL are refused.
- A malformed entry in a tenant's stored provider list is skipped with a warning
  instead of turning the settings page into a 500.
- The retired master key (`vault.key.previous`) is written owner-only and ignored by
  git, like `vault.key` itself.
- Every endpoint that accepts `tenant_id` now resolves it through
  `unimonitor/auth/tenant_scope.py` (44 query parameters plus body/model-carried ids),
  so a non-administrator cannot read another tenant by editing the URL. An account with
  no grant is pinned to its home tenant.
- `AuthorisationError` returns 403; it previously fell through to the generic 500 handler.

### Changed

- Removed unreferenced helpers and constants found by vulture/deadcode
  (`posture.engine.pass_if`, `posture.inventory.falsy`, `zerotrust.coverage._catalogue_tests`,
  `zerotrust.normalise.VALID_STATUSES`, `docx_generator.DARK_TEXT`), and the five open
  Sonar findings from the 2026-11-23 scan (S5778 x3, S6582, S8415).

### Added

- Automatic posture inventory: every assessment run assembles the collected AWS, GCP,
  Google Workspace and Microsoft data into the normalised resource model and writes it
  atomically, so the CIS/DSPM/CIEM/AI-SPM/attack-path engines run without an operator
  exporting JSON. A configured `UNIMONITOR_POSTURE_SNAPSHOT` still wins; the API now
  reports which source it used.
- Per-provider evidence coverage on `/grc/frameworks/{id}/evidence-coverage`
  (`by_provider`, `measured_providers`, `missing_providers`), shown on the framework page.
- A requirement/level catalogue for every framework (`unimonitor/grc/requirements.py`):
  CPCSC keeps its official 98, NIS2 and DORA their named measures, everything else a
  requirement view derived from existing control references or one control per
  requirement — labelled by source and filterable by level.
- Graph resilience: an outage (timeout, 5xx, connection error) is answered from the last
  successful response, marked `stale`, instead of leaving collectors empty; a revoked
  permission (401/403) is still a hard failure so stale data cannot hide it.
- Diagnostics bundle (`GET /settings/diagnostics`) and its Settings panel: versions,
  counts, collector catalogue and redacted configuration as a zip.
- Tenant lifecycle controls on the Managed Tenants page: add, suspend/activate, remove.
- Findings workspace: saved views and bulk acknowledge/resolve across selected rows.
- Monkey365-shaped collector additions: AWS EC2 metadata options/public IP/volume
  encryption, EBS default encryption and RDS exposure; GCP compute instances with
  external IPs and shielded-VM state; Workspace users without 2SV and group settings.
- Vault master-key rotation with retained previous keys, and `migrate_secrets()` to
  copy secrets (with tags) to another provider when changing backends.
- Framework registry test and a composite findings index (migration 009).

- Custom AI providers: a tenant can register an OpenAI-compatible endpoint (Settings →
  AI remediation providers), tried before the built-in chain, with the key in the secret
  provider. Azure OpenAI was removed from the provider list.
- Findings gained a "Generate AI guidance" button and provider attribution; the
  settings page shows built-in provider state and manages custom endpoints.

- Evidence status per control: `evaluated`, `stale` (older than `EVIDENCE_STALE_DAYS`,
  default 7) or `never_evaluated`, with the evaluation time and source run, plus
  `GET /grc/frameworks/{id}/evidence-coverage` for framework coverage.

- AI remediation now works: it was dead code (the endpoint imported a task that did
  not exist). Guidance is generated with an anonymised prompt through an ordered
  provider chain — Freebuff (all its models, discovered live), Groq, OpenAI, Anthropic
  (Claude) and Azure OpenAI — failing over automatically when a provider is out of
  quota or unavailable. `GET /ai/status` and `GET /ai/models` expose the provider and
  model lists without keys.
- Sign-in with Google Workspace and Okta, alongside Microsoft, through one OIDC
  provider list (`/auth/sso/providers`, `/auth/oidc/{provider}/login|callback`).
- `docs/AI_REMEDIATION_AND_SSO.md` and `docs/MONKEY365_COMPARISON.md`.

- Both notification APIs write one document (`unimonitor/notifications/preferences.py`).
  The SMTP password and the Teams, Slack and generic webhook credentials are stored in
  the secret provider and masked on read; the nested API previously wrote an attribute
  that did not exist and silently dropped them.
- SPA/API contract tests compare `useApi.ts` with the OpenAPI document: paths, query
  parameters and response fields.
- SOC dashboard metrics: active, acknowledged and 24-hour resolved alert counts, mean
  time to acknowledge and resolve, and a seven-day incident trend, all from `Alert` rows.
- Assessment runs display their `error_message` when a run fails.

### Fixed

- First-time SSO sign-in failed: `upsert_from_entra` created users without the
  NOT NULL `tenant_id`. New accounts are now attached by Entra `tid`, or to the only
  active tenant, and refused rather than guessed when ambiguous.
- The AI remediation endpoint now checks the caller may see the finding's tenant.

- Manual assessment runs: `run_assessment_task` is exported from `unimonitor.worker.tasks`
  again (its absence made every manual run fail), and a dispatch failure now returns the
  real error instead of "queued successfully".
- `tenant_id` now appears in the OpenAPI document for every endpoint scoped through the
  tenant dependency.
- The assessment runs response includes `triggered_by` and `findings_count`, which the
  runs table reads.

- Local vault writes are atomic (temp file + `fsync` + `os.replace`) for the ciphertext,
  the metadata and a newly generated master key, so a crash mid-write cannot truncate
  the vault. Two regression tests fail the write at `fsync` and at the rename.
- Findings accepted `severity` only in the exact stored case; the SOC dashboard links
  sent uppercase and returned no rows. Filtering (list and SIEM export) is now
  case-insensitive.
- Risk dashboard counted open findings belonging to providers that are not connected.
- Delegated tenant access requested `page_size=200` (the API caps at 100) and read a
  bare `/users` array as `{items}`, leaving both dropdowns empty.
- Settings posted to a non-existent `/settings/notifications`; notification preferences
  now persist in `Tenant.settings_json`, while the SMTP password is written to the
  configured secret provider (encrypted local vault by default) and only masked out of
  the API. A password left in the settings row by the earlier build migrates on save.

### Added

- `GET /dashboard/ciso` returns `strongest_frameworks`; the control-state footer counts
  link into the filtered findings list.
- Executive dashboard framework-coverage widget has a per-framework selector.
- New assessments list every registered framework rather than ten hard-coded ids.
- Optional local password when creating a user.

### Documentation

- The 19-item owner review of 2026-11-22 (root causes, what changed, and what
  remains open) is consolidated into `docs/TRACKER.md`.

---

## [Unreleased] — Session 5 (2026-11-06)

### Added

#### Secret Management System (GAP-001)
- `unimonitor/secrets/provider.py` — `SecretProvider` protocol, `SecretMetadata`, `HealthStatus`, `ProviderType`
- `unimonitor/secrets/azure_keyvault.py` — Azure Key Vault provider (azure-keyvault-secrets + azure-identity)
- `unimonitor/secrets/aws_secrets_manager.py` — AWS Secrets Manager provider (boto3)
- `unimonitor/secrets/local_vault.py` — Fernet-encrypted local vault (cryptography)
- `unimonitor/secrets/cache.py` — TTL-based in-memory secret cache
- `unimonitor/secrets/audit.py` — Structured audit log for all secret operations
- `unimonitor/secrets/rotation.py` — `RotationManager` with rotation-due detection
- `unimonitor/secrets/health.py` — `check_all_providers()` aggregated health reporting
- `unimonitor/secrets/resolver.py` — `SecretResolver` with caching, failover, `resolve_ref()`

#### First-Run Setup Wizard (GAP-002)
- `scripts/setup_wizard.py` — Rich CLI wizard: provider selection → validation → DB migration → admin account → readiness report

#### Missing Foundational Files (GAP-004, GAP-005, GAP-006, GAP-008)
- `unimonitor/db/models/tenant.py` — `Tenant` SQLAlchemy model
- `unimonitor/db/models/user.py` — `User` SQLAlchemy model (hashed_password, entra_oid, role, is_active)
- `unimonitor/db/session.py` — `AsyncSessionLocal`, `get_db` aliases to `base.py`

#### CLI Entry Point (GAP-013)
- `unimonitor/cli.py` — Click CLI with `start`, `setup`, `migrate`, `smoke-test`, `secrets` command group

#### GRC Scoring Aliases (GAP-007)
- `unimonitor/grc/scoring.py` — Added `SEVERITY_WEIGHTS` dict, `compute_score()`, `compute_framework_score()` functions

#### Secret Provider Tests (GAP-018)
- `tests/unit/test_secrets.py` — 25 unit tests: Local Vault, SecretCache, SecretResolver, protocol compliance

#### Configuration Improvements (GAP-023, GAP-025, GAP-030)
- `unimonitor/config.py` — Added `REPORTS_DIR` property alias, `SECRETS_PROVIDER` and related settings, `@model_validator` to reject default SECRET_KEY in production, `SMTP_PASSWORD_REF` reference field

#### pyproject.toml (GAP-030)
- Added optional extras: `azure-secrets`, `aws-secrets`, `all-secrets`
- Added `moto[secretsmanager]` to dev dependencies

#### Documentation (GAP-022)
- `README.md` — Project readme with quick-start, architecture overview, links
- `docs/ARCHITECTURE.md` — System design, component descriptions, data flow
- `docs/SECRET_MANAGEMENT.md` — Provider setup, CLI, audit log, Kubernetes ESO examples
- `docs/CHANGELOG.md` — This file
- `docs/DEPLOYMENT_GUIDE.md` — Windows, Docker, Kubernetes, Azure Container Apps, AWS ECS
- `docs/PRODUCTION_READINESS.md` — Pre-production checklist
- `docs/NEXT_SESSION_PLAN.md` — Continuation plan for next session

#### Infrastructure
- `.gitignore` — Comprehensive Python/Node/secrets/vault exclusions (GAP-012)
- `LICENSE` — Proprietary software license (GAP-034)

#### Kubernetes Secret Security (GAP-010, GAP-032)
- `deploy/kubernetes/external-secrets/` — ExternalSecret CRD examples for all three providers

---

## [0.1.0] — Sessions 1–4 (2026-11-05/06) — Initial Build

### Added

#### Backend
- `unimonitor/main.py` — FastAPI lifespan, OTEL setup, exception handlers, health endpoints
- `unimonitor/config.py` — `Settings(BaseSettings)` via pydantic-settings
- `unimonitor/db/base.py` — SQLAlchemy async engine, session factory, `Base`
- `unimonitor/db/models/` — `Finding`, `Assessment`, `Report`, `ScheduledTask` models
- `unimonitor/db/repositories/` — Repository pattern for all models
- `unimonitor/grc/engine.py` — `AssessmentEngine` orchestration
- `unimonitor/grc/scoring.py` — `calculate_scores()`, `calculate_framework_coverage()`
- `unimonitor/grc/control_loader.py` — YAML control loader
- `unimonitor/grc/crosswalk.py` — Framework cross-reference mapping
- `unimonitor/grc/ai_remediation.py` — Azure OpenAI + rule-based remediation
- `unimonitor/graph/client.py` — Microsoft Graph API async client with rate limiting
- `unimonitor/graph/collectors/entra_id.py` — Entra ID collector
- `unimonitor/graph/collectors/intune.py` — Intune/MDM collector
- `unimonitor/reporting/` — PDF, DOCX, JSON, CSV report generators
- `unimonitor/tasks/` — Celery task definitions
- `unimonitor/api/v1/` — Full REST API: auth, tenants, assessments, findings, reports, settings

#### Frontend
- React 18 + TypeScript + Vite application
- 7 dashboard pages: Executive, Security, Compliance, Findings, Assessments, Reports, Settings
- Zustand state management with persist middleware
- TanStack Query v5 for server state
- Recharts data visualizations

#### Infrastructure
- `deploy/docker/docker-compose.yml` — Full stack with health checks
- `deploy/kubernetes/` — Namespace, ConfigMap, Deployment, Service, Ingress
- `installer/install.nsi` — Windows MSI installer (NSIS)
- `installer/unimonitor.spec` — PyInstaller spec

#### Tests
- `tests/conftest.py` — pytest fixtures, async test client
- `tests/unit/test_grc_engine.py` — GRC engine unit tests
- `tests/unit/test_scoring.py` — Scoring algorithm tests
- `tests/unit/test_ai_remediation.py` — AI remediation tests
- `tests/unit/test_reporting.py` — Report generation tests
- `tests/integration/test_api_health.py` — API health endpoint tests

#### Controls
- YAML control definitions for Identity, Devices, Defender, Data Protection
- Framework mappings for 13 GRC frameworks
