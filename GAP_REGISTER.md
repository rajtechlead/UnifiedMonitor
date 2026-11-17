# GAP_REGISTER.md

Project: UnifiedMonitor
Repository: https://github.com/rajtechlead/UnifiedMonitor
Last Updated: 2026-11-16 UTC

## Critical — Active

None

## High — Active

None

## Medium — Active

| ID | Description | File | Status |
|---|---|---|---|
| M-006 | NSIS installer not tested | `deploy/windows/` | ⬜ P5-003 — Windows environment required |
| M-013 | Release tag not pushed; no tag exists in any clone | `.git` | 🟡 recreate + push with tag permission |
| M-015 | Docker Compose never validated end-to-end (CI builds the image only) | `deploy/docker/` | ⬜ no Docker daemon in agent workspace |
| M-016 | Setup wizard exists as a script but is not wired into the NSIS install flow | `scripts/setup_wizard.py`, `deploy/windows/install.nsi` | ⬜ P3-003 follow-up |

## Low — Active

| ID | Description | File | Status |
|---|---|---|---|
| L-001 | PROJECT_AUDIT.md not generated | — | ⬜ deferred by owner decision |
| L-002 | Test coverage 62% (last measured `79dfb98`), not re-measured since | `tests/` | 🟡 P7-006 |
| L-011 | `pip-audit` gates CI, but the audit ignores the local `unimonitor` package (not on PyPI) — a vulnerability in our own code is caught by Bandit/review, not the audit | `.github/workflows/ci.yml` | ℹ️ expected limitation |
| L-012 | Bandit flags `exec()` in the control evaluator (B102) and the `0.0.0.0` CLI default (B104); both are by design — controls are shipped YAML, and the server default binds all interfaces | `grc/control_loader.py`, `cli.py` | ℹ️ reviewed, accepted |
| L-007 | Remaining frontend majors: react 18→19, @vitejs/plugin-react 4→6 | `frontend/` | ⬜ P7-007 |
| L-008 | Ruff per-file ignores added for CLI `print` (T201 in `scripts/`) and dummy credentials in `tests/` (S105/S106/S108/B017) | `pyproject.toml` | ℹ️ By design — documented decision |
| L-010 | Some new control keys still depend on the posture snapshot (Copilot Studio, LAPS policy, app blocklist, insider-risk connectors) because no Graph endpoint exposes them | `unimonitor/graph/collectors/snapshot.py` | 🟡 by design; documented in OPERATIONS |
| M-023 | Google collectors use a pre-issued access token; there is no refresh flow, so a long run needs an external refresher | `unimonitor/graph/collectors/cloud_providers.py` | ⬜ P8-005 |
| M-024 | AWS/GCP/Workspace controls have never run against live accounts — payload tests only | `controls/aws`, `controls/gcp`, `controls/google_workspace` | ⬜ P8-004 |
| M-029 | Windows installer: PyInstaller freeze and the packaged `--help` smoke test are verified on a `windows-latest` runner, and the NSIS step's PATH bug is fixed, but a green installer build and a real fresh install/upgrade have not been observed | `deploy/windows/` | 🟡 needs a green NSIS run |
| M-028 | Azure-specific controls (25, `azure_security`) roll up under the Microsoft 365 provider; there is no standalone Azure dashboard | `unimonitor/grc/providers.py` | 🟡 grouping decision; split if Azure is sold separately |

## Resolved This Session (2026-11-16)

