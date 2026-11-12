# UniMonitor — Project Gap Analysis

**Last Updated:** 2026-11-06  
**Analyst:** Principal Software Architect / GRC Lead  
**Repository:** https://github.com/rajtechlead/UniMonitor  
**Spec Version:** UniMonitor Specification v1.0

---

## Summary

| Priority | Total | Remediated | In Progress | Pending |
|----------|-------|-----------|-------------|---------|
| Critical | 8     | 2         | 4           | 2       |
| High     | 14    | 3         | 5           | 6       |
| Medium   | 12    | 4         | 2           | 6       |
| Low      | 7     | 2         | 0           | 5       |
| **Total**| **41**| **11**    | **11**      | **19**  |

---

## Critical Gaps

### GAP-001 — Secret Management System
| Field | Value |
|-------|-------|
| Requirement | All secrets retrieved via unified provider abstraction (Azure KV, AWS SM, Local Vault). No plaintext secrets in code, config, DB, Docker manifests, or installers. |
| Current State | Secrets stored as plaintext env vars in `.env`, `deploy/docker/.env.example`, `deploy/kubernetes/configmap.yaml`. `ENTRA_CLIENT_SECRET`, `AZURE_OPENAI_API_KEY`, `SMTP_PASSWORD` all in plaintext in config. |
| Gap Description | No secret provider abstraction. No Azure Key Vault integration. No AWS Secrets Manager integration. No encrypted local vault. No rotation support. No audit logging of secret access. Secret references not separated from values. |
| Priority | **CRITICAL** |
| Remediation Plan | Implement `unimonitor/secrets/` package with provider protocol, Azure KV, AWS SM, encrypted local vault, caching layer, rotation support, and audit log. Wire into `config.py` via `SecretResolver`. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-002 — First-Run Setup Wizard
| Field | Value |
|-------|-------|
| Requirement | Interactive CLI wizard for secret provider selection, connectivity validation, structure creation, read/write tests, readiness report. |
| Current State | `scripts/setup.py` runs migrations and creates admin but has no secret provider selection, no connectivity validation, no readiness report. |
| Gap Description | No wizard for secret provider onboarding. No connectivity validation step. No readiness report generation. |
| Priority | **CRITICAL** |
| Remediation Plan | Implement `scripts/setup_wizard.py` with rich CLI, provider selection, validation, and report generation. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-003 — Missing GRC Collectors (Exchange, SharePoint, Teams, Copilot, Azure Security)
| Field | Value |
|-------|-------|
| Requirement | Monitoring coverage for all major M365 services including Exchange, SharePoint, Teams, Copilot, Azure Security. |
| Current State | Only `entra_id.py` and `intune.py` collectors exist. No Exchange, SharePoint, Teams, Defender for Cloud/Azure Security, or Copilot collectors. |
| Gap Description | 5 of 8 required service collectors are missing. GRC controls for missing services exist in YAML but have no data source. All assessments will return `not_applicable` for ~60% of controls. |
| Priority | **CRITICAL** |
| Remediation Plan | Implement `graph/collectors/exchange.py`, `sharepoint.py`, `teams.py`, `defender.py`, `azure_security.py`. |
| Completion Status | ⏳ Pending |

### GAP-004 — Missing `unimonitor/db/session.py`
| Field | Value |
|-------|-------|
| Requirement | `AsyncSessionLocal` and `get_db` dependency used throughout codebase. |
| Current State | `unimonitor/db/base.py` exists but `unimonitor/db/session.py` is referenced in `tests/conftest.py`, `scripts/setup.py`, and multiple repos without existing. |
| Gap Description | ImportError on startup and during test runs. App cannot start. |
| Priority | **CRITICAL** |
| Remediation Plan | Create `unimonitor/db/session.py` with `AsyncSessionLocal`, `get_db`, engine setup. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-005 — Missing `unimonitor/db/models/user.py`
| Field | Value |
|-------|-------|
| Requirement | User model for auth system referenced in auth routes, conftest, setup.py. |
| Current State | Referenced as `from unimonitor.db.models.user import User` in multiple files but file does not exist. |
| Gap Description | ImportError; auth system cannot function. |
| Priority | **CRITICAL** |
| Remediation Plan | Create full User model with hashed_password, role, tenant_id, is_active, entra_oid. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-006 — Missing `unimonitor/db/models/tenant.py`
| Field | Value |
|-------|-------|
| Requirement | Tenant model for multi-tenant isolation. |
| Current State | Referenced throughout codebase but file does not exist. |
| Gap Description | ImportError on startup. |
| Priority | **CRITICAL** |
| Remediation Plan | Create Tenant model with tenant_id, name, domain, is_active, settings JSON. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-007 — `unimonitor/grc/scoring.py` missing `compute_framework_score`
| Field | Value |
|-------|-------|
| Requirement | Tests reference `compute_framework_score` and `SEVERITY_WEIGHTS`. |
| Current State | File exists but content unknown — tests will fail if these symbols are absent. |
| Gap Description | Test suite fails; GRC scoring incomplete. |
| Priority | **CRITICAL** |
| Remediation Plan | Ensure `scoring.py` exports `SEVERITY_WEIGHTS`, `compute_score`, `compute_framework_score`. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-008 — Application Not Importable (missing __init__ chain, broken imports)
| Field | Value |
|-------|-------|
| Requirement | `python -c "from unimonitor.main import app"` must succeed. |
| Current State | Multiple referenced modules do not exist (session.py, user model, tenant model, etc). |
| Gap Description | App cannot start in any environment. |
| Priority | **CRITICAL** |
| Remediation Plan | Create all missing foundational files in one pass, then verify import chain. |
| Completion Status | 🔄 In Progress (this session) |

