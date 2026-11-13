# TROUBLESHOOTING_GUIDE.md
**UniMonitor — Unified Monitoring and GRC Solution for Microsoft 365**  
**Version:** 1.0.0  
**Last Updated:** 2026-11-13

---

## Table of Contents
1. [Startup Issues](#startup-issues)
2. [Authentication Issues](#authentication-issues)
3. [Database Issues](#database-issues)
4. [Redis / Cache Issues](#redis--cache-issues)
5. [Microsoft Graph API Issues](#microsoft-graph-api-issues)
6. [Assessment Issues](#assessment-issues)
7. [Frontend Issues](#frontend-issues)
8. [Performance Issues](#performance-issues)
9. [Windows Installer Issues](#windows-installer-issues)
10. [Docker Issues](#docker-issues)
11. [Diagnostic Commands](#diagnostic-commands)

---

## Startup Issues

### Application fails to start — `Connection refused` to PostgreSQL

**Symptom:** `sqlalchemy.exc.OperationalError: connection refused`

**Causes and fixes:**
1. PostgreSQL is not running → start it: `systemctl start postgresql`
2. Wrong `DATABASE_URL` — verify host, port, username, password, database name
3. PostgreSQL is not accepting connections from the app host — check `pg_hba.conf`
4. Database does not exist → `createdb unimonitor`

---

### Application fails to start — `could not connect to Redis`

**Symptom:** `redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379`

**Causes and fixes:**
1. Redis is not running → `systemctl start redis`
2. Wrong `REDIS_URL` — verify host and port
3. Redis requires a password — add `?password=<password>` to `REDIS_URL`

---

### Application fails to start — `alembic.util.exc.CommandError: Can't locate revision`

**Symptom:** Migration error at startup

**Fix:**
```bash
# Reset migrations to head (destructive — only on a fresh database)
alembic stamp head

# Or apply migrations fresh
alembic upgrade head
```

---

### `OSError: Readme file does not exist: README.md` during Docker build

**Fix:** Ensure the Dockerfile includes:
```dockerfile
COPY pyproject.toml README.md ./
```
hatchling requires `README.md` to be present in the build context.

---

### Windows Service fails to start — Event ID 7001

**Symptom:** Service does not start; Event Viewer shows error code 1053

**Causes and fixes:**
1. Environment variables not set for the service account — set them in the service's Environment block via `sc config` or the installer
2. Python path incorrect — verify the installation directory
3. Port 8000 already in use: `netstat -ano | findstr :8000` — kill the conflicting process

---

## Authentication Issues

### `401 Unauthorized` on API requests

**Causes and fixes:**
1. JWT token expired — re-authenticate; adjust `JWT_EXPIRE_MINUTES` if too short
2. Wrong `SECRET_KEY` — verify that all instances use the same key
3. Token sent in wrong header — must be `Authorization: Bearer <token>`

---

### `403 Forbidden` — tenant not found

**Symptom:** API returns 403 for valid credentials

**Causes and fixes:**
1. Tenant not registered in the system — register via the admin API or the setup wizard
2. User not associated with a tenant — check user record in the database

---

### Microsoft OAuth login fails — `AADSTS700016: Application not found`

**Fix:**
1. Verify `AZURE_CLIENT_ID` matches the app registration in Entra ID
2. Verify `AZURE_TENANT_ID` matches your directory
3. Ensure the app registration redirect URI matches `APP_HOST/auth/callback`

---

### Microsoft OAuth login fails — `AADSTS65001: Consent required`

**Fix:**  
An admin must grant consent for the app's API permissions:
1. Go to **Azure Portal → Entra ID → App registrations → UniMonitor → API permissions**
2. Click **Grant admin consent for `<tenant>`**

---

### `python-jose` JWT decode error — `jose.exceptions.JWTError`

**Causes and fixes:**
1. Token was issued by a different instance with a different `SECRET_KEY`
2. Token has been tampered with
3. Wrong algorithm configured — verify `JWT_ALGORITHM=HS256`

---

## Database Issues

### `sqlalchemy.exc.IntegrityError: duplicate key value`

**Causes and fixes:**
1. Duplicate data being inserted — check application logic
2. Sequence out of sync after a restore:
   ```sql
   SELECT setval('tablename_id_seq', (SELECT MAX(id) FROM tablename));
   ```

---

### `sqlalchemy.exc.OperationalError: too many connections`

**Fix:**
1. Increase PostgreSQL's `max_connections` in `postgresql.conf`
2. Reduce `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW` in settings
3. Consider PgBouncer for connection pooling in high-load environments

---

### Alembic migration fails — `relation already exists`

**Fix:**  
The database is ahead of Alembic's tracking. Stamp the current state:
```bash
alembic stamp <revision_id>
alembic upgrade head
```

---

### SQLite in-memory database used instead of PostgreSQL

**Symptom:** Data disappears on restart; `DATABASE_URL` not respected

**Fix:**  
UniMonitor falls back to SQLite only when `DATABASE_URL` is not set or starts with `sqlite`. Verify the environment variable is loaded:
```bash
unimonitor config show | grep DATABASE_URL
```

---

## Redis / Cache Issues

### Cache not working — `GET /api/v1/dashboard` always slow

**Diagnosis:**
```bash
redis-cli monitor | grep dashboard
# If no cache hits appear, cache is bypassed
```

**Causes and fixes:**
1. `REDIS_URL` incorrect — cache failures are silently swallowed; check logs
2. Redis maxmemory policy is `noeviction` and Redis is full — increase `maxmemory` or switch to `allkeys-lru`
3. Cache TTL too short — increase `REDIS_CACHE_TTL`

---

### Celery tasks not processing

**Symptom:** Tasks enqueued but not running

**Fix:**
```bash
# Check workers are running
celery -A unimonitor.worker.celery_app inspect ping

# Check queue depth
celery -A unimonitor.worker.celery_app inspect reserved

# Check for failed tasks
celery -A unimonitor.worker.celery_app events
```

---

## Microsoft Graph API Issues

### `401 Unauthorized` from Graph API

**Causes and fixes:**
1. Client secret has expired — rotate the secret in Entra ID and update `AZURE_CLIENT_SECRET`
2. App registration deleted or disabled in Entra ID
3. Token cache stale — restart the application to clear the MSAL token cache

---

### `403 Forbidden` from Graph API — specific endpoint

**Causes and fixes:**
1. Required API permission not granted — see the [Microsoft Entra ID App Registration](INSTALLATION_GUIDE.md#microsoft-entra-id-app-registration) section
2. Conditional Access policy blocking the service principal — check Entra ID sign-in logs

---

### `throttled` responses from Graph API — `429 Too Many Requests`

**Fix:**  
UniMonitor uses `tenacity` for automatic retry with exponential backoff. If throttling is persistent:
1. Reduce assessment frequency in the schedule settings
2. Enable Graph API response caching (increase `REDIS_CACHE_TTL`)

---

### Graph API data appears stale

**Fix:**  
UniMonitor caches Graph API responses in Redis. Clear the cache:
```bash
redis-cli KEYS "graph:*" | xargs redis-cli DEL
```

---

## Assessment Issues

### Assessment run stuck in `running` state

**Causes and fixes:**
1. Celery worker crashed mid-task — restart the worker; the task will time out and be retried
2. Deadlock in database — check PostgreSQL locks: `SELECT * FROM pg_locks WHERE NOT granted;`
3. Graph API rate limit hit — wait and retry

---

### Assessment shows `0 controls evaluated`

**Causes and fixes:**
1. YAML control files not found — check `controls/` directory is present and contains `.yaml` files
2. Invalid YAML syntax in control file — run `unimonitor controls validate`
3. No tenants registered — register a tenant first

---

### Control results always `unknown`

**Causes and fixes:**
1. Graph API permissions missing for the control type
2. Control YAML uses non-standard `result` values — must be `pass`, `fail`, `error`, or `unknown`

---

## Frontend Issues

### Blank white screen on load

**Causes and fixes:**
1. Frontend build artefacts not present — run `npm run build` in `frontend/`
2. API backend not reachable — check `VITE_API_URL` environment variable used at build time
3. Browser console shows CORS error — verify `ALLOWED_ORIGINS` includes the frontend origin

---

### Login page shows but `Sign In` button does nothing

**Causes and fixes:**
1. Backend API returning errors — check browser DevTools → Network tab
2. Backend not running — verify `GET /health` returns 200

---

### `Sign in with Microsoft` button returns error page

**Fix:**  
See [Microsoft OAuth login fails](#microsoft-oauth-login-fails--aadsts700016-application-not-found).

---

## Performance Issues

### API responses slow (> 2s)

**Diagnosis:**
```bash
# Check slow queries in PostgreSQL
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 20;
```

**Causes and fixes:**
1. Missing database indexes — run `EXPLAIN ANALYSE` on slow queries
2. Cache not warming — verify Redis is reachable and cache TTL is adequate
3. Too many Graph API calls per request — enable caching; check for N+1 patterns

---

### High memory usage in backend

**Causes and fixes:**
1. Too many open DB connections — reduce `DATABASE_POOL_SIZE`
2. Memory leak in a long-running Celery task — set `CELERYD_MAX_TASKS_PER_CHILD=100`
3. Large assessment results not paginated — enable pagination on API calls

---

## Windows Installer Issues

### Installer reports `Error opening file for writing`

**Fix:**  
Run the installer as Administrator. If files are locked:
1. Stop the `UniMonitorSvc` service
2. Close any file explorers open to the install directory
3. Re-run the installer

---

### Service does not appear after installation

**Fix:**
```powershell
# Re-register the service manually
sc create UniMonitorSvc binPath="C:\Program Files\UniMonitor\UniMonitor.exe serve" start=auto
sc start UniMonitorSvc
```

---

### Uninstaller leaves files behind

**Fix:**  
Manually delete `C:\Program Files\UniMonitor\` after uninstalling. This is a known limitation when log files are open.

---

## Docker Issues

### `docker compose up` fails — `port 5432 already in use`

**Fix:**  
Local PostgreSQL instance running. Either:
1. Stop local PostgreSQL: `systemctl stop postgresql`
2. Change the port mapping in `docker-compose.yml`: `"5433:5432"`

---

### Backend container exits immediately

**Fix:**
```bash
docker compose logs backend
# Check the last error message
```

Common causes:
1. `DATABASE_URL` or `REDIS_URL` not set in `.env`
2. Database not accepting connections yet — the backend has a health-check retry but may time out

---

## Diagnostic Commands

```bash
# Check all configuration values
unimonitor config show

# Validate YAML controls
unimonitor controls validate

# Test database connectivity
unimonitor db ping

# Test Redis connectivity
unimonitor cache ping

# Test Graph API connectivity
unimonitor graph ping --tenant-id <guid>

# Run smoke tests
unimonitor smoke-test

# View recent structured logs (pretty-printed)
unimonitor logs tail --lines 100

# Check secrets backend
unimonitor secrets status
```
