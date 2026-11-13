# OPERATIONS_GUIDE.md
**UniMonitor — Unified Monitoring and GRC Solution for Microsoft 365**  
**Version:** 1.0.0  
**Last Updated:** 2026-11-13

---

## Table of Contents
1. [Service Management](#service-management)
2. [Configuration Reference](#configuration-reference)
3. [Database Management](#database-management)
4. [Backup and Restore](#backup-and-restore)
5. [Log Management](#log-management)
6. [Monitoring and Health](#monitoring-and-health)
7. [Scaling](#scaling)
8. [Secrets Management](#secrets-management)
9. [Scheduled Tasks and Celery](#scheduled-tasks-and-celery)
10. [Upgrade Procedure](#upgrade-procedure)

---

## Service Management

### Windows Service

```powershell
# Start
Start-Service UniMonitorSvc

# Stop
Stop-Service UniMonitorSvc

# Restart
Restart-Service UniMonitorSvc

# Check status
Get-Service UniMonitorSvc

# View recent events
Get-EventLog -LogName Application -Source UniMonitor -Newest 50
```

### Docker Compose

```bash
# Start all services
docker compose -f deploy/docker/docker-compose.yml up -d

# Stop all services
docker compose -f deploy/docker/docker-compose.yml down

# Restart a specific service
docker compose -f deploy/docker/docker-compose.yml restart backend

# View logs
docker compose -f deploy/docker/docker-compose.yml logs -f backend

# Scale workers
docker compose -f deploy/docker/docker-compose.yml up -d --scale celery=3
```

### Manual/Systemd

```bash
# Start
systemctl start unimonitor

# Stop
systemctl stop unimonitor

# Restart
systemctl restart unimonitor

# Status
systemctl status unimonitor

# Enable on boot
systemctl enable unimonitor
```

---

## Configuration Reference

All settings can be provided as environment variables or in a `.env` file. Settings are loaded via Pydantic settings with the following precedence: environment variables > `.env` file > defaults.

### Core Settings

| Variable | Default | Description |
|---|---|---|
| `APP_HOST` | `0.0.0.0` | Listen address |
| `APP_PORT` | `8000` | Listen port |
| `DEBUG` | `false` | Enable debug mode (never in production) |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |

### Database Settings

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `DATABASE_ECHO` | No | Log all SQL (dev only) |
| `DATABASE_POOL_SIZE` | No (default 10) | Connection pool size |
| `DATABASE_MAX_OVERFLOW` | No (default 20) | Max overflow connections |

### Cache Settings

| Variable | Required | Description |
|---|---|---|
| `REDIS_URL` | Yes | Redis connection string (`redis://host:port/db`) |
| `REDIS_CACHE_TTL` | No (default 300) | Default cache TTL in seconds |

### Authentication Settings

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | JWT signing key (32+ hex chars) |
| `JWT_ALGORITHM` | No (default HS256) | JWT algorithm |
| `JWT_EXPIRE_MINUTES` | No (default 60) | Access token lifetime |
| `AZURE_TENANT_ID` | Yes | Entra ID tenant GUID |
| `AZURE_CLIENT_ID` | Yes | App registration client GUID |
| `AZURE_CLIENT_SECRET` | Yes | App registration client secret |

### Secrets Backend Settings

| Variable | Default | Description |
|---|---|---|
| `SECRETS_BACKEND` | `local` | Backend: `local`, `azure_keyvault`, or `aws_secretsmanager` |
| `AZURE_KEY_VAULT_URL` | — | Required if backend is `azure_keyvault` |
| `LOCAL_VAULT_KEY` | — | Encryption key for local vault |
| `AWS_REGION` | `us-east-1` | AWS region for Secrets Manager |

---

## Database Management

### Running Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Check current revision
alembic current

# View migration history
alembic history --verbose

# Rollback one revision
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>
```

### Creating a New Migration

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "describe your change"

# Empty migration (manual)
alembic revision -m "describe your change"

# Always review generated migration before applying
```

### Database Maintenance

```sql
-- Check table sizes (run in psql)
SELECT
    table_name,
    pg_size_pretty(pg_total_relation_size(table_name::text)) AS total_size
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY pg_total_relation_size(table_name::text) DESC;

-- Vacuum and analyse (run periodically)
VACUUM ANALYSE;
```

---

## Backup and Restore

### PostgreSQL Backup

```bash
# Full database backup
pg_dump -h localhost -U unimonitor -d unimonitor -F c -f unimonitor-$(date +%Y%m%d).dump

# Restore from backup
pg_restore -h localhost -U unimonitor -d unimonitor unimonitor-20261113.dump

# Automated daily backup (cron)
0 2 * * * pg_dump -h localhost -U unimonitor -d unimonitor -F c -f /backups/unimonitor-$(date +\%Y\%m\%d).dump
```

### Local Vault Backup (if using local secrets backend)

```bash
# The local vault file is stored at:
# Windows: %APPDATA%\UniMonitor\vault.enc
# Linux:   ~/.config/unimonitor/vault.enc

# Back it up alongside your database backup
cp ~/.config/unimonitor/vault.enc /backups/vault-$(date +%Y%m%d).enc
```

---

## Log Management

### Log Locations

| Deployment | Log Location |
|---|---|
| Windows Service | `%PROGRAMDATA%\UniMonitor\logs\unimonitor.log` |
| Docker | `docker compose logs backend` |
| Manual | `./logs/unimonitor.log` or stdout |

### Log Format

UniMonitor uses structured JSON logging via structlog:

```json
{
  "timestamp": "2026-11-13T10:00:00Z",
  "level": "info",
  "event": "HTTP request",
  "method": "GET",
  "path": "/api/v1/dashboard",
  "status_code": 200,
  "duration_ms": 45,
  "tenant_id": "..."
}
```

### Log Rotation

For manual deployments, configure logrotate:

```
/var/log/unimonitor/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        systemctl reload unimonitor
    endscript
}
```

---

## Monitoring and Health

### Health Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Liveness probe — returns `{"status": "healthy"}` |
| `GET /health/ready` | Readiness probe — checks DB and Redis connectivity |
| `GET /metrics` | Prometheus metrics (if OpenTelemetry enabled) |

### Key Metrics to Monitor

- `unimonitor_http_requests_total` — total HTTP requests by method/path/status
- `unimonitor_assessment_runs_total` — total assessment runs by tenant/status
- `unimonitor_celery_tasks_total` — Celery task completions
- PostgreSQL: connection pool usage, query times
- Redis: memory usage, cache hit rate

### Alert Thresholds (Recommended)

| Metric | Warning | Critical |
|---|---|---|
| HTTP 5xx error rate | > 1% | > 5% |
| Response latency p95 | > 2s | > 10s |
| DB connection pool usage | > 70% | > 90% |
| Redis memory | > 70% | > 90% |
| Celery queue depth | > 100 | > 500 |

---

## Scaling

### Horizontal Scaling

UniMonitor backend is stateless (session state in Redis). Scale by:

1. Run multiple backend instances behind a load balancer
2. All instances share the same PostgreSQL and Redis
3. Configure `ALLOWED_ORIGINS` on all instances

```bash
# Scale backend workers in Docker Compose
docker compose up -d --scale backend=3
```

### Celery Worker Scaling

```bash
# Scale Celery workers independently
docker compose up -d --scale celery=5

# Or start workers with concurrency
celery -A unimonitor.worker.celery_app worker --concurrency=8 --loglevel=info
```

---

## Secrets Management

UniMonitor supports three secrets backends:

### Local Encrypted Store (default)
Secrets are encrypted with AES-256 and stored locally. Suitable for single-server deployments.

```bash
# Rotate the local vault key
unimonitor secrets rotate-key --new-key <new-key>
```

### Azure Key Vault
```env
SECRETS_BACKEND=azure_keyvault
AZURE_KEY_VAULT_URL=https://your-vault.vault.azure.net/
# Credentials via AZURE_CLIENT_ID + AZURE_CLIENT_SECRET, or managed identity
```

### AWS Secrets Manager
```env
SECRETS_BACKEND=aws_secretsmanager
AWS_REGION=us-east-1
# Credentials via IAM role or AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
```

---

## Scheduled Tasks and Celery

Celery handles all background tasks: Graph API polling, assessment runs, report generation, cache warming.

### Worker Start

```bash
# Start a Celery worker
celery -A unimonitor.worker.celery_app worker --loglevel=info

# Start Celery beat scheduler (runs scheduled tasks)
celery -A unimonitor.worker.celery_app beat --loglevel=info
```

### Inspect Running Tasks

```bash
# List active tasks
celery -A unimonitor.worker.celery_app inspect active

# Check queue length
celery -A unimonitor.worker.celery_app inspect reserved

# Purge queue (caution — discards all pending tasks)
celery -A unimonitor.worker.celery_app purge
```

---

## Upgrade Procedure

### Minor Version Upgrade (e.g. 1.0.0 → 1.0.1)

1. **Back up the database** (see [Backup and Restore](#backup-and-restore))
2. Stop the application service
3. Replace application files (or pull new Docker image)
4. Run migrations: `alembic upgrade head`
5. Start the application service
6. Verify health: `curl http://localhost:8000/health`

### Windows Installer Upgrade

1. Download the new `UniMonitor-Setup.exe`
2. Run as Administrator — the installer detects the existing installation
3. The installer stops the service, upgrades files, runs migrations, and restarts the service

### Docker Compose Upgrade

```bash
git pull origin main
docker compose -f deploy/docker/docker-compose.yml pull
docker compose -f deploy/docker/docker-compose.yml up -d
docker compose exec backend alembic upgrade head
```

### Rollback

If the upgrade fails:

```bash
# Windows: use the uninstaller and reinstall the previous version
# Docker: pin to previous image tag
docker compose -f deploy/docker/docker-compose.yml down
# Edit docker-compose.yml: change image tag to previous version
docker compose -f deploy/docker/docker-compose.yml up -d
docker compose exec backend alembic downgrade -1
```