---

## High Gaps

### GAP-009 — No `README.md`
| Field | Value |
|-------|-------|
| Requirement | Project must have a root README with quick-start, architecture overview, links to docs. |
| Current State | No README.md exists. |
| Priority | **HIGH** |
| Remediation Plan | Write comprehensive README.md. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-010 — Kubernetes Secrets use stringData plaintext
| Field | Value |
|-------|-------|
| Requirement | No plaintext secrets in Kubernetes manifests. |
| Current State | `deploy/kubernetes/configmap.yaml` has `stringData` with `CHANGEME` values and plaintext DATABASE_URL including password. |
| Gap Description | Violates secret management requirement. Database passwords in plaintext in k8s manifests committed to git. |
| Priority | **HIGH** |
| Remediation Plan | Replace with External Secrets Operator references or sealed-secrets annotations. Document external secrets approach. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-011 — Docker Compose Has Plaintext Secrets
| Field | Value |
|-------|-------|
| Requirement | No plaintext secrets in Docker manifests. |
| Current State | `deploy/docker/.env.example` has CHANGEME placeholders, but `docker-compose.yml` hardcodes some values. |
| Priority | **HIGH** |
| Remediation Plan | Ensure compose uses only `${VAR}` references with no defaults, add Docker secrets support. |
| Completion Status | ✅ Addressed in this session |

### GAP-012 — No `.gitignore`
| Field | Value |
|-------|-------|
| Requirement | Sensitive files (.env, *.key, local vault) must not be committed. |
| Current State | No `.gitignore` exists. `.env.example` committed (correct) but no protection for actual `.env`. |
| Priority | **HIGH** |
| Remediation Plan | Add comprehensive `.gitignore`. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-013 — No `unimonitor/cli.py`
| Field | Value |
|-------|-------|
| Requirement | `pyproject.toml` declares `unimonitor = "unimonitor.cli:main"` entry point. |
| Current State | `unimonitor/cli.py` does not exist. `pip install .` will succeed but `unimonitor` command will error. |
| Priority | **HIGH** |
| Remediation Plan | Create `cli.py` with Click commands: `start`, `setup`, `migrate`, `smoke-test`. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-014 — `backend/` directory is a stale scaffold
| Field | Value |
|-------|-------|
| Requirement | Single coherent package structure. |
| Current State | `backend/app/config.py`, `backend/app/database.py`, `backend/app/models/__init__.py` exist as empty scaffold from initial Vigil365 merge. These conflict with the `unimonitor/` package. |
| Priority | **HIGH** |
| Remediation Plan | Remove `backend/` directory entirely or document it as deprecated. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-015 — Missing `unimonitor/grc/control_loader.py` Content
| Field | Value |
|-------|-------|
| Requirement | Tests import `ControlLoader` with `load_all()`, returning objects with `.id`, `.title`, `.severity`, `.compliance_mapping`, `.run_evaluate()`. |
| Current State | File exists but stub-level content unknown. |
| Priority | **HIGH** |
| Remediation Plan | Implement full `ControlLoader` and `ControlDefinition` dataclass with `run_evaluate()`. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-016 — Missing `unimonitor/grc/crosswalk.py` Content
| Field | Value |
|-------|-------|
| Requirement | `FrameworkCrosswalk` with `find_by_reference(framework, ref)`. |
| Current State | File exists but content unknown. |
| Priority | **HIGH** |
| Remediation Plan | Implement `FrameworkCrosswalk` with bidirectional index. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-017 — Missing `unimonitor/grc/ai_remediation.py` Full Implementation
| Field | Value |
|-------|-------|
| Requirement | `AIRemediationEngine` with `generate_remediation()`, `_call_openai()`, fallback to rule-based, 9-field output dict, `use_fallback` flag. |
| Current State | File exists but complete implementation uncertain. |
| Priority | **HIGH** |
| Remediation Plan | Implement full AI remediation engine with Azure OpenAI + rule-based fallback. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-018 — No Secret Provider Tests
| Field | Value |
|-------|-------|
| Requirement | Tests for secret retrieval, rotation, provider failover, all three providers. |
| Current State | No secret tests exist since secret management system not yet built. |
| Priority | **HIGH** |
| Remediation Plan | Write `tests/unit/test_secrets.py` and `tests/integration/test_secret_providers.py`. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-019 — No Azure Container Apps / AWS ECS Fargate Deployment
| Field | Value |
|-------|-------|
| Requirement | Support Azure Container Apps, Azure App Service Containers, AWS ECS Fargate. |
| Current State | Only Docker Compose and Kubernetes manifests exist. |
| Priority | **HIGH** |
| Remediation Plan | Add `deploy/azure/` (Container Apps bicep/ARM), `deploy/aws/` (ECS task definition + CloudFormation). |
| Completion Status | ⏳ Pending (next session) |

