# UniMonitor — Developer Makefile
# ================================
# Common development, test, lint, migrate, and deploy targets.
#
# Prerequisites:
#   - Python 3.11+ with uv or pip
#   - Node.js 20+ with pnpm or npm
#   - Docker + Docker Compose
#   - PostgreSQL client (psql) for db-shell
#
# Quickstart:
#   make install   — install all dependencies
#   make dev       — start backend + frontend in development mode
#   make test      — run full test suite
#   make lint      — lint + type-check all code

.PHONY: help install dev dev-api dev-frontend test test-unit test-integration \
        lint lint-python lint-frontend format migrate migrate-create db-shell \
        docker docker-build docker-up docker-down docker-logs \
        clean clean-pyc clean-node secrets-check pre-commit

# ─────────────────────────────────────────────────────────────────────────────
# Default target
# ─────────────────────────────────────────────────────────────────────────────
.DEFAULT_GOAL := help

PYTHON  := python3
UV      := uv
PIP     := pip
PNPM    := pnpm
NPM     := npm
DOCKER  := docker
COMPOSE := docker compose

# Detect whether uv is installed; fall back to pip
HAS_UV := $(shell command -v uv 2>/dev/null)

help: ## Show this help message
	@echo ""
	@echo "  UniMonitor — Developer Makefile"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Install
# ─────────────────────────────────────────────────────────────────────────────
install: install-python install-frontend ## Install all dependencies

install-python: ## Install Python dependencies
ifdef HAS_UV
	$(UV) pip install -e ".[dev]"
else
	$(PIP) install -e ".[dev]"
endif

install-frontend: ## Install frontend Node dependencies
	@if command -v pnpm >/dev/null 2>&1; then \
	  cd frontend && pnpm install; \
	else \
	  cd frontend && npm install; \
	fi

# ─────────────────────────────────────────────────────────────────────────────
# Development servers
# ─────────────────────────────────────────────────────────────────────────────
dev: ## Start both API and frontend in development mode (requires tmux or two terminals)
	@echo "Starting API on http://localhost:8000 and frontend on http://localhost:5173"
	@echo "Run 'make dev-api' and 'make dev-frontend' in separate terminals."
	@$(MAKE) -j2 dev-api dev-frontend

dev-api: ## Start the FastAPI development server with hot-reload
	$(PYTHON) -m uvicorn unimonitor.app:app \
	  --reload \
	  --host 0.0.0.0 \
	  --port 8000 \
	  --log-level info

dev-frontend: ## Start the Vite frontend development server
	@if command -v pnpm >/dev/null 2>&1; then \
	  cd frontend && pnpm dev; \
	else \
	  cd frontend && npm run dev; \
	fi

dev-worker: ## Start Celery worker in development mode
	celery -A unimonitor.worker.celery_app worker \
	  --loglevel=debug \
	  --concurrency=2

dev-beat: ## Start Celery beat scheduler in development mode
	celery -A unimonitor.worker.celery_app beat \
	  --loglevel=info

# ─────────────────────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────────────────────
test: ## Run the full test suite
	$(PYTHON) -m pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	$(PYTHON) -m pytest tests/unit/ -v --tb=short

test-integration: ## Run integration tests only
	$(PYTHON) -m pytest tests/integration/ -v --tb=short

test-cov: ## Run tests with coverage report
	$(PYTHON) -m pytest tests/ \
	  --cov=unimonitor \
	  --cov-report=term-missing \
	  --cov-report=html:htmlcov \
	  --tb=short
	@echo "Coverage report: htmlcov/index.html"

test-watch: ## Run tests in watch mode (requires pytest-watch)
	$(PYTHON) -m pytest_watch tests/ -- -v --tb=short

# ─────────────────────────────────────────────────────────────────────────────
# Lint & Format
# ─────────────────────────────────────────────────────────────────────────────
lint: lint-python lint-frontend ## Lint all code

lint-python: ## Lint Python code with ruff and mypy
	$(PYTHON) -m ruff check unimonitor/ tests/
	$(PYTHON) -m mypy unimonitor/ --ignore-missing-imports

lint-frontend: ## Lint TypeScript/React code
	@if command -v pnpm >/dev/null 2>&1; then \
	  cd frontend && pnpm lint; \
	else \
	  cd frontend && npm run lint; \
	fi

format: ## Auto-format Python code with ruff
	$(PYTHON) -m ruff format unimonitor/ tests/
	$(PYTHON) -m ruff check --fix unimonitor/ tests/

format-frontend: ## Auto-format TypeScript/React code with prettier
	@if command -v pnpm >/dev/null 2>&1; then \
	  cd frontend && pnpm format; \
	else \
	  cd frontend && npm run format; \
	fi

# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────
migrate: ## Apply all pending Alembic migrations
	alembic upgrade head

