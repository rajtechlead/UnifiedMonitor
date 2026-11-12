# UniMonitor Architecture

**Version:** 1.0  
**Updated:** 2026-11-06

---

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     React 18 Frontend                        │
│         TypeScript · Vite · TanStack Query v5                │
│         Zustand · Recharts · lucide-react                    │
│                                                              │
│  Dashboards: Executive · Security · Compliance · Findings    │
│              Assessments · Reports · Settings                │
└───────────────────────────┬──────────────────────────────────┘
                            │  REST (JSON) + SSE
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│                   Python 3.11 · Pydantic v2                  │
│                                                              │
│  ┌──────────┐  ┌────────────┐  ┌────────────────────────┐   │
│  │ Auth     │  │ Graph API  │  │    GRC Engine          │   │
│  │ MSAL/JWT │  │ Client     │  │  13 frameworks         │   │
│  │ Entra ID │  │ Rate-limit │  │  YAML controls         │   │
│  └──────────┘  └────────────┘  │  AI remediation        │   │
│                                └────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            Secret Provider Abstraction               │   │
│  │  Azure Key Vault │ AWS Secrets Manager │ Local Vault  │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            OpenTelemetry + structlog                 │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────┬───────────────────────────┬──────────────────────┘
            │                           │
  ┌─────────▼──────────┐    ┌───────────▼──────────┐
  │  PostgreSQL/SQLite │    │  Redis + Celery Beat  │
  │  SQLAlchemy async  │    │  Async task workers   │
  └────────────────────┘    └──────────────────────┘
            │
  ┌─────────▼──────────┐
  │  Microsoft Graph   │
  │  API v1.0          │
  │  Entra ID, Intune, │
  │  Defender, Exchange│
  │  SharePoint, Teams │
  └────────────────────┘
```

---

## Component Descriptions

### Frontend

- **Framework:** React 18 with TypeScript, built by Vite
- **State:** Zustand with persist middleware for UI preferences
- **Server state:** TanStack Query v5 (React Query) with stale-while-revalidate
- **Charts:** Recharts — RadialBar, Bar, Line, Radar chart types
- **Icons:** lucide-react
- **Design system:** CSS custom properties on `:root`, dark-mode via `[data-theme="dark"]`
- **Auth:** JWT access + refresh tokens stored in memory + secure cookie

### API Layer (FastAPI)

- **Versioned routes** under `/api/v1/`
- **Authentication:** Entra ID OAuth2 (MSAL) + local JWT fallback
- **Middleware:** CORS, GZip, request ID injection, OpenTelemetry tracing
- **Exception handlers:** 422 (validation), 401/403, 500 with structured JSON
- **Lifespan:** async startup runs DB connection warm-up and schedules first heartbeat

### Database

| Setting | Value |
|---|---|
| ORM | SQLAlchemy 2.0 async (`Mapped[]` types) |
| Primary DB | PostgreSQL via asyncpg |
| Dev/Offline DB | SQLite via aiosqlite |
| Migrations | Alembic (auto-generate from models) |
| Connection pool | 20 + 10 overflow (PostgreSQL); WAL mode (SQLite) |

Key models: `Tenant`, `User`, `Assessment`, `Finding`, `Report`, `ScheduledTask`

### GRC Engine

```
YAML Controls ──► ControlLoader ──► AssessmentEngine
                                           │
                               ┌───────────┼───────────┐
                               ▼           ▼           ▼
                         Graph API    Evaluate()   AI Remediation
                         Collectors   functions    (Azure OpenAI)
                               │           │
                               └─────┬─────┘
                                     ▼
                               Scoring Engine
                               (security / compliance / risk scores)
                                     │
                                     ▼
                            DB: Finding records
