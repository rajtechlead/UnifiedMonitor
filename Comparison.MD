# Comparison — UniMonitor vs. M365 Sheppard, Vigil365 and Microsoft Zero Trust Assessment

Last updated: 2026-11-18
Compared repositories:

| # | Repository | Purpose |
|---|---|---|
| 1 | [mstanton/m365_sheppard](https://github.com/mstanton/m365_sheppard) | CLI/TUI Microsoft 365 security auditor with a YAML control library |
| 2 | [sameerk27/vigil365](https://github.com/sameerk27/vigil365) | Self-hosted M365 alert dashboard (.NET 8 + React, SQL Server/PostgreSQL) |
| 3 | [microsoft/zerotrustassessment](https://github.com/microsoft/zerotrustassessment) | PowerShell Zero Trust assessment across seven pillars |
| 4 | [rajtechlead/UnifiedMonitor](https://github.com/rajtechlead/UnifiedMonitor) | Multi-cloud security monitoring, GRC and compliance platform |

This document is the factual comparison. The gap register and the disposition of
every gap live in [gap_analysis.md](gap_analysis.md).

---

## 1. One-line positioning

| Repository | What it is | What it is not |
|---|---|---|
| **M365 Sheppard** | A scriptable audit engine with 84 YAML controls, an interactive TUI, and JSON/HTML output | Not a hosted platform: no database, no history, no multi-user UI, Microsoft 365 only |
| **Vigil365** | An operations dashboard: alerts, incidents, trends, licence posture and a triage workflow on a 15-minute collector | Not a GRC tool: no framework mapping, no per-control compliance evidence, Windows/.NET-centric |
| **Zero Trust Assessment** | A read-only PowerShell assessment producing one HTML report across seven pillars | No persistence, no scheduling, no cloud providers outside Microsoft/Azure, no UI |
| **UniMonitor** | A multi-cloud GRC platform: 180 controls, 13 frameworks, assessment runs, AI remediation, reporting and multi-tenant isolation | Weaker operational alerting than Vigil365 and a much smaller Microsoft-native assessment catalogue than the 364-check Zero Trust module |

---

## 2. Architecture

| Dimension | M365 Sheppard | Vigil365 | Zero Trust Assessment | UniMonitor |
|---|---|---|---|---|
| Language / runtime | Python 3.11 | C# / .NET 8 + React 18 | PowerShell 7.6 + React report bundle | Python 3.11 / FastAPI + React 18 |
| Deployment | `uv sync`, CLI/TUI | Windows installer + Windows Service | PowerShell Gallery module | Windows installer, Docker Compose, Kubernetes |
| Database | None (files) | SQL Server Express / PostgreSQL | None (local files) | SQLite / PostgreSQL via SQLAlchemy + Alembic |
| Scheduling | Manual CLI run | BackgroundService, every 15 min | Manual `Invoke-ZtAssessment` | Celery workers + beat |
| Collection auth | Graph app registration (secret) | Graph app-only: secret **or** certificate | Delegated or app-only certificate | Graph app registration: certificate (default) or secret; AWS role; Google service account |
| Cloud coverage | Microsoft 365 | Microsoft 365 | Microsoft 365, Azure, Defender for Cloud | Microsoft 365, AWS, GCP, Google Workspace |
| Multi-tenancy | Config-file tenants, parallel runs | MSP edition (per-client isolation, rollup) | One tenant per run | Tenant table with per-tenant isolation |
| Users / RBAC | None | Admin / Analyst / Viewer, invitations | None | Admin / Analyst / Viewer JWT auth + Microsoft SSO |
| Persistence of results | JSON/HTML per run | SQL, full history | HTML/JSON per run | Assessment runs, findings, history, evidence, audit log |

---

## 3. Capability matrix

Legend: ✅ first-class · 🟡 partial / implicit · ❌ absent · **➡** merged into UniMonitor in this change

| Capability | Sheppard | Vigil365 | ZT Assessment | UniMonitor (before) | UniMonitor (now) |
|---|---|---|---|---|---|
| Control / assessment catalogue | 84 controls, 9 categories | Metric + activity + anomaly alert policies | 364 assessment checks, 7 pillars | 180 controls, 13 categories | 180 + Zero Trust pillar view **➡** |
| Compliance frameworks | CIS/NIST/ISO/CoreView tags per control | ❌ | Maps to ZT pillars | 13 frameworks (ISO, NIST, CIS, SOC 2, HIPAA, PCI, CMMC, …) | unchanged |
| Executive / security dashboards | TUI dashboard only | 16 operational pages | Static HTML report | 13 pages incl. Executive, CISO, Risk, SOC, Audit, Clouds | + Zero Trust page **➡** |
| Assessment history / trends | ❌ | ✅ posture snapshots | ❌ | ✅ score trends | unchanged |
| Alert lifecycle (ack / snooze / assign / resolve) | ❌ | ✅ policies + alerts | ❌ | ❌ (findings had only compliance state) | ✅ finding triage **➡** |
| Notification channels | ❌ | Teams, email, webhook, digests | ❌ | SMTP, Teams, Slack, generic webhook, daily/weekly digest | unchanged |
| Remediation prioritisation (ROI) | ✅ severity ÷ complexity | ❌ | ❌ | ❌ | ✅ `/findings/priority` **➡** |
| AI remediation guidance | ❌ | ❌ | ❌ | ✅ Azure OpenAI + rule-based fallback | unchanged |
| HTML report | ✅ | ❌ (scheduled CSV digest) | ✅ | ❌ | ✅ **➡** |
| Other report formats | JSON | CSV attachment | JSON (workshop) | PDF, DOCX, Excel, CSV, JSON | + HTML |
| Entity investigation timeline | ❌ | ✅ merged user/device timeline | ❌ | ❌ | ✅ per-finding timeline **➡** |
| Global search palette | TUI filter | ✅ Ctrl+K | ❌ | Findings search only | ✅ Ctrl+K across pages, findings, alerts, controls **➡** |
| Licence posture / Copilot / Power Platform pages | ❌ (biz controls) | ✅ | ❌ | Copilot controls, no licence page | ✅ licence posture **➡**; Copilot/Power Platform controls only |
| Service health page | ❌ | ✅ | 🟡 via assessments | ❌ | ✅ **➡** |
| Tamper-evident audit log | ❌ | ✅ SHA-256 hash chain | ❌ | Audit log table + Audit page, no hash chain | ✅ hash chain + verify badge **➡** |
| Scheduled collection with manual override | Manual CLI run | ✅ 15-min service | Manual run | Celery beat for assessments; tenants without an assessment were skipped | ✅ interval configurable, default assessment auto-created, manual runs **➡** |
| Secret storage | Env vars | DPAPI / config | Certificate store | Key Vault / AWS Secrets Manager / encrypted local vault | unchanged |
| Guided first-run setup | Config file | Windows wizard | PowerShell prompts | Web `/setup` wizard (cert default, AWS role, shared Google account) | unchanged |
| Microsoft sign-in for the web UI | n/a | ✅ MSAL | n/a | 🟡 broken (wrong route, tokens discarded, no redirect URI) | ✅ fixed **➡** |
| Report generation actually ran | ✅ | ✅ | ✅ | 🟡 worker awaited a sync call, so every report failed | ✅ fixed **➡** |
| Terminal UI | ✅ | ❌ | ❌ | ❌ | not ported (see gap_analysis) |
| Extensibility model | YAML `evaluate()` (AST-checked) | C# policy classes | PowerShell test files | YAML `evaluate()` (AST-checked) | unchanged |

---

## 4. Notes per repository

### 4.1 M365 Sheppard

- **Control model**: flat YAML per control (`control_id`, `metadata.severity`, `check.evaluation`
  Python executed in a restricted namespace). 84 controls across `app`, `atp`, `biz`, `dev`,
  `dgv`, `iam`, `mon`, `ops`, `osint`.
- **ROI**: `core/scoring.py:prioritize_findings` ranks by severity ÷ remediation complexity and the
  CLI prints "Top Priorities (by ROI)".
- **Output**: `output/html_renderer.py`, `output/json_renderer.py`.
- **Interface**: `sentinel` CLI plus a Textual TUI with dashboard, control browser, live audit run
  and finding triage.
- **Overlap with UniMonitor**: same Graph read-only approach, same `evaluate(data)` YAML concept,
  same severity vocabulary. UniMonitor has more controls (180 vs 84) and frameworks but had no
  ROI ranking and no HTML output.

### 4.2 Vigil365

- **Backend**: ASP.NET Core 8 minimal API, EF Core with per-engine migrations, BackgroundService
  collector every 15 minutes, `AlertPolicy` model with metric/activity/anomaly rules, alert states
  (acknowledged / snoozed / resolved / assigned / notes).
- **Frontend**: 16 pages — Overview, Identity, Devices, Email, Incidents, Compliance, Licence
  Posture, Copilot, Power Platform, Alert Center, Service Health, Connectivity, Licenses & Users,
  Conditional Access, Tenant Activity, Sign-in Locations.
- **Enterprise features**: Teams/SMTP/webhook notifications with digests, scheduled executive
  digest with CSV, trends, recommendations hub, entity investigation timeline, RBAC with
  invitations, SHA-256 hash-chained audit trail, Ctrl+K search, CSV export, saved filters.
- **Overlap with UniMonitor**: both are self-hosted dashboards over Graph; Vigil365 is
  operations-first, UniMonitor is GRC/compliance-first. UniMonitor already has the stronger
  framework, multi-cloud and reporting story; Vigil365 had the stronger triage workflow.
- **Not portable without changing the product**: SQL Server/PostgreSQL dual-provider EF model,
  Windows Service packaging, MSAL hosted UI, and its page-per-service dashboard taxonomy.

### 4.3 Microsoft Zero Trust Assessment

- **Scope**: seven pillars — Identity, Devices, Network, Data, Infrastructure, SecOps, AI.
- **Catalogue**: 364 `Test-Assessment.*.ps1` files under `src/powershell`, each with Pester tests.
- **Output**: `ZeroTrustAssessmentReport.html` (plus classic), `zt-export/ZeroTrustWorkshop.json`,
  telemetry with opt-out.
- **Overlap with UniMonitor**: UniMonitor controls *already* carry a `zero_trust` compliance
  mapping (`identity.verify_explicitly`, `endpoints.threat_protection`, …), so the pillar model can
  be expressed over existing data rather than importing a second control library.
- **Deliberate difference**: the 364 checks are PowerShell cmdlets against Microsoft-only
  endpoints. Porting them one-for-one would duplicate control logic and contradict UniMonitor's
  multi-cloud, YAML-based catalogue.

### 4.4 UniMonitor (as found)

- 180 controls in 13 categories, 13 frameworks, Zero Trust mappings already present in every
  control file.
- 5 report generators, 13 dashboard pages, Celery reporting/notification/assessment tasks.
- Two defects found while comparing: the Findings page sent `limit`/`offset` and read fields the
  API never returned, and the worker awaited a synchronous generator, so report builds failed.

---

## 5. What this change merged

| Source | Capability | Where it landed |
|---|---|---|
| Sheppard | ROI remediation ranking | `unimonitor/api/v1/findings.py` `/findings/priority`, `grc/control_loader.py` (`impact`, `effort`), Findings page "Fix first" |
| Sheppard + ZT | Single-file HTML report | `unimonitor/reporting/html_generator.py`, report API, worker, Reports page |
| ZT Assessment | Seven-pillar coverage model | `unimonitor/grc/pillars.py`, `GET /dashboard/zero-trust`, `ZeroTrustPage` |
| Vigil365 | Acknowledge / snooze / assign / resolve | `Finding.triage_status/assignee_id/snoozed_until`, `POST /findings/{id}/triage`, migration `002` |
| Vigil365 | Entity investigation timeline | `GET /findings/{id}/timeline`, Findings detail panel |
| Vigil365 | Operational queue view | Findings page triage column and filters |
| Vigil365 | Metric/activity/anomaly alert policies and alert objects | `AlertPolicy`/`Alert`, `alerts/engine.py`, `/alerts`, Alert Center page |
| Vigil365 | Licence posture and service health | `/monitoring/licensing`, `/monitoring/service-health`, two pages |
| Vigil365 | Ctrl+K global search | `/search`, `SearchPalette` |
| Vigil365 | Hash-chained audit trail | `core/audit.py`, migration 003, Audit page badge |
| ZT Assessment | 364 PowerShell checks with per-result remediation | Import JSON, ZT Assessment page, runner script bundled |
| Vigil365 + ZT Assessment | Coverage extended to AWS, GCP, Google Workspace | `/zerotrust/run` + remediation on all cloud controls |
| ZT Assessment | Remediation guidance on every result | Cloud controls carry summary + steps; import keeps Microsoft's |
| Vigil365 | Scheduled collection | `collect_all_tenants` beat task, Data Collection page |

Everything else in UniMonitor — the setup wizard, dashboards, assessments, frameworks, reporting,
secret management and multi-cloud collectors — is unchanged, by request.

---

## 6. Where each project still leads

| Project | Still ahead of UniMonitor | Tracked as |
|---|---|---|
| M365 Sheppard | Interactive TUI for air-gapped triage; OSINT threat-intel controls | GAP-13, GAP-14 |
| Vigil365 | Saved filter presets; per-staff tenant scoping | GAP-11, GAP-17 |
| ZT Assessment | 364 Microsoft-authored checks with per-check Pester tests; workshop export; telemetry | GAP-12 |
| UniMonitor | Multi-cloud coverage, 13 frameworks, AI remediation, certificate-first onboarding, per-tenant isolation, report breadth | — |

The disposition of each gap, including why it was not merged, is in
[gap_analysis.md](gap_analysis.md).
