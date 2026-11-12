"""Application configuration via Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET_KEY = "change-me-in-production"


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

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./unimonitor.db"
    DATABASE_SYNC_URL: str = "sqlite:///./unimonitor.db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False

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

    @model_validator(mode="after")
    def reject_default_secret_key_in_production(self) -> "Settings":
        """Refuse to start in production with the default SECRET_KEY."""
        if (
            self.UNIMONITOR_ENV == "production"
            and self.UNIMONITOR_SECRET_KEY == _DEFAULT_SECRET_KEY
        ):
            raise ValueError(
                "UNIMONITOR_SECRET_KEY must be changed from the default value before "
                "running in production. Generate a key with: "
                "python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return self

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
    def REPORTS_DIR(self) -> str:
        """Alias for REPORT_STORAGE_PATH — used by report generators."""
        return self.REPORT_STORAGE_PATH


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