```

**Supported frameworks (13):**
NIST CSF 2.0, ISO/IEC 27001:2022, CIS Controls v8, SOC 2, HIPAA,
PCI-DSS v4, NIST SP 800-53, NIST SP 800-171, CMMC 2.0, GDPR,
Microsoft Zero Trust, Azure Security Benchmark, M365 Security Baseline

**Severity weights:** CRITICAL=10, HIGH=8, MEDIUM=5, LOW=3, INFORMATIONAL=1

### Secret Management

See [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md) for full details.

**Key principle:** The database stores only *references* (e.g.,
`azure_key_vault://unimonitor/tenants/abc/client-secret`), never values.
The `SecretResolver` resolves references at runtime with TTL caching.

### Microsoft Graph API Client

- **Async HTTP** via httpx
- **Authentication:** `azure-identity` DefaultAzureCredential + per-tenant MSAL
- **Rate limiting:** Token bucket (configurable RPS, default 5 req/s)
- **Retry:** tenacity with exponential backoff on 429/503
- **Pagination:** automatic `@odata.nextLink` following
- **Cache:** Redis (configurable TTL per endpoint)

### Celery Workers

- **Broker + Result:** Redis
- **Beat scheduler:** periodic tasks (nightly assessments, rotation checks)
- **Tasks:** `run_assessment`, `generate_report`, `collect_data`, `check_secret_rotation`
- **Async bridge:** `_run_async()` helper bridges sync Celery ↔ async SQLAlchemy

---

## Directory Structure

```
UniMonitor/
├── unimonitor/              # Core Python package
│   ├── api/v1/              # FastAPI routers
│   ├── core/                # Logging, telemetry, exceptions
│   ├── db/                  # Models, session, migrations
│   ├── grc/                 # GRC engine, scoring, AI remediation
│   ├── graph/               # Microsoft Graph API client + collectors
│   ├── reporting/           # PDF, DOCX, JSON, CSV report generators
│   ├── secrets/             # Secret provider abstraction
│   ├── tasks/               # Celery task definitions
│   ├── cli.py               # CLI entry point (unimonitor command)
│   ├── config.py            # Pydantic settings
│   └── main.py              # FastAPI app factory
├── controls/                # GRC control YAML definitions
│   ├── identity/
│   ├── devices/
│   ├── data_protection/
│   └── ...
├── frontend/                # React 18 TypeScript app
│   └── src/pages/           # Dashboard pages
├── deploy/
│   ├── docker/              # Docker Compose
│   └── kubernetes/          # K8s manifests + External Secrets
├── installer/               # Windows MSI (NSIS + PyInstaller)
├── scripts/                 # setup.py, setup_wizard.py, smoke_test.py
├── tests/                   # pytest suite
└── docs/                    # Architecture, deployment, security docs
```

---

## Data Flow: Assessment Run

```
1. API POST /api/v1/assessments/{id}/run
         │
2. Celery task: run_assessment(assessment_id, tenant_id, framework_ids)
         │
3. ControlLoader.load_controls_for_frameworks(framework_ids)
         │
4. For each collector (EntraID, Intune, Defender, ...):
     GraphClient.collect_data(tenant_id)  → raw data dict
         │
5. For each control:
     control.evaluate(collected_data)     → state string
     AIRemediationEngine.generate(...)    → 9-field remediation dict
         │
6. ScoringEngine.calculate_scores(findings)
     → security_score, compliance_score, risk_score
         │
7. DB: Persist Finding records + update Assessment.scores
         │
8. SSE: Push progress events to frontend
```

---

## Security Design

| Concern | Approach |
|---|---|
| Secret storage | Reference-only in DB; values in vault (Azure KV / AWS SM / Local) |
| Authentication | Entra ID OAuth2 (PKCE) + local JWT (argon2 hashed passwords) |
| Authorization | Role-based: admin, analyst, auditor, viewer |
| Transport | TLS 1.2+ enforced; HSTS in production |
| Input validation | Pydantic v2 strict models on all API inputs |
| SQL injection | SQLAlchemy parameterized queries only |
| Audit trail | structlog → OTEL log exporter; secret audit log separate |
| Container | Non-root user (uid 10001) in Docker |
| Kubernetes | External Secrets Operator; no raw `Secret` with stringData |
