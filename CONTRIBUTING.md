# Contributing to UniMonitor

Thank you for helping make UniMonitor better. This guide covers everything you need to get started, make changes, and get them merged.

---

## Table of Contents

1. [Development Environment](#development-environment)
2. [Project Structure](#project-structure)
3. [Running Tests](#running-tests)
4. [Code Style](#code-style)
5. [Branch & Commit Conventions](#branch--commit-conventions)
6. [Pull Request Process](#pull-request-process)
7. [Security](#security)
8. [Architecture Decisions](#architecture-decisions)

---

## Development Environment

### Prerequisites

| Tool | Minimum version |
|------|----------------|
| Python | 3.11 |
| Node.js | 20 LTS |
| Docker + Compose | v24 |
| Git | 2.40 |
| pnpm (optional) | 8 |

### Quick start

```bash
# 1. Clone
git clone https://github.com/rajtechlead/UniMonitor.git
cd UniMonitor

# 2. Install dependencies
make install

# 3. Configure environment
cp .env.example .env
# Edit .env — set UNIMONITOR_ENV=development (SQLite is used automatically)

# 4. Run migrations
make migrate

# 5. Start dev servers (two terminals)
make dev-api        # Terminal 1 — FastAPI on :8000
make dev-frontend   # Terminal 2 — Vite on :5173
```

The API has interactive docs at `http://localhost:8000/docs`.

---

## Project Structure

```
unimonitor/           Python package (FastAPI application)
  api/v1/             REST API route handlers
  auth/               JWT + Entra ID OAuth2 authentication
  config.py           Pydantic settings (reads from env / Key Vault)
  core/               Logging, caching, exceptions
  db/                 SQLAlchemy models, migrations, repositories
  grc/                GRC engine: control loader, scoring, AI remediation
  graph/              Microsoft Graph API client + collectors
  reporting/          PDF/Excel/CSV report generators
  secrets/            Secret provider abstraction (Azure KV, AWS SM, local)
  worker/             Celery tasks and beat schedule

controls/             YAML control definitions
  identity/           Entra ID / identity controls
  intune/             Intune device management controls
  defender/           Microsoft Defender controls
  purview/            Microsoft Purview controls
  exchange/           Exchange Online controls
  sharepoint/         SharePoint Online controls
  teams/              Microsoft Teams controls

frontend/             React 18 + TypeScript + Vite SPA
  src/
    components/       Shared UI components
    pages/            Route-level page components
    store/            Zustand state stores
    hooks/            TanStack Query hooks + API client

tests/
  unit/               Fast unit tests (no DB, no network)
  integration/        API integration tests (SQLite in-memory DB)

deploy/
  docker/             Docker Compose + Dockerfiles
  kubernetes/         Kubernetes manifests
  azure/              Azure Container Apps Bicep template
  aws/                AWS ECS Fargate CloudFormation template
  windows/            NSIS Windows installer
```

---

## Running Tests

```bash
make test               # Full suite (74 tests)
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-cov           # With HTML coverage report
```

Tests use `UNIMONITOR_ENV=test` which switches to an in-memory SQLite database — no real infrastructure needed.

**New features must have tests.** The minimum bar is:

- One unit test per public function in `grc/`, `auth/`, `secrets/`
- One integration test per new API endpoint (happy path + at least one error case)

---

## Code Style

### Python

- **Formatter**: `ruff format` (Black-compatible)
- **Linter**: `ruff check` + `mypy`
- **Style**: PEP 8, type annotations on all public functions, `from __future__ import annotations`
- **ORM**: SQLAlchemy 2.0 `Mapped[]` style — no legacy `Column()` syntax
- **Async**: `async def` throughout; never block the event loop
- **Imports**: stdlib → third-party → local; sorted by `ruff`

```bash
make format        # auto-fix formatting
make lint-python   # check for issues
```

### TypeScript / React

- **Formatter**: Prettier
- **Linter**: ESLint with TypeScript plugin
- **Components**: functional components + hooks only; no class components except `ErrorBoundary`
- **State**: Zustand for global state; TanStack Query for server state
- **Styling**: CSS-in-JS (inline styles with CSS variables from theme)

```bash
make lint-frontend
make format-frontend
```

### Naming conventions

| Concept | Convention |
|---------|-----------|
| Python files | `snake_case.py` |
| Python classes | `PascalCase` |
| React components | `PascalCase.tsx` |
| React hooks | `useXxx.ts` |
| API endpoints | `kebab-case` paths, `snake_case` JSON keys |
| YAML control IDs | `CTRL-{SERVICE_PREFIX}-{NUMBER}` (e.g. `CTRL-ENT-001`) |
| DB columns | `snake_case` |

---

## Branch & Commit Conventions

### Branches

```
main                Production-ready code
feat/<short-name>   New features
fix/<short-name>    Bug fixes
chore/<short-name>  Tooling, docs, refactors
```

### Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`  
**Scopes**: `api`, `grc`, `auth`, `db`, `frontend`, `deploy`, `controls`, `worker`

**Examples**:
```
feat(grc): add FrameworkCrosswalk for multi-framework control mapping
fix(api): return 200 for unknown finding state filter values
docs(deploy): add Azure Container Apps Bicep deployment guide
test(grc): add unit tests for scoring engine not_applicable exclusion
```

---

## Pull Request Process

1. Fork the repository and create a branch from `main`
2. Make your changes with tests and documentation
3. Run the full test suite: `make test`
4. Run linting: `make lint`
5. Check for secrets: `make secrets-check`
6. Open a PR against `main` with:
   - **What** changed and **why**
   - Any breaking changes
   - Screenshots for frontend changes
   - Link to related issue (if any)

PRs require:
- All CI checks passing (tests, lint, security scan)
- At least one approving review

**Do not merge your own PRs without review.**

---

## Security

Please read [SECURITY.md](SECURITY.md) before contributing.

Key rules:

1. **No plaintext secrets** anywhere in the codebase — not in source, config, tests, Docker manifests, or migration files
2. **No hardcoded credentials** in test fixtures — use generated values or environment variables
3. Use `make secrets-check` before every PR
4. Report security vulnerabilities privately — see SECURITY.md

---

## Architecture Decisions

### Why FastAPI + SQLAlchemy 2.0?

- Async-first; `asyncpg` driver enables true async PostgreSQL
- Pydantic v2 for request/response validation; aligns with the ORM via `model_config = {"from_attributes": True}`
- OpenAPI schema generated automatically; every new endpoint is instantly documented

### Why Celery + Redis for background tasks?

- Assessment runs and report generation are long-running (minutes); they block the web workers
- Beat scheduler handles recurring tasks (hourly data collection, nightly scoring)
- Redis also serves as the JWT blacklist cache and rate-limit store

### Why YAML controls instead of code?

- Security team and compliance officers can add/modify controls without Python knowledge
- Controls are version-controlled alongside the codebase
- The `evaluate:` block is a sandboxed Python expression — not arbitrary exec

### Why support both PostgreSQL and SQLite?

- SQLite for local development and Windows installer — zero infrastructure
- PostgreSQL for production — required for concurrent multi-tenant workloads
- The `UNIMONITOR_ENV` setting switches automatically

### Adding a new YAML control

1. Add an entry to the appropriate `controls/<service>/security_controls.yaml`
2. The `id` must be unique across all YAML files
3. The `evaluate:` block receives `data` (a dict of Graph API results) and must return one of:
   `"implemented"`, `"partially_implemented"`, `"not_implemented"`, `"not_applicable"`
4. Add `compliance_mapping` entries to cover at least one framework
5. Run `python -c "from unimonitor.grc.control_loader import ControlLoader; ControlLoader().load_all()"` to validate

### Adding a new API endpoint

1. Add the route to the appropriate `unimonitor/api/v1/<resource>.py`
2. Use `Annotated[Any, Depends(get_current_user)]` — **not** `dict`
3. Access user attributes via `current_user.id`, `current_user.role`, etc.
4. Use `require_role("analyst")` or `require_role("admin")` for protected endpoints
5. Add an integration test in `tests/integration/test_api_<resource>.py`