migrate-create: ## Create a new Alembic migration (MSG="description")
	@if [ -z "$(MSG)" ]; then \
	  echo "Usage: make migrate-create MSG=\"your migration message\""; \
	  exit 1; \
	fi
	alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Downgrade by one migration step
	alembic downgrade -1

migrate-history: ## Show migration history
	alembic history --verbose

db-shell: ## Open a PostgreSQL shell (reads DATABASE_URL from env)
	@$(PYTHON) -c "import os; url=os.environ.get('DATABASE_URL','').replace('postgresql+asyncpg://','postgresql://'); print(url)" | xargs psql

# ─────────────────────────────────────────────────────────────────────────────
# Docker
# ─────────────────────────────────────────────────────────────────────────────
docker: docker-build docker-up ## Build images and start all services

docker-build: ## Build all Docker images
	$(COMPOSE) -f deploy/docker/docker-compose.yml build

docker-up: ## Start all services (detached)
	$(COMPOSE) -f deploy/docker/docker-compose.yml up -d
	@echo "Services starting — API will be available at http://localhost:8000"

docker-down: ## Stop all services
	$(COMPOSE) -f deploy/docker/docker-compose.yml down

docker-down-v: ## Stop all services and remove volumes (destructive!)
	$(COMPOSE) -f deploy/docker/docker-compose.yml down -v

docker-logs: ## Tail logs from all services
	$(COMPOSE) -f deploy/docker/docker-compose.yml logs -f

docker-logs-api: ## Tail API service logs
	$(COMPOSE) -f deploy/docker/docker-compose.yml logs -f unimonitor

docker-restart: ## Restart all services
	$(COMPOSE) -f deploy/docker/docker-compose.yml restart

docker-migrate: ## Run migrations inside the Docker API container
	$(COMPOSE) -f deploy/docker/docker-compose.yml exec unimonitor alembic upgrade head

docker-shell: ## Open a shell inside the API container
	$(COMPOSE) -f deploy/docker/docker-compose.yml exec unimonitor /bin/bash

# ─────────────────────────────────────────────────────────────────────────────
# Security checks
# ─────────────────────────────────────────────────────────────────────────────
secrets-check: ## Scan for accidentally committed secrets (requires trufflehog or gitleaks)
	@if command -v gitleaks >/dev/null 2>&1; then \
	  gitleaks detect --source . --verbose; \
	elif command -v trufflehog >/dev/null 2>&1; then \
	  trufflehog git file://. --only-verified; \
	else \
	  echo "Install gitleaks or trufflehog for secret scanning."; \
	  grep -rn --include="*.py" --include="*.yaml" --include="*.yml" --include="*.json" \
	    -E "(password|secret|api_key|client_secret)\s*=\s*['\"][^'\"]{8,}" . \
	    --exclude-dir=.git \
	    --exclude-dir=node_modules \
	    --exclude-dir=__pycache__ \
	    || echo "No obvious plaintext secrets found."; \
	fi

audit-python: ## Run pip-audit to check for known CVEs in Python deps
	pip-audit --require-hashes -r requirements.txt || pip-audit

audit-frontend: ## Run npm audit to check for known CVEs in JS deps
	@if command -v pnpm >/dev/null 2>&1; then \
	  cd frontend && pnpm audit; \
	else \
	  cd frontend && npm audit; \
	fi

# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────
setup: ## Run the first-run setup wizard
	$(PYTHON) scripts/setup_wizard.py

setup-dev: ## Quick dev environment setup (SQLite + local vault)
	@cp -n .env.example .env 2>/dev/null || true
	@echo "UNIMONITOR_ENV=development" >> .env
	$(MAKE) install
	$(PYTHON) -m alembic upgrade head
	@echo ""
	@echo "✅ Dev environment ready. Run 'make dev' to start."

pre-commit: ## Install pre-commit hooks
	pre-commit install
	pre-commit install --hook-type commit-msg

pre-commit-run: ## Run all pre-commit hooks against all files
	pre-commit run --all-files

# ─────────────────────────────────────────────────────────────────────────────
# Frontend build
# ─────────────────────────────────────────────────────────────────────────────
frontend-build: ## Build the frontend for production
	@if command -v pnpm >/dev/null 2>&1; then \
	  cd frontend && pnpm build; \
	else \
	  cd frontend && npm run build; \
	fi

frontend-preview: ## Preview the production frontend build
	@if command -v pnpm >/dev/null 2>&1; then \
	  cd frontend && pnpm preview; \
	else \
	  cd frontend && npm run preview; \
	fi

# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────
clean: clean-pyc ## Remove build artefacts

clean-pyc: ## Remove Python bytecode files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage

clean-node: ## Remove node_modules and build output
	rm -rf frontend/node_modules frontend/dist
