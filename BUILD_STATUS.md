# BUILD_STATUS.md

Project: UnifiedMonitor
Repository: https://github.com/rajtechlead/UnifiedMonitor
Last Updated: 2026-11-16 UTC

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

## Backend Validation (measured 2026-11-16)

| Check | Status | Notes |
|---|---|---|
| Dependency installation | ✅ | `pip install -e ".[dev,production]"` clean |
| Test suite | ✅ 518/518 | 73s; 7 warnings (AsyncMock coroutine never awaited inside mocks) |
| Control library | ✅ 180 controls | 21 YAML files; unique ids, valid severities, all framework keys registered |
| Multi-cloud collectors | ✅ unit-tested | AWS (boto3), GCP + Workspace (REST); no live accounts exercised |
| Multi-cloud dashboards | ✅ API + UI | aggregate `/clouds` and per-provider `/clouds/{id}`; React `tsc` + vite build clean |
| Ruff check | ✅ CLEAN | 0 errors — was 157 on HEAD before this session |
| Ruff format | ✅ CLEAN | 132 files |
| mypy | ✅ CLEAN | 87 source files |
| SQLite validation | ✅ | in-memory SQLite for all tests |
| PostgreSQL validation | ⬜ | not exercised this session |
| Health endpoint | ✅ | covered by integration tests |
| Entra ID OAuth2 | ✅ | mocked in tests; live tenant not exercised |
| Secrets framework | ✅ | Azure KV / AWS SM / local store covered by tests |
| Redis / Celery | ⬜ | health check code present; no broker available here |

## Testing Status

| Test Type | Status | Count | Notes |
|---|---|---|---|
| Unit tests | ✅ PASS | 452 | across 24 files |
| Integration tests | ✅ PASS | 66 | health, e2e journeys, dashboard + cloud views |
| New this session | ✅ | +5 | `tests/integration/test_dashboard_views.py` |
| Coverage | 🟡 62% | — | last measured at `79dfb98`; not re-measured |
| UI / Playwright | ⬜ NOT RUN | 4 tests exist | browsers not installed here; CI job `playwright-e2e` |
| Installer tests | ⬜ | — | Phase 5, Windows required |

## Frontend Validation (measured 2026-11-16)

| Check | Status | Notes |
|---|---|---|
| npm ci | ✅ | clean install from lockfile |
| ESLint | ✅ CLEAN | 0 warnings, `--max-warnings 0` |
| TypeScript (`tsc`) | ✅ | no type errors |
| Vite production build | ✅ | 2613 modules, 5.0s; charts chunk 437 kB (gzip 124 kB) |
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
| ecdsa | 0.19.2 | PYSEC-2026-1325 | No (latest affected) |
| python-jose | 3.5.0 | PYSEC-2026-4298 | No (latest affected) |

Action: security debt recorded (L-004, L-005); decide accept-vs-migrate to `pyjwt` (P7-008).

## Production Readiness Score (revised 2026-11-16)

| Area | Readiness |
|---|---|
| Backend stability | 88% |
| Test coverage | 62% (measured at `79dfb98`) |
| Security | 58% (two unfixable upstream CVEs, no live-tenant auth test) |
| Deployment | 70% (Docker CI green, Linux PyInstaller green, Windows pending) |
| Requirements coverage | 93% (13 frameworks, 8 dashboard views incl. multi-cloud, 7 monitoring areas, 4 provider scopes) |
| Documentation | 90% |
| Overall | ~75% |

## Release Criteria

- [x] Backend Build Passes
- [x] Frontend Build Passes
- [x] Unit Tests Pass (452)
- [x] Integration Tests Pass (66)
- [x] Lint Passes (ruff, format, mypy, ESLint)
- [x] Security Scan Run (informational CVEs only)
- [x] Docker Build Passes (CI, `1de7bcd`)
- [x] PyInstaller Build Passes (Linux, 2026-11-13)
- [x] GitHub Actions Green (last confirmed `1de7bcd`)
- [x] All 6 required dashboard views present
- [ ] NSIS Build Passes (Windows environment required)
- [ ] Fresh Install / Upgrade / Rollback Passes (Windows required)
- [ ] Playwright E2E at HEAD
- [ ] Release tag `v1.0.0-rc1` pushed