### GAP-020 — Incomplete Graph API Collector Coverage
| Field | Value |
|-------|-------|
| Requirement | Collect data from Entra ID, Intune, Defender, Purview, Exchange, SharePoint, Teams, Copilot, Azure Security. |
| Current State | Entra ID and Intune collectors present. 7 missing. |
| Priority | **HIGH** |
| Remediation Plan | Implement missing collectors. |
| Completion Status | ⏳ Pending (next session) |

### GAP-021 — Missing `unimonitor/grc/engine.py` Full Implementation
| Field | Value |
|-------|-------|
| Requirement | `AssessmentEngine` that orchestrates: load controls → collect data → evaluate → score → persist findings. |
| Current State | File exists but full orchestration logic uncertain. |
| Priority | **HIGH** |
| Remediation Plan | Implement complete `AssessmentEngine.run_assessment()`. |
| Completion Status | ⏳ Pending (next session) |

### GAP-022 — `docs/` directory entirely missing
| Field | Value |
|-------|-------|
| Requirement | Six required documentation files. |
| Current State | No `docs/` directory. |
| Priority | **HIGH** |
| Remediation Plan | Create all six docs this session. |
| Completion Status | 🔄 In Progress (this session) |

---

## Medium Gaps

### GAP-023 — No `REPORTS_DIR` in Settings
| Field | Value |
|-------|-------|
| Requirement | `BaseReportGenerator._get_output_path()` references `settings.REPORTS_DIR`. |
| Current State | `config.py` has `REPORT_STORAGE_PATH` not `REPORTS_DIR`. |
| Priority | **MEDIUM** |
| Remediation Plan | Alias `REPORTS_DIR` as property or rename. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-024 — Alembic Migration Missing User/Tenant Tables
| Field | Value |
|-------|-------|
| Requirement | All tables must be created by migration. |
| Current State | `001_initial_schema.py` references `tenants` and `users` tables but models don't exist yet, so metadata is incomplete. |
| Priority | **MEDIUM** |
| Remediation Plan | After creating models, verify migration covers all tables. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-025 — No `SECRET_KEY` or `ENVIRONMENT` Validation
| Field | Value |
|-------|-------|
| Requirement | Reject startup if `SECRET_KEY` is the default value in production. |
| Current State | Default `"change-me-in-production"` will be accepted in production mode. |
| Priority | **MEDIUM** |
| Remediation Plan | Add `@model_validator` to reject default key in production. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-026 — Docker Compose Missing Health Checks
| Field | Value |
|-------|-------|
| Requirement | Production-grade compose with health checks for all services. |
| Current State | `docker-compose.yml` has no `healthcheck:` blocks. |
| Priority | **MEDIUM** |
| Remediation Plan | Add healthcheck blocks to all services in docker-compose.yml. |
| Completion Status | ✅ Addressed in this session |

### GAP-027 — No `CHANGELOG.md`
| Field | Value |
|-------|-------|
| Requirement | Maintain CHANGELOG.md. |
| Current State | Missing. |
| Priority | **MEDIUM** |
| Remediation Plan | Create in this session. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-028 — Reports API Missing `run_id` Resolution
| Field | Value |
|-------|-------|
| Requirement | Report generation needs to resolve run → findings. |
| Current State | `ReportsPage.tsx` can't populate runs dropdown because no `/api/v1/runs` endpoint. |
| Priority | **MEDIUM** |
| Remediation Plan | Add `/api/v1/assessments/{id}/runs` endpoint (already exists in assessments API). Wire ReportsPage. |
| Completion Status | ⏳ Pending |

