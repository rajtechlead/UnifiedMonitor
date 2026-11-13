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

# Install Python dependencies (cached layer)
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --break-system-packages -e ".[production]" 2>/dev/null || \
    pip install --no-cache-dir -e ".[production]"

# Copy application source
COPY unimonitor/ ./unimonitor/
COPY controls/ ./controls/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist ./static/

# Non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER 1000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/monitoring/health || exit 1

CMD ["uvicorn", "unimonitor.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
