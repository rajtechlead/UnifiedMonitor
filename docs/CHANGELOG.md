# Changelog

All notable changes to UniMonitor are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — 2026-11-22

### Security

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

- `docs/PLATFORM_OBSERVATIONS_2026-11-22.md` — the 19-item owner review with root
  causes, what changed, and what remains open.

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
