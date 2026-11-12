# Changelog

All notable changes to UniMonitor are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
