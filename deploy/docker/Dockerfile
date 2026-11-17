# ── Stage 1: Frontend build ───────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --prefer-offline
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend ───────────────────────────────────────────────────
FROM python:3.12-slim AS backend

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Metadata *and* the package must be present before installing: hatchling builds
# the wheel from `unimonitor/`, so installing earlier ships an empty distribution
# and only appears to work because the source is copied in afterwards.
COPY pyproject.toml README.md ./
COPY unimonitor/ ./unimonitor/
RUN pip install --no-cache-dir .

# Runtime data that is not part of the wheel
COPY controls/ ./controls/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY branding/ ./branding/

# Built frontend, where create_app() looks for it
COPY --from=frontend-builder /app/frontend/dist ./unimonitor/static/

# Non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER 1000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/monitoring/health || exit 1

CMD ["uvicorn", "unimonitor.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
