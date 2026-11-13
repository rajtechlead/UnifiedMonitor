# INSTALLATION_GUIDE.md
**UniMonitor — Unified Monitoring and GRC Solution for Microsoft 365**  
**Version:** 1.0.0  
**Last Updated:** 2026-11-13

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Deployment Options](#deployment-options)
3. [Option A — Windows Installer (Recommended)](#option-a--windows-installer-recommended)
4. [Option B — Docker Compose](#option-b--docker-compose)
5. [Option C — Manual Python Install](#option-c--manual-python-install)
6. [Post-Installation Configuration](#post-installation-configuration)
7. [Verify Installation](#verify-installation)
8. [Uninstalling](#uninstalling)

---

## Prerequisites

### For All Deployment Options
| Requirement | Minimum | Recommended |
|---|---|---|
| Microsoft 365 tenant | Any plan | Business Premium or higher |
| Microsoft Entra ID | Yes | With admin consent granted |
| PostgreSQL | 14 | 16+ |
| Redis | 6.2 | 7+ |
| Outbound HTTPS | 443 | — |

### Microsoft Entra ID App Registration
Before installing, create an app registration in Entra ID:

1. Go to **Azure Portal → Entra ID → App registrations → New registration**
2. Name: `UniMonitor`
3. Redirect URI: `https://<your-host>/auth/callback` (or `http://localhost:8000/auth/callback` for dev)
4. Under **API permissions**, add:
   - `User.Read.All` (Application)
   - `Directory.Read.All` (Application)
   - `Policy.Read.All` (Application)
   - `DeviceManagementConfiguration.Read.All` (Application)
   - `SecurityEvents.Read.All` (Application)
5. Click **Grant admin consent**
6. Under **Certificates & secrets**, create a new **Client secret**
7. Note: **Application (client) ID**, **Directory (tenant) ID**, and the **Client secret value**

---

## Deployment Options

| Option | OS | Best for |
|---|---|---|
| Windows Installer | Windows Server 2019+ / Windows 10+ | Production Windows environments |
| Docker Compose | Linux / macOS / Windows | Containerised or cloud deployments |
| Manual Python | Linux / macOS | Development and custom environments |

---

## Option A — Windows Installer (Recommended)

### System Requirements
- Windows Server 2019+ or Windows 10/11 (64-bit)
- 4 GB RAM minimum (8 GB recommended)
- 20 GB free disk space
- .NET 4.8+ (for NSIS uninstaller; usually pre-installed)
- PostgreSQL 14+ (must be installed separately before running the installer)
- Redis 6.2+ (bundled option available, or use external Redis)

### Installation Steps

1. **Download** `UniMonitor-Setup.exe` from the [latest GitHub release](https://github.com/rajtechlead/UniMonitor/releases)
2. **Run the installer** as Administrator
3. Follow the Setup Wizard:
   - Accept the licence agreement
   - Choose install directory (default: `C:\Program Files\UniMonitor\`)
   - Provide database connection string (PostgreSQL)
   - Provide Redis connection string
   - Provide Entra ID credentials (tenant ID, client ID, client secret)
4. Click **Install**
5. The installer will:
   - Copy application files
   - Create Windows Service `UniMonitorSvc`
   - Run database migrations (`alembic upgrade head`)
   - Start the service
6. Click **Finish**

### Verify Windows Service

```powershell
Get-Service UniMonitorSvc
# Expected: Status Running
```

### Installer Silent Mode (for GPO/SCCM deployment)

```powershell
.\UniMonitor-Setup.exe /S /DB_URL="postgresql+asyncpg://user:pass@host/db" /REDIS_URL="redis://host:6379/0" /TENANT_ID="<guid>" /CLIENT_ID="<guid>" /CLIENT_SECRET="<secret>"
```

---

## Option B — Docker Compose

### System Requirements
- Docker 24+ and Docker Compose v2
- 4 GB RAM
- 20 GB free disk space

### Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/rajtechlead/UnifiedMonitor.git
   cd UnifiedMonitor
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   # Edit .env with your values (see Post-Installation Configuration)
   ```

3. **Start services:**
   ```bash
   docker compose -f deploy/docker/docker-compose.yml up -d
   ```

4. **Run database migrations:**
   ```bash
   docker compose exec backend alembic upgrade head
   ```

5. **Check status:**
   ```bash
   docker compose ps
   # All services should show 'running'
   ```

### Docker Compose Services
| Service | Port | Description |
|---|---|---|
| `backend` | 8000 | FastAPI application |
| `frontend` | 3000 | React frontend (Nginx) |
| `postgres` | 5432 | PostgreSQL database |
| `redis` | 6379 | Redis cache / broker |
| `celery` | — | Background task worker |

---

## Option C — Manual Python Install

### System Requirements
- Python 3.12+
- PostgreSQL 14+
- Redis 6.2+
- Node.js 20+ (for frontend build)

### Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/rajtechlead/UnifiedMonitor.git
   cd UnifiedMonitor
   ```

2. **Create a virtual environment:**
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -e ".[production]"
   ```

4. **Build the frontend:**
   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```

5. **Configure environment** (see [Post-Installation Configuration](#post-installation-configuration))

6. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

7. **Start the application:**
   ```bash
   unimonitor serve
   ```

---

## Post-Installation Configuration

### Environment Variables
Create a `.env` file in the installation directory (or set as system environment variables):

```env
# Database
DATABASE_URL=postgresql+asyncpg://unimonitor:password@localhost:5432/unimonitor
DATABASE_ECHO=false

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# Microsoft Entra ID
AZURE_TENANT_ID=<your-tenant-id>
AZURE_CLIENT_ID=<your-client-id>
AZURE_CLIENT_SECRET=<your-client-secret>

# Application
APP_HOST=0.0.0.0
APP_PORT=8000
ALLOWED_ORIGINS=https://your-domain.com
LOG_LEVEL=INFO

# Secrets backend (choose one)
SECRETS_BACKEND=local          # local | azure_keyvault | aws_secretsmanager
# For Azure Key Vault:
# AZURE_KEY_VAULT_URL=https://your-vault.vault.azure.net/
# For AWS Secrets Manager:
# AWS_REGION=us-east-1
```

### Generating a Secure Secret Key
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Admin User Creation
After first startup, create the initial admin user:
```bash
unimonitor create-admin --email admin@yourdomain.com --password <secure-password>
```

---

## Verify Installation

1. **Health check:**
   ```bash
   curl http://localhost:8000/health
   # Expected: {"status": "healthy"}
   ```

2. **Open the browser:**
   Navigate to `http://localhost:8000` (or your configured host)

3. **Sign in:**
   - Use the email/password you created with `create-admin`
   - Or click **Sign in with Microsoft** to authenticate via Entra ID

4. **Run smoke tests:**
   ```bash
   unimonitor smoke-test
   ```

---

## Uninstalling

### Windows Installer
- Go to **Control Panel → Programs → Uninstall a program**
- Select **UniMonitor** and click **Uninstall**
- The uninstaller will stop the service, remove files, and optionally remove the database

### Docker Compose
```bash
docker compose -f deploy/docker/docker-compose.yml down -v
```

### Manual Install
```bash
deactivate
rm -rf .venv
# Remove the installation directory and .env file
```

---

## Support
- GitHub Issues: https://github.com/rajtechlead/UnifiedMonitor/issues
- Security issues: See SECURITY.md
