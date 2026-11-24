"""Notification dispatcher — sends alerts via SMTP, Teams, and Slack."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from unimonitor.config import get_settings
from unimonitor.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class NotificationDispatcher:
    """Sends notifications to configured channels for a tenant."""

    def __init__(self, db: Any, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id

    # ── Public methods ───────────────────────────────────────────────────────

    async def send_daily_digest(self, settings_obj: Any) -> None:
        """Send daily digest to all configured channels."""
        subject, body = await self._build_daily_digest_body(self.tenant_id)
        await self._send_to_channels(subject, body, settings_obj)

    async def send_weekly_digest(self, settings_obj: Any) -> None:
        """Send weekly digest."""
        subject, body = await self._build_weekly_digest_body(self.tenant_id)
        await self._send_to_channels(subject, body, settings_obj)

    async def send_finding_alert(self, finding: Any, settings_obj: Any) -> None:
        """Send an immediate alert for a specific finding."""
        sev = (getattr(finding, "severity", "HIGH") or "HIGH").upper()
        ctrl_id = getattr(finding, "external_control_id", finding.id)
        title = getattr(finding, "title", "Security Finding")
        subject = f"[UniMonitor Alert] {sev}: {ctrl_id} — {title}"
        body = (
            f"**Security Finding Alert**\n\n"
            f"**Control:** {ctrl_id}\n"
            f"**Title:** {title}\n"
            f"**Severity:** {sev}\n"
            f"**Status:** {getattr(finding, 'state', 'not_implemented')}\n"
            f"**Category:** {getattr(finding, 'category', '')}\n\n"
            f"**Description:**\n{getattr(finding, 'description', '')}\n\n"
            f"Review this finding in your UniMonitor dashboard."
        )
        await self._send_to_channels(subject, body, settings_obj)

    async def send_alert(self, alert: Any, settings_obj: Any) -> None:
        """Send an alert-policy notification through the configured channels."""
        sev = (getattr(alert, "severity", "HIGH") or "HIGH").upper()
        subject = f"[UniMonitor Alert] {sev}: {getattr(alert, 'title', 'Alert')}"
        body = (
            f"**Alert triggered**\n\n"
            f"**{getattr(alert, 'title', 'Alert')}**\n\n"
            f"**Severity:** {sev}\n"
            f"**Status:** {getattr(alert, 'status', 'open')}\n"
            f"**Metric:** {getattr(alert, 'metric', '')} = "
            f"{getattr(alert, 'metric_value', '')} (threshold {getattr(alert, 'threshold', '')})\n\n"
            f"{getattr(alert, 'detail', '') or ''}\n\n"
            f"Open the Alert Center in UniMonitor to acknowledge or resolve it."
        )
        await self._send_to_channels(subject, body, settings_obj)

    # ── Channel dispatch ─────────────────────────────────────────────────────

    async def _send_to_channels(self, subject: str, body: str, settings_obj: Any) -> None:
        await self._send_email_channel(subject, body, settings_obj)
        await self._send_teams_channel(subject, body, settings_obj)
        await self._send_slack_channel(subject, body, settings_obj)

    @staticmethod
    def _recipients(settings_obj: Any) -> list[str]:
        emails = getattr(settings_obj, "smtp_to_emails", None) or []
        if isinstance(emails, str):
            try:
                emails = json.loads(emails)
            except ValueError:
                emails = [emails]
        if not isinstance(emails, list):
            return []
        return [str(address).strip() for address in emails if str(address).strip()]

    async def _send_email_channel(self, subject: str, body: str, settings_obj: Any) -> None:
        emails = self._recipients(settings_obj)
        if not emails:
            return
        # The registered Entra app is the built-in default: an install that has
        # connected Microsoft 365 can send without SMTP. SMTP is used when it is
        # switched on, and Graph is the fallback when SMTP is not configured.
        smtp_ready = bool(getattr(settings_obj, "smtp_enabled", False) and getattr(settings_obj, "smtp_host", None))
        if smtp_ready:
            try:
                await asyncio.to_thread(self._send_smtp, emails, subject, body)
                return
            except Exception as exc:
                logger.error("SMTP send failed", extra={"error": str(exc), "tenant_id": self.tenant_id})
        try:
            await self._send_graph_email(emails, subject, body, settings_obj)
        except Exception as exc:
            logger.error("Graph mail send failed", extra={"error": str(exc), "tenant_id": self.tenant_id})

    def _graph_sender(self, settings_obj: Any) -> str:
        """The mailbox Graph sends from: the configured From, else the app's account."""
        from unimonitor.config import get_settings

        configured = getattr(settings_obj, "smtp_from_address", None) or getattr(settings_obj, "smtp_username", None) or get_settings().SMTP_FROM
        return str(configured).strip()

    async def _send_graph_email(self, to_emails: list[str], subject: str, body: str, settings_obj: Any) -> None:
        """Send through Microsoft Graph with the connected app (Mail.Send)."""
        from sqlalchemy import select

        from unimonitor.auth.oauth import acquire_token_for_client
        from unimonitor.config import get_settings
        from unimonitor.db.models.cloud_connection import CloudConnection
        from unimonitor.onboarding.service import microsoft_app

        app = await microsoft_app(self.db, self.tenant_id)
        if not app.get("configured"):
            return
        sender = self._graph_sender(settings_obj)
        if not sender:
            account = (
                await self.db.execute(
                    select(CloudConnection.account).where(
                        CloudConnection.tenant_id == self.tenant_id,
                        CloudConnection.provider == "microsoft",
                    )
                )
            ).scalar_one_or_none()
            sender = str(account or "").strip()
        if not sender:
            raise RuntimeError("No sender address: set a From address in notification settings.")

        token = await acquire_token_for_client(
            tenant_id=app.get("directory"),
            client_id=app.get("client_id"),
            client_secret=app.get("client_secret") or None,
            certificate_pem=app.get("certificate_pem") or None,
            private_key_pem=app.get("private_key_pem") or None,
        )
        message = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body.replace("\n", "<br>")},
                "toRecipients": [{"emailAddress": {"address": address}} for address in to_emails],
            },
            "saveToSentItems": True,
        }
        url = f"{get_settings().graph_base_url}/users/{sender}/sendMail"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                url,
                json=message,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
        if response.status_code >= 400:
            raise RuntimeError(f"Graph sendMail answered HTTP {response.status_code}: {response.text[:200]}")
        logger.info("Graph mail sent", extra={"to": to_emails, "subject": subject})

    async def _send_teams_channel(self, subject: str, body: str, settings_obj: Any) -> None:
        teams_url = getattr(settings_obj, "teams_webhook_url", None)
        if not teams_url:
            return
        try:
            await self._send_teams_webhook(teams_url, subject, body)
        except Exception as exc:
            logger.error("Teams webhook failed", extra={"error": str(exc), "tenant_id": self.tenant_id})

    async def _send_slack_channel(self, subject: str, body: str, settings_obj: Any) -> None:
        slack_url = getattr(settings_obj, "slack_webhook_url", None)
        if not slack_url:
            return
        try:
            await self._send_slack_webhook(slack_url, subject, body)
        except Exception as exc:
            logger.error("Slack webhook failed", extra={"error": str(exc), "tenant_id": self.tenant_id})

    def _send_smtp(self, to_emails: list[str], subject: str, body: str) -> None:
        """Send via SMTP using smtplib; blocking, so callers run it in a thread."""
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM or "unimonitor@noreply.local"
        msg["To"] = ", ".join(to_emails)
        msg.attach(MIMEText(body, "plain"))

        # Convert markdown-ish body to simple HTML
        html_body = body.replace("\n", "<br>").replace("**", "<strong>").replace("**", "</strong>")
        msg.attach(MIMEText(f"<html><body>{html_body}</body></html>", "html"))

        with smtplib.SMTP(settings.SMTP_HOST or "localhost", settings.SMTP_PORT or 587) as server:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], to_emails, msg.as_string())

        logger.info("SMTP sent", extra={"to": to_emails, "subject": subject})

    async def _send_teams_webhook(self, webhook_url: str, subject: str, body: str) -> None:
        """Send Microsoft Teams Adaptive Card via webhook."""
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "1776D2",
            "summary": subject,
            "sections": [
                {
                    "activityTitle": f"**{subject}**",
                    "activitySubtitle": f"Tenant: {self.tenant_id}",
                    "text": body[:1000],
                    "markdown": True,
                }
            ],
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
        logger.info("Teams webhook sent", extra={"subject": subject})

    async def _send_slack_webhook(self, webhook_url: str, subject: str, body: str) -> None:
        """Send Slack message via incoming webhook."""
        payload = {
            "text": subject,
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": subject[:150]},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": body[:2900]},
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"UniMonitor | Tenant: `{self.tenant_id}` | {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
                        }
                    ],
                },
            ],
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
        logger.info("Slack webhook sent", extra={"subject": subject})

    # ── Digest builders ──────────────────────────────────────────────────────

    async def _build_daily_digest_body(self, tenant_id: str) -> tuple[str, str]:
        from sqlalchemy import func as sqlfunc
        from sqlalchemy import select

        from unimonitor.db.models.finding import Finding

        since = datetime.now(UTC) - timedelta(hours=24)
        result = await self.db.execute(
            select(Finding.severity, sqlfunc.count(Finding.id))
            .where(Finding.tenant_id == tenant_id, Finding.first_detected_at >= since)
            .group_by(Finding.severity)
        )
        rows = result.all()

        counts = {r[0].upper() if r[0] else "UNKNOWN": r[1] for r in rows}
        total = sum(counts.values())

        subject = f"[UniMonitor Daily Digest] {total} new findings in last 24h"
        lines = [
            f"Daily Security Digest — {datetime.now(UTC).strftime('%Y-%m-%d')}",
            f"Tenant: {tenant_id}",
            "",
            f"New findings in last 24 hours: {total}",
        ]
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]:
            cnt = counts.get(sev, 0)
            if cnt:
                lines.append(f"  {sev}: {cnt}")

        lines += ["", "Log in to UniMonitor for full details."]
        return subject, "\n".join(lines)

    async def _build_weekly_digest_body(self, tenant_id: str) -> tuple[str, str]:
        from sqlalchemy import func as sqlfunc
        from sqlalchemy import select

        from unimonitor.db.models.assessment import AssessmentRun
        from unimonitor.db.models.finding import Finding

        since = datetime.now(UTC) - timedelta(days=7)
        result = await self.db.execute(
            select(Finding.severity, sqlfunc.count(Finding.id))
            .where(Finding.tenant_id == tenant_id, Finding.first_detected_at >= since)
            .group_by(Finding.severity)
        )
        rows = result.all()
        counts = {r[0].upper() if r[0] else "UNKNOWN": r[1] for r in rows}
        total = sum(counts.values())

        # Latest run score
        latest_run_result = await self.db.execute(
            select(AssessmentRun)
            .join(AssessmentRun.assessment)
            .where(AssessmentRun.assessment.has(tenant_id=tenant_id))
            .order_by(AssessmentRun.started_at.desc())
            .limit(1)
        )
        latest_run = latest_run_result.scalar_one_or_none()
        score_line = ""
        if latest_run and latest_run.security_score is not None:
            score_line = f"Latest Security Score: {latest_run.security_score:.1f}/100"

        subject = f"[UniMonitor Weekly Report] {total} findings this week"
        lines = [
            f"Weekly Security Report — Week of {since.strftime('%Y-%m-%d')}",
            f"Tenant: {tenant_id}",
            "",
            score_line,
            "",
            f"Findings this week: {total}",
        ]
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]:
            cnt = counts.get(sev, 0)
            lines.append(f"  {sev}: {cnt}")

        lines += ["", "Log in to UniMonitor for full details and trend analysis."]
        return subject, "\n".join(lines)
