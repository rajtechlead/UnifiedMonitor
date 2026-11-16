# SESSION_STATE.md

Project: UnifiedMonitor
Repository: https://github.com/rajtechlead/UnifiedMonitor
Last Updated: 2026-11-16 UTC

## Current Session Commits

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
- Fixed 157 ruff + 2 mypy errors that existed on HEAD (CI would have been red): import sorting,
  line length, unused imports/variables, `print` in CLI scripts, dummy-credential false positives.

## Completed Previously (Phases 1–5, unchanged)

- Phase 1 Repository Recovery ✅ (PROJECT_AUDIT.md still deferred, L-001)
- Phase 2 Stabilisation ✅ — all Critical/High resolved (see GAP_REGISTER.md)
- Phase 3 Architecture ✅ — unified secrets framework done; setup wizard script exists
  (`scripts/setup_wizard.py`, wired into `unimonitor/cli.py setup`)
- Phase 4 Build Validation ✅ — tests, lint, mypy, ESLint, Playwright, Docker (CI)
- Phase 5 Packaging 🟡 — Docker ✅ CI, PyInstaller Linux ✅, NSIS/Windows ⬜
- Phase 6 Release 🟡 — all four production guides written; release tag not pushed

## In Progress

None.

## Blocking Issues

1. **NSIS / Windows validation** — requires a Windows Server 2019+ host. Not possible in this
   Linux cloud workspace. Covers P5-003…P5-006.
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
5. `ecdsa` / `python-jose` CVEs — decide between accepting the risk and migrating to `pyjwt`.
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
| Python tests | ✅ 473/473 | 47s, 7 warnings (AsyncMock never-awaited in mocks) |
| Control library | ✅ 158 controls | 18 YAML files, all framework keys resolve |
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

## Resume Instructions

1. Read `SECTION_STATE.md`… i.e. this file, `NEXT_ACTIONS.md`, `GAP_REGISTER.md`,
   `BUILD_STATUS.md`, `TECHNOLOGY_BASELINE.md`, `PROJECT_REQUIREMENTS.md`.
2. Country-free first action: push the release tag if the session allows it.
3. Then the Windows validation block, or the control-library expansion if no Windows host exists.
4. Do NOT re-audit completed work. Do NOT regenerate the Phase 6 guides.

## Usage Limit Procedure

At ~95% context: update all four trackers, commit, push, stop. Never leave untracked work.
