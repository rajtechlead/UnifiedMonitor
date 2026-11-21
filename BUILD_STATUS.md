# BUILD_STATUS.md

Project: UnifiedMonitor
Repository: https://github.com/rajtechlead/UnifiedMonitor
Last Updated: 2026-11-20 UTC

## Current Release Status

Status: 🟢 Green locally — Release Candidate blocked on Windows validation + tag push

## Build Environment

| Item | Value |
|---|---|
| Python | 3.12.3 (requires >=3.12; CI 3.12.16) |
| Node | 26.13.0 locally, 20 in CI |
| OS | Linux (agent workspace / CI / Docker); Windows is the target installer platform |
| ruff | 0.17.5 |
| mypy | 2.4.1 |
| Vite | 5.4.21 |
| PyInstaller | 6.22.3 (last Linux validation 2026-11-13) |

## Backend Validation (measured 2026-11-20)

| Check | Status | Notes |
|---|---|---|
| Dependency installation | ✅ | `pip install -e ".[dev,production]"` clean |
| Test suite | ✅ 673/673 | 95s after caching the control library (was 329s); 8 warnings (AsyncMock coroutine never awaited inside mocks) |
| Control library | ✅ 190 controls | 23 YAML files; unique ids, valid severities; **33 frameworks** (CPCSC, 800-171, FedRAMP, NIS2, DORA, CCM, SCuBA, ISO extensions, AI frameworks, regional sets) all resolve to controls |
| Framework mappings | ✅ | `grc/framework_mappings.py` holds explicit CPCSC/NIS2/DORA maps and derived crosswalks; `SUPPORTED_FRAMEWORKS` and `FRAMEWORK_KEYS` are generated from the registry so they cannot drift (regression test asserts no orphan rule exists) |
| CPCSC requirement level | ✅ | all 98 ITSP.10.171 identifiers with titles and the 13 Level 1 flags; `/grc/frameworks/cpcsc/requirements` reports per-requirement status |
| Exception lifecycle | ✅ | time-boxed suppression (`expires_in_days`), auto-release on read, migration `005` |
| SIEM export | ✅ | `GET /findings/export/siem` (CEF / NDJSON), open findings only |
| Posture snapshot | ✅ | admin `GET/PUT /settings/posture-snapshot`, edited from the Settings page with JSON validation |
| Integrations | ✅ | SIEM push connectors (Datadog, Splunk HEC, Elastic, Sentinel, Sumo, Chronicle, Wazuh, webhook, CEF syslog) and idempotent Jira/ServiceNow/webhook ticket sync; env-configured, tested with fakes only |
| MTTR / SLA | ✅ | `/dashboard/trends` adds mean/median/p90 remediation hours per severity and open SLA breaches |
| MSP rollup | ✅ | `/tenants/rollup` plus the Managed Tenants page |
| Auditor portal | ✅ | hashed evidence package per framework and CPCSC requirement status page for auditor/compliance roles |
| Zero Trust catalogues | ✅ | Microsoft 364 upstream tests + native Python catalogues: AWS 19, GCP 15, Workspace 14; mapping and evidence-gap endpoints covered |
| Multi-cloud collectors | ✅ unit-tested | AWS (boto3), GCP + Workspace (REST); no live accounts exercised |
| First-run onboarding | ✅ 45 tests | setup window closes after the first admin; connect/list/delete; certificate default + manual-upload fallback; AWS role; one Google service account; sign-in client override; certificate expiry + rotation |
| Bundled UI | ✅ verify_bundled_ui.py | shell, hashed asset, `/setup` deep link, API precedence, 401/404 |
| Multi-cloud dashboards | ✅ API + UI | aggregate `/clouds` and per-provider `/clouds/{id}`; React `tsc` + vite build clean |
| CISO dashboard | ✅ API + UI | `/dashboard/ciso` and `/ciso` page; cloud exposure, top risks, framework gaps, trend |
| Report exports | ✅ PDF + DOCX | per-cloud sections in every report type; aggregate summary retained |
| Dependency audit | ✅ Clean | python-jose/ecdsa removed (PyJWT); pip-audit reports no known vulnerabilities |
| Installer workflow | ✅ On demand | `windows-installer.yml` dispatch builds the .exe + portable zip |
| Windows installer | 🟡 PyInstaller ✅ on runner | freezes 1134 files and `--help` passes on `windows-latest`; NSIS step fixed (`makensis` PATH) and awaiting a green run |
| Ruff check | ✅ CLEAN | 0 errors — was 157 on HEAD before this session |
| Ruff format | ✅ CLEAN | all Python files |
| mypy | ✅ CLEAN | 122 source files |
| SQLite validation | ✅ | in-memory SQLite for all tests |
| PostgreSQL validation | ⬜ | not exercised this session |
| Health endpoint | ✅ | covered by integration tests |
| Entra ID OAuth2 | ✅ | mocked in tests; live tenant not exercised |
| Secrets framework | ✅ | Azure KV / AWS SM / local store covered by tests |
| Redis / Celery | ⬜ | health check code present; no broker available here |

## Testing Status

