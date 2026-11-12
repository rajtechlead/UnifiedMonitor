"""
Secret access audit log.

Every secret read, write, rotation, and deletion is logged with:
  - timestamp (UTC)
  - operation (get / set / rotate / delete / health_check)
  - secret name (safe to log — it is not the value)
  - provider type
  - caller context (function + module derived from call stack)
  - outcome (success / error)
  - latency_ms

Audit events are emitted via structlog (picked up by OTEL log exporter)
and optionally written to a local append-only audit file.
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import structlog

logger = structlog.get_logger("unimonitor.secrets.audit")


class AuditOperation(str, Enum):
    GET = "get"
    SET = "set"
    ROTATE = "rotate"
    DELETE = "delete"
    HEALTH_CHECK = "health_check"
    LIST = "list"


class SecretAuditLog:
    """Logs secret access events to structlog and optional file."""

    def __init__(self, audit_file: Path | None = None) -> None:
        self._audit_file = audit_file
        if audit_file:
            audit_file.parent.mkdir(parents=True, exist_ok=True)

    def _write_to_file(self, record: dict) -> None:
        if not self._audit_file:
            return
        try:
            import json
            with self._audit_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception as exc:
            logger.error("Failed to write audit log to file", error=str(exc))

    def log(
        self,
        operation: AuditOperation,
        secret_name: str,
        provider: str,
        success: bool,
        latency_ms: float | None = None,
        error: str | None = None,
    ) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "secret_access",
            "operation": operation.value,
            "secret_name": secret_name,
            "provider": provider,
            "success": success,
            "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
            "error": error,
        }

        if success:
            logger.info(
                "secret_access",
                operation=operation.value,
                secret_name=secret_name,
                provider=provider,
                latency_ms=record["latency_ms"],
            )
        else:
            logger.warning(
                "secret_access_failed",
                operation=operation.value,
                secret_name=secret_name,
                provider=provider,
                error=error,
            )

        self._write_to_file(record)

    @asynccontextmanager
    async def track(
        self,
        operation: AuditOperation,
        secret_name: str,
        provider: str,
    ):
        """Async context manager that tracks timing and outcome of an operation."""
        start = time.monotonic()
        try:
            yield
            self.log(
                operation=operation,
                secret_name=secret_name,
                provider=provider,
                success=True,
                latency_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as exc:
            self.log(
                operation=operation,
                secret_name=secret_name,
                provider=provider,
                success=False,
                latency_ms=(time.monotonic() - start) * 1000,
                error=str(exc),
            )
            raise