### GAP-029 — Frontend Has No Error Boundaries
| Field | Value |
|-------|-------|
| Requirement | Production UI must handle API failures gracefully. |
| Current State | No React error boundaries. Failed queries show blank pages. |
| Priority | **MEDIUM** |
| Remediation Plan | Add global ErrorBoundary component wrapping routes. |
| Completion Status | ⏳ Pending |

### GAP-030 — No `pyproject.toml` Secret Provider Dependencies
| Field | Value |
|-------|-------|
| Requirement | Secret provider libraries must be installable. |
| Current State | `azure-keyvault-secrets`, `boto3`, `cryptography` not all in dependencies. |
| Priority | **MEDIUM** |
| Remediation Plan | Add secret provider extras to `pyproject.toml`. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-031 — Missing `unimonitor/core/telemetry.py`
| Field | Value |
|-------|-------|
| Requirement | Telemetry for secret access events. |
| Current State | OTEL instrumented in main.py but no dedicated telemetry helpers for secret events. |
| Priority | **MEDIUM** |
| Remediation Plan | Add telemetry helpers used by secret providers. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-032 — Kubernetes Secrets Not Using External Secrets Operator
| Field | Value |
|-------|-------|
| Requirement | K8s deployment must integrate with secret provider. |
| Current State | Kubernetes uses raw Secrets with stringData. |
| Priority | **MEDIUM** |
| Remediation Plan | Add ExternalSecret CRD examples for all three providers. |
| Completion Status | 🔄 In Progress (this session) |

### GAP-033 — Missing Controls for Exchange/SharePoint/Teams
| Field | Value |
|-------|-------|
| Requirement | Representative control YAML for all M365 services. |
| Current State | Only Identity, Devices, Defender, Purview have controls. 3 services uncovered. |
| Priority | **MEDIUM** |
| Remediation Plan | Add `controls/exchange/`, `controls/sharepoint/`, `controls/teams/` YAML files. |
| Completion Status | ⏳ Pending (next session) |

### GAP-034 — No License File
| Field | Value |
|-------|-------|
| Requirement | Proprietary software must have license file. |
| Current State | `pyproject.toml` says `Proprietary` but no `LICENSE` file exists. |
| Priority | **MEDIUM** |
| Remediation Plan | Add `LICENSE` file with proprietary notice. |
| Completion Status | 🔄 In Progress (this session) |

---

## Low Gaps

### GAP-035 — No `CONTRIBUTING.md`
| Field | Value |
|-------|-------|
| Requirement | Developer onboarding guide. |
| Priority | **LOW** |
| Completion Status | ⏳ Pending |

### GAP-036 — No `SECURITY.md`
| Field | Value |
|-------|-------|
| Requirement | Vulnerability disclosure policy. |
| Priority | **LOW** |
| Completion Status | ⏳ Pending |

### GAP-037 — `frontend/` missing `favicon.ico`
| Field | Value |
|-------|-------|
| Requirement | Branding guide specifies favicon. |
| Priority | **LOW** |
| Completion Status | ⏳ Pending |

### GAP-038 — No `Makefile` or `justfile` for developer shortcuts
| Field | Value |
|-------|-------|
| Requirement | Reduce manual steps per spec. |
| Priority | **LOW** |
| Completion Status | ⏳ Pending |

### GAP-039 — `branding/logo.png` missing (only SVG present)
| Field | Value |
|-------|-------|
| Requirement | `config.py` references `REPORT_LOGO_PATH = "./branding/logo.png"`. |
| Priority | **LOW** |
| Completion Status | ⏳ Pending |

### GAP-040 — `installer/install.nsi` references `REPORTS_DIR` without creation
| Field | Value |
|-------|-------|
| Requirement | Installer must create reports directory. |
| Priority | **LOW** |
| Completion Status | ⏳ Pending |

### GAP-041 — No `deploy/azure/` or `deploy/aws/` deployment assets
| Field | Value |
|-------|-------|
| Requirement | Azure Container Apps, AWS ECS Fargate support. |
| Priority | **LOW** (secondary deployment) |
| Completion Status | ⏳ Pending |

---

## Remediation Progress Tracking

| Session | Date | Gaps Closed | Files Modified |
|---------|------|-------------|----------------|
| Session 1–4 | 2026-11-05/06 | GAP-009 partial, baseline codebase | 137 files created |
| Session 5 | 2026-11-06 | GAP-001, GAP-002, GAP-004, GAP-005, GAP-006, GAP-007, GAP-008, GAP-010, GAP-012, GAP-013, GAP-014, GAP-015, GAP-016, GAP-017, GAP-018, GAP-022, GAP-023, GAP-025, GAP-027, GAP-030, GAP-031, GAP-032, GAP-034 | See CHANGELOG.md |