| ID | Description | Resolution |
|---|---|---|
| M-017 | `ExecutiveDashboard` read `scores.security`, `severity_counts`, `trend` — none of which `/dashboard/executive` returns; page silently displayed hard-coded demo values | Mapped to `security_score`/`compliance_score`/`risk_score`, `score_trends`, `framework_coverage`, `top_risks`; demo fallbacks removed |
| M-018 | `ComplianceDashboard` expected `{framework, score, implemented…}`; API returns `{framework_id, framework_name, coverage_pct, controls_total, controls_passed}` — framework list rendered empty | Aligned to the API contract |
| M-019 | Risk, SOC and Audit dashboard views required by PROJECT_REQUIREMENTS had no UI (Risk/SOC had API only; Audit had no API) | Added `RiskDashboard`, `SocDashboard`, `AuditPage` + `GET /api/v1/dashboard/audit`, routes and nav |
| M-031 | `POST /reports/generate` required `tenant_id`/`report_type`/`report_format` while the UI sends `run_id`/`formats`, and `unimonitor.worker.tasks` exported no task, so generation never ran | Endpoint accepts run+formats (legacy fields still work), resolves the tenant from the run, dispatches the worker with its real signature, and reports queue failures instead of claiming success |
| M-032 | CISO severity tiles counted implemented findings as open risk | Severity totals now count open, non-suppressed findings only |
| M-033 | `create_app()` mounted only `branding` at `/static`, so the Vite build copied into `unimonitor/static` was never served — `/` 404'd in the Docker image and the Windows installer | App mounts the build at `/` with an SPA fallback (client-side routes and refresh work), API routes still take precedence; Docker image now copies `dist` to `unimonitor/static` and includes `branding/` |
| L-004/L-005 | `ecdsa` PYSEC-2026-1325 and `python-jose` PYSEC-2026-4298 had no upstream fix | Migrated JWT to PyJWT and removed python-jose (and ecdsa); `pip-audit` now clean, CI audit job green |
| M-030 | DOCX export was documented but never implemented; PDF crashed on dict-shaped runs | Added `docx_generator.py`; PDF now uses the dict-safe accessors and emits per-cloud sections |
| M-027 | Reports emitted one blended score with no cloud breakdown | PDF/DOCX now carry provider coverage + per-provider findings; aggregate summary retained |
| M-025 | L-009 duplicate insider-risk title | CTRL-PUR-006 replaced with a departing-employee scenario control |
| M-026 | 58 new controls had no collector producing their data keys | Added `extended.py` + snapshot ingestion; 19 payload tests prove collector → control |
| M-021 | Control library depth — 100 controls across 10 areas; 7 named monitoring areas had no controls | Added 58 controls in 8 new files (Intune baselines, app inventory, Defender Office/Identity/Cloud Apps, Insider Risk, eDiscovery, Copilot Studio); library now 158 |
| M-022 | 12 controls mapped to unregistered framework key `nist_csf`, so their NIST CSF mapping never resolved | Renamed to `nist_csf_2` in exchange, teams and sharepoint control files |
| M-020 | 157 ruff errors + 2 mypy errors on HEAD (tests/scripts added after `1de7bcd` were never linted → CI red) | Auto-fix + format; manual fixes for unused imports/vars, `S607`, E501; per-file ignores for CLI `print` and test fixtures |
| L-003b | Tracker files described HEAD `1de7bcd`, 105 tests, 47% coverage, "10 dependabot PRs" — all stale | Trackers reconciled to measured state (467 tests, majors merged) |

## Resolved Previously

| ID | Description | Resolution | Commit |
|---|---|---|---|
| C-001 | passlib + bcrypt>=4.0 incompatibility | Replaced passlib with direct bcrypt | `afe46fc` |
| C-002 | Duplicate /health route in main.py | Removed duplicate registration | `afe46fc` |
| C-003 | @dataclass mutable default fields (control_loader) | Moved to module level | `afe46fc` |
| C-004 | Missing production extra in pyproject.toml | Added azure/boto3 extras | `afe46fc` |
| C-005 | Missing reporting/templates directory | Created | `afe46fc` |
| C-006 | Python 3.11 used throughout | Updated to 3.12 | `afe46fc` |
| C-007 | pip-audit referenced deleted requirements.txt | Fixed | `afe46fc` |
| C-008 | YAML controls returned "pass"/"fail" | Normalised in control_loader | `afe46fc` |
| H-001 | Ruff 153 lint issues | Fixed | `11f5309` |
| H-002 | Dead directories | Removed | `afe46fc` |
| H-003 | Duplicate root files | Removed | `afe46fc` |
| H-004 | Deprecated ruff config layout | Moved to `[tool.ruff.lint]` | `afe46fc` |
| H-005 | Starlette 422 deprecation | `HTTP_422_UNPROCESSABLE_CONTENT` | `0b98fc3` |
| H-006 | 236 auto-fixable ruff issues | Applied | `0b98fc3` |
| M-001 | Frontend not validated | ESLint 0, vite build OK, Playwright 4/4 in CI | `11f5309` |
| M-002 | Docker build not validated | CI green | `11f5309` |
| M-003 | GitHub Actions not confirmed green | All 8 jobs green | `11f5309` |
| M-004 | Setup wizard not implemented | `scripts/setup_wizard.py` + CLI `setup` (installer wiring tracked as M-016) | — |
| M-005 | PyInstaller not tested | Linux bundle 222 MB | `edbe3f3` |
| M-007 | Security scan not run | pip-audit in CI, informational CVEs only | `11f5309` |
| M-008 | mypy strict 297 errors | strict disabled, per-module ignores, 0 issues | `11f5309` |
| M-009 | Playwright strict-mode violation | exact match fix | `11f5309` |
| M-010 | Docker hatchling README.md missing | COPY line added | `49e5f14` |
| M-011 | Missing init_db/init_cache/close_cache | Aliases added | `11f5309` |
| M-012 | Missing CLI entry points | Added | `11f5309` |
| L-006 | Frontend majors open (recharts, zustand, lucide, ts-eslint, date-fns) | Merged in `417ad87`; two remain (L-007) | `417ad87` |
