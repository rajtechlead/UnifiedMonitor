"""Application configuration via Pydantic Settings."""

from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET_KEY = "change-me-in-production"  # noqa: S105


def _load_or_create_secret_key() -> str:
    """Return the install's JWT signing key, generating and persisting one if absent.

    A fresh install used to start with an empty key and then reject itself, or worse,
    sign tokens with a public placeholder. Generating the key on first use keeps a
    single-node install working with no manual step; set UNIMONITOR_SECRET_KEY to
    share one key across several nodes.
    """
    data_dir = Path(os.environ.get("UNIMONITOR_DATA_DIR") or (Path.home() / ".unimonitor"))
    key_path = data_dir / "secret.key"
    try:
        if key_path.exists():
            existing = key_path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        data_dir.mkdir(parents=True, exist_ok=True)
        generated = secrets.token_hex(32)
        key_path.write_text(generated, encoding="utf-8")
        try:
            key_path.chmod(0o600)
        except OSError:  # noqa: S110 — Windows ACLs already restrict the directory
            pass
        return generated
    except OSError:
        # Read-only filesystem: still start, but tokens will not survive a restart.
        return secrets.token_hex(32)


class Settings(BaseSettings):
    """All application settings loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────
    UNIMONITOR_ENV: Literal["development", "production", "test"] = "production"
    UNIMONITOR_DEBUG: bool = False
    UNIMONITOR_SECRET_KEY: str = _DEFAULT_SECRET_KEY
    UNIMONITOR_ALLOWED_HOSTS: list[str] = ["*"]
    UNIMONITOR_CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    API_V1_PREFIX: str = "/api/v1"
    # Optional JSON file supplying posture keys Graph cannot expose (see collectors/snapshot.py)
    UNIMONITOR_POSTURE_SNAPSHOT: str = ""

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./unimonitor.db"
    DATABASE_SYNC_URL: str = "sqlite:///./unimonitor.db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False

    # ── Multi-cloud providers (AWS / GCP / Google Workspace) ─────
    GCP_PROJECT_ID: str = ""
    GCP_ACCESS_TOKEN: str = ""
    GOOGLE_WORKSPACE_CUSTOMER_ID: str = "my_customer"
    GOOGLE_ACCESS_TOKEN: str = ""

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600

    # ── Celery ───────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_ALWAYS_EAGER: bool = False  # Set True in tests

    # ── Entra ID / Graph ─────────────────────────────────────
    ENTRA_TENANT_ID: str = ""
    ENTRA_CLIENT_ID: str = ""
    ENTRA_CLIENT_SECRET: str = ""
    # Certificate authentication (the setup wizard's default). When both are set they
    # take precedence over ENTRA_CLIENT_SECRET.
    ENTRA_CLIENT_PRIVATE_KEY: str = ""
    ENTRA_CLIENT_CERTIFICATE: str = ""
    # Optional: the public client the setup wizard signs in with. Tenants that block
    # Microsoft's first-party clients (AADSTS65002) put their own app registration here.
    ENTRA_SIGNIN_CLIENT_ID: str = ""
    ENTRA_AUTHORITY: str = "https://login.microsoftonline.com"
    ENTRA_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/callback"
    GRAPH_API_VERSION: str = "v1.0"
    GRAPH_API_BASE_URL: str = "https://graph.microsoft.com"
    GRAPH_RATE_LIMIT_PER_SECOND: float = 5.0
    GRAPH_MAX_CONCURRENT: int = 10
    GRAPH_REQUEST_TIMEOUT: int = 30
    GRAPH_MAX_RETRIES: int = 3

    # ── Admin Bootstrap ──────────────────────────────────────
    BOOTSTRAP_ADMIN_EMAIL: str = ""

    # ── JWT ──────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Telemetry ────────────────────────────────────────────
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "unimonitor"

    # ── Reporting ────────────────────────────────────────────
    REPORT_STORAGE_PATH: str = "./reports"
    REPORT_LOGO_PATH: str = "./branding/logo.png"

    # ── AI Remediation ───────────────────────────────────────
    AI_ENABLED: bool = False
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o"

    # ── Secret Management ────────────────────────────────────
    # Provider: azure_key_vault | aws_secrets_manager | local_vault
    SECRETS_PROVIDER: str = "local_vault"
    SECRETS_CACHE_TTL_SECONDS: int = 300
    SECRETS_FAILOVER_ENABLED: bool = True
    # Azure Key Vault
    AZURE_KEY_VAULT_URL: str = ""
    # AWS Secrets Manager
    AWS_REGION: str = "us-east-1"
    AWS_SECRETS_MANAGER_ENDPOINT_URL: str = ""  # LocalStack override
    # Local Vault
    VAULT_DIR: str = ""  # defaults to ~/.unimonitor/vault
    VAULT_KEY_PATH: str = ""  # separate key file location

    # ── OSINT ────────────────────────────────────────────────
    HIBP_API_KEY: str = ""
    VIRUSTOTAL_API_KEY: str = ""
    SHODAN_API_KEY: str = ""

    # ── Notifications ────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    # Store only the reference key; value retrieved at runtime via SecretResolver
    SMTP_PASSWORD_REF: str = ""
    SMTP_PASSWORD: str = ""  # plaintext fallback for dev/test only
    SMTP_FROM: str = ""
    TEAMS_WEBHOOK_URL: str = ""
    SLACK_WEBHOOK_URL: str = ""

    @field_validator("UNIMONITOR_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            import json

            return json.loads(v)
        return v

    @field_validator("UNIMONITOR_SECRET_KEY", mode="after")
    @classmethod
    def ensure_secret_key(cls, value: str) -> str:
        """Replace an empty or placeholder key with this install's persisted key."""
        if not value or value == _DEFAULT_SECRET_KEY:
            return _load_or_create_secret_key()
        return value

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL.lower()

    @property
    def is_production(self) -> bool:
        return self.UNIMONITOR_ENV == "production"

    @property
    def graph_base_url(self) -> str:
        return f"{self.GRAPH_API_BASE_URL}/{self.GRAPH_API_VERSION}"

    @property
    def REPORTS_DIR(self) -> str:  # noqa: N802
        """Alias for REPORT_STORAGE_PATH — used by report generators."""
        return self.REPORT_STORAGE_PATH


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
