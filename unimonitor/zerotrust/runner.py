"""Run a Zero Trust assessment and write its interactive report.

The Python engine scores every platform from UniMonitor's own evidence and is the
default on every host. Microsoft additionally ships a PowerShell assessment module;
when the install runs on Windows with PowerShell available the runner can execute it
with the registered Entra app and copy the module's own report into the report folder.
If that path is unavailable or fails, the Python engine still produces a report, so a
run is never silently empty.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from unimonitor.core.logging import get_logger
from unimonitor.zerotrust import reports, service

logger = get_logger(__name__)

POWERSHELL_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "zerotrust" / "Invoke-ZtAppOnly.ps1"
POWERSHELL_TIMEOUT_SECONDS = 4 * 60 * 60


def powershell_path() -> str | None:
    """``pwsh`` first (PowerShell 7 is what the module needs), then ``powershell``."""
    if sys.platform != "win32":
        return None
    return shutil.which("pwsh") or shutil.which("powershell")


def _certificate_pfx(app: dict[str, Any], folder: Path) -> tuple[Path, str]:
    """Write the vaulted certificate and key to a private temporary PFX.

    Microsoft's module authenticates app-only with a certificate, and it needs the
    private key on the machine running the assessment. The file is created with an
    owner-only mode and removed by the caller's ``finally`` block.
    """
    import secrets as _secrets

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509 import load_pem_x509_certificate

    certificate = load_pem_x509_certificate(str(app["certificate_pem"]).encode())
    decoded_key = serialization.load_pem_private_key(str(app["private_key_pem"]).encode(), password=None)
    # The loader's union includes key types PKCS#12 cannot hold; an app certificate
    # is always RSA/EC, and a wrong key fails loudly inside the serializer.
    key = cast(Any, decoded_key)
    password = _secrets.token_urlsafe(24)
    blob = pkcs12.serialize_key_and_certificates(
        name=b"unimonitor-zt",
        key=key,
        cert=certificate,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode()),
    )
    target = folder / "app.pfx"
    target.write_bytes(blob)
    target.chmod(0o600)
    return target, password


async def _run_powershell(app: dict[str, Any], tenant_name: str) -> tuple[Path | None, str | None]:
    """Attempt Microsoft's own assessment module with the registered app."""
    executable = powershell_path()
    if not executable or not POWERSHELL_SCRIPT.is_file():
        return None, "PowerShell 7 is not available on this host."
    if not (app.get("certificate_pem") and app.get("private_key_pem")):
        # The module has no client-secret app auth; telling the administrator is
        # better than a silent empty report.
        return None, "Microsoft's module needs certificate app authentication. Re-connect Microsoft 365 with a certificate to run it."

    import tempfile

    output = reports.zt_directory() / "powershell"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="unimonitor-zt-") as temporary:
        try:
            pfx_path, pfx_password = _certificate_pfx(app, Path(temporary))
        except Exception as exc:  # noqa: BLE001 - a bad certificate pair is a setup problem
            return None, f"The stored app certificate could not be used: {str(exc)[:200]}"

        command = [
            executable,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(POWERSHELL_SCRIPT),
            "-TenantId",
            str(app.get("directory") or ""),
            "-ClientId",
            str(app.get("client_id") or ""),
            "-OutputPath",
            str(output),
        ]
        # Neither the key nor its password goes on the command line: a process
        # argument list is readable by other users on the host.
        environment = {
            **os.environ,
            "ZT_CLIENT_PFX": str(pfx_path),
            "ZT_CLIENT_PFX_PASSWORD": pfx_password,
        }
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=POWERSHELL_TIMEOUT_SECONDS)
        except TimeoutError:
            process.kill()
            logger.error("zt_powershell_timeout", tenant=tenant_name)
            return None, "The Microsoft assessment timed out."

    if process.returncode != 0:
        message = (stderr or stdout or b"").decode(errors="replace").strip()[-500:]
        logger.warning("zt_powershell_failed", code=process.returncode, error=message)
        return None, message or f"PowerShell exited with code {process.returncode}"
    generated = sorted(output.glob("*.html"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not generated:
        logger.warning("zt_powershell_no_report", stdout=(stdout or b"")[-400:].decode(errors="replace"))
        return None, "The Microsoft assessment finished without writing an HTML report."
    target = reports.zt_directory() / reports.report_name("microsoft")
    shutil.copyfile(generated[0], target)
    return target, None


async def run_assessment_now(
    *,
    tenant_id: str,
    platform: str,
    user_id: str | None = None,
    engine: str = "python",
) -> dict[str, Any]:
    """Score one platform, persist the run and write the HTML report."""
    from sqlalchemy import select

    from unimonitor.db.base import async_session_factory
    from unimonitor.db.models.tenant import Tenant
    from unimonitor.onboarding.service import microsoft_app

    async with async_session_factory() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
        if tenant is None:
            raise ValueError(f"Tenant {tenant_id} not found")

        engine_used = "python"
        report_path: Path | None = None
        powershell_error: str | None = None
        if platform == "microsoft" and engine == "powershell":
            try:
                app = await microsoft_app(db, tenant.id)
                report_path, failure = await _run_powershell(app, tenant.display_name or tenant.name)
                powershell_error = failure
            except Exception as exc:  # noqa: BLE001 - fall back to Python, never fail the run
                powershell_error = str(exc)[:300]
                logger.warning("zt_powershell_unavailable", error=powershell_error)
            if report_path is not None:
                engine_used = "powershell"

        checks = await service.cloud_checks(db, tenant.id, platform)
        run, summary = await service.store_run(
            db,
            tenant_id=tenant.id,
            source=platform,
            checks=checks,
            origin=engine_used,
            user_id=user_id,
        )
        if report_path is None:
            catalogue, _rows = service.catalogue_for(platform)
            content = reports.render_html(
                platform=platform,
                catalogue=catalogue,
                summary=summary,
                checks=checks,
                tenant_name=tenant.display_name or tenant.name,
                engine=engine_used,
            )
            report_path = reports.write_report(content, platform, datetime.now(UTC))
        await db.commit()

    logger.info("zt_assessment_completed", tenant_id=tenant_id, platform=platform, engine=engine_used, run_id=run.id)
    return {
        "run_id": run.id,
        "platform": platform,
        "engine": engine_used,
        "report": report_path.name,
        "report_path": str(report_path),
        "summary": summary,
        "powershell_error": powershell_error,
        "checked_at": datetime.now(UTC).isoformat(),
    }


__all__ = ["POWERSHELL_SCRIPT", "powershell_path", "run_assessment_now"]