| Test Type | Status | Count | Notes |
|---|---|---|---|
| Unit tests | ✅ PASS | 511+ | across 26 files |
| Integration tests | ✅ PASS | 122+ | health, e2e journeys, dashboard, cloud, CISO, onboarding, report, framework coverage, evidence gaps and SPA serving |
| New this session | ✅ | +5 | `tests/integration/test_dashboard_views.py` |
| Coverage | 🟡 62% | — | last measured at `79dfb98`; not re-measured |
| UI / Playwright | ⬜ NOT RUN | 4 tests exist | browsers not installed here; CI job `playwright-e2e` |
| Installer tests | ⬜ | — | Phase 5, Windows required |

## Frontend Validation (measured 2026-11-20)

| Check | Status | Notes |
|---|---|---|
| npm ci | ✅ | clean install from lockfile |
| ESLint | ✅ CLEAN | 0 warnings, `--max-warnings 0` |
| TypeScript (`tsc`) | ✅ | no type errors |
| Vite production build | ✅ | 5.2s; charts chunk 452 kB (gzip 127 kB) |
| npm audit | ⚠️ | major-version advisories only; two majors still pending |
| Playwright E2E smoke | ⬜ NOT RUN | CI only |

## Dashboard Views (requirement: Executive, Security, SOC, Compliance, Risk, Audit)

| View | API | UI | Notes |
|---|---|---|---|
| Executive | ✅ `/dashboard/executive` | ✅ | contract fixed this session |
| Security | ✅ `/dashboard/security` | ✅ | pre-existing |
| Compliance | ✅ `/dashboard/compliance` | ✅ | contract fixed this session |
| Risk | ✅ `/dashboard/risk` | ✅ | new this session (heatmap + critical risks) |
| SOC | ✅ `/dashboard/soc` | ✅ | new this session |
| Audit | ✅ `/dashboard/audit` | ✅ | new endpoint + page this session |

Visualisations present: radial gauges, bar, multi-line trend, radar, risk heatmap.
Still absent from the requirement list: maturity matrix, compliance waterfall, framework
crosswalk chart, executive scorecard export.

## Docker Validation

| Check | Status | Notes |
|---|---|---|
| Docker build (CI) | ✅ | green at `1de7bcd` |
| Docker Compose E2E | ⬜ | no daemon in agent workspace (M-015) |

## Windows Packaging Validation

| Component | Status | Known Issues |
|---|---|---|
| PyInstaller spec | ✅ Linux | 222 MB bundle; Windows-only module warnings expected |
| NSIS installer | ⬜ Windows only | `deploy/windows/install.nsi` |
| Fresh install / upgrade / rollback | ⬜ Windows only | |
| Setup wizard in installer flow | ⬜ | script exists, not wired (M-016) |

## CI Status

| Workflow | Status | Notes |
|---|---|---|
| `ci.yml` | 🟡 Unverified at HEAD | last green run `1de7bcd`; HEAD had 157 ruff + 2 mypy errors, now fixed locally |
| `release.yml` | ✅ Config OK | tag-triggered |
| `security-scan.yml` | ✅ Config OK | informational CVEs |

## Security Audit Findings

| Package | Version | CVE | Fix Available |
|---|---|---|---|
| ~~ecdsa~~ | 0.19.2 | PYSEC-2026-1325 | ✅ Removed with python-jose |
| ~~python-jose~~ | 3.5.0 | PYSEC-2026-4298 | ✅ Replaced by PyJWT |

Action: security debt closed (L-004, L-005) by migrating to PyJWT; `pip-audit` on a clean
runtime install reports no known vulnerabilities (verified 2026-11-17).

## Production Readiness Score (revised 2026-11-16)

| Area | Readiness |
|---|---|
| Backend stability | 88% |
| Test coverage | 62% (measured at `79dfb98`) |
| Security | 58% (two unfixable upstream CVEs, no live-tenant auth test) |
| Deployment | 70% (Docker CI green, Linux PyInstaller green, Windows pending) |
| Requirements coverage | 95% (13 frameworks, 9 dashboard views incl. CISO + multi-cloud, 4 provider scopes, per-cloud PDF/DOCX exports) |
| Documentation | 90% |
| Overall | ~75% |

## Release Criteria

- [x] Backend Build Passes
- [x] Frontend Build Passes
- [x] Unit Tests Pass
- [x] Integration Tests Pass (663 total)
- [x] Lint Passes (ruff, format, mypy, ESLint)
- [x] Security Scan Run (informational CVEs only)
- [x] Docker Build Passes (CI, `1de7bcd`)
- [x] PyInstaller Build Passes (Linux 2026-11-13; packaged `--help` smoke test green on windows-latest)
- [x] One-command installer build (`scripts/build-windows-installer.ps1`) covers venv, frontend, PyInstaller, NSSM, NSIS, smoke test and portable zip — exercised on Windows only through CI
- [x] SonarQube cleanup pass (110+ issues: redundant `response_model`, duplicated literals, unhandled promises, nested ternaries, sort comparators, read-only props)
- [x] GitHub Actions Green (last confirmed `1de7bcd`)
- [x] All 6 required dashboard views present
- [ ] NSIS Build Passes (Windows environment required)
- [ ] Fresh Install / Upgrade / Rollback Passes (Windows required)
- [ ] Playwright E2E at HEAD
- [ ] Release tag `v1.0.0-rc1` pushed
