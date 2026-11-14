"""
Unit tests for unimonitor/notifications/dispatcher.py

All network calls (httpx, smtplib) and DB queries are mocked.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_dispatcher(db=None):
    from unimonitor.notifications.dispatcher import NotificationDispatcher
    db = db or AsyncMock()
    return NotificationDispatcher(db=db, tenant_id="tenant-001"), db


def _make_settings_obj(
    smtp_enabled=False,
    smtp_to_emails=None,
    teams_webhook_url=None,
    slack_webhook_url=None,
):
    obj = MagicMock()
    obj.smtp_enabled = smtp_enabled
    obj.smtp_to_emails = smtp_to_emails or []
    obj.teams_webhook_url = teams_webhook_url
    obj.slack_webhook_url = slack_webhook_url
    return obj


def _db_result(value):
    r = MagicMock()
    r.all.return_value = value
    r.scalar_one_or_none.return_value = value if not isinstance(value, list) else None
    r.scalars.return_value.all.return_value = value if isinstance(value, list) else []
    return r


# ---------------------------------------------------------------------------
# _send_to_channels
# ---------------------------------------------------------------------------

class TestSendToChannels:
    def test_no_channels_configured(self):
        d, _ = _make_dispatcher()
        settings_obj = _make_settings_obj()
        _run(d._send_to_channels("subj", "body", settings_obj))  # no error

    def test_smtp_called_when_enabled(self):
        d, _ = _make_dispatcher()
        settings_obj = _make_settings_obj(smtp_enabled=True, smtp_to_emails=["a@b.com"])
        with patch.object(d, "_send_smtp", new_callable=AsyncMock) as mock_smtp:
            _run(d._send_to_channels("subj", "body", settings_obj))
            mock_smtp.assert_awaited_once_with(["a@b.com"], "subj", "body")

    def test_smtp_emails_as_json_string(self):
        d, _ = _make_dispatcher()
        settings_obj = _make_settings_obj(
            smtp_enabled=True, smtp_to_emails='["a@b.com","c@d.com"]'
        )
        with patch.object(d, "_send_smtp", new_callable=AsyncMock) as mock_smtp:
            _run(d._send_to_channels("subj", "body", settings_obj))
            mock_smtp.assert_awaited_once_with(["a@b.com", "c@d.com"], "subj", "body")

    def test_smtp_emails_as_plain_string(self):
        """Non-JSON string treated as a single email address."""
        d, _ = _make_dispatcher()
        settings_obj = _make_settings_obj(smtp_enabled=True, smtp_to_emails="a@b.com")
        with patch.object(d, "_send_smtp", new_callable=AsyncMock) as mock_smtp:
            _run(d._send_to_channels("subj", "body", settings_obj))
            mock_smtp.assert_awaited_once_with(["a@b.com"], "subj", "body")

    def test_smtp_error_swallowed(self):
        """SMTP failures are caught and logged — do not propagate."""
        d, _ = _make_dispatcher()
        settings_obj = _make_settings_obj(smtp_enabled=True, smtp_to_emails=["a@b.com"])
        with patch.object(d, "_send_smtp", new_callable=AsyncMock, side_effect=RuntimeError("conn refused")):
            _run(d._send_to_channels("subj", "body", settings_obj))  # must not raise

    def test_teams_called_when_configured(self):
        d, _ = _make_dispatcher()
        settings_obj = _make_settings_obj(teams_webhook_url="https://teams.example.com/hook")
        with patch.object(d, "_send_teams_webhook", new_callable=AsyncMock) as mock_teams:
            _run(d._send_to_channels("subj", "body", settings_obj))
            mock_teams.assert_awaited_once()

    def test_teams_error_swallowed(self):
        d, _ = _make_dispatcher()
        settings_obj = _make_settings_obj(teams_webhook_url="https://teams.example.com/hook")
        with patch.object(d, "_send_teams_webhook", new_callable=AsyncMock, side_effect=RuntimeError("timeout")):
            _run(d._send_to_channels("subj", "body", settings_obj))  # must not raise

    def test_slack_called_when_configured(self):
        d, _ = _make_dispatcher()
        settings_obj = _make_settings_obj(slack_webhook_url="https://hooks.slack.com/xxx")
        with patch.object(d, "_send_slack_webhook", new_callable=AsyncMock) as mock_slack:
            _run(d._send_to_channels("subj", "body", settings_obj))
            mock_slack.assert_awaited_once()

    def test_slack_error_swallowed(self):
        d, _ = _make_dispatcher()
        settings_obj = _make_settings_obj(slack_webhook_url="https://hooks.slack.com/xxx")
        with patch.object(d, "_send_slack_webhook", new_callable=AsyncMock, side_effect=RuntimeError("timeout")):
            _run(d._send_to_channels("subj", "body", settings_obj))  # must not raise

    def test_all_channels_called_together(self):
        d, _ = _make_dispatcher()
        settings_obj = _make_settings_obj(
            smtp_enabled=True,
            smtp_to_emails=["a@b.com"],
            teams_webhook_url="https://teams.example.com/hook",
            slack_webhook_url="https://hooks.slack.com/xxx",
        )
        with (
            patch.object(d, "_send_smtp", new_callable=AsyncMock) as smtp,
            patch.object(d, "_send_teams_webhook", new_callable=AsyncMock) as teams,
            patch.object(d, "_send_slack_webhook", new_callable=AsyncMock) as slack,
        ):
            _run(d._send_to_channels("subj", "body", settings_obj))
            smtp.assert_awaited_once()
            teams.assert_awaited_once()
            slack.assert_awaited_once()


# ---------------------------------------------------------------------------
# _send_teams_webhook
# ---------------------------------------------------------------------------

class TestSendTeamsWebhook:
    def test_posts_correct_payload(self):
        d, _ = _make_dispatcher()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            _run(d._send_teams_webhook("https://hook.url", "Subject", "Body text"))

        mock_client.post.assert_awaited_once()
        _, kwargs = mock_client.post.call_args
        payload = kwargs["json"]
        assert payload["@type"] == "MessageCard"
        assert "Subject" in payload["summary"]
        mock_resp.raise_for_status.assert_called_once()

    def test_raises_on_http_error(self):
        import httpx
        d, _ = _make_dispatcher()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=MagicMock()
        )
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception):
                _run(d._send_teams_webhook("https://hook.url", "Subject", "Body"))


# ---------------------------------------------------------------------------
# _send_slack_webhook
# ---------------------------------------------------------------------------

class TestSendSlackWebhook:
    def test_posts_correct_payload(self):
        d, _ = _make_dispatcher()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            _run(d._send_slack_webhook("https://hooks.slack.com/xxx", "Subject", "Body"))

        mock_client.post.assert_awaited_once()
        _, kwargs = mock_client.post.call_args
        payload = kwargs["json"]
        assert payload["text"] == "Subject"
        assert any(b.get("type") == "header" for b in payload["blocks"])
        mock_resp.raise_for_status.assert_called_once()


# ---------------------------------------------------------------------------
# _send_smtp
# ---------------------------------------------------------------------------

class TestSendSmtp:
    def test_smtp_calls_sendmail(self):
        d, _ = _make_dispatcher()
        mock_server = MagicMock()
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=None)

        with patch("smtplib.SMTP", return_value=mock_server):
            _run(d._send_smtp(["a@b.com"], "Subject", "Body"))

        mock_server.sendmail.assert_called_once()

    def test_smtp_with_credentials(self):
        d, _ = _make_dispatcher()
        mock_server = MagicMock()
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=None)

        with (
            patch("smtplib.SMTP", return_value=mock_server),
            patch("unimonitor.notifications.dispatcher.settings") as mock_settings,
        ):
            mock_settings.SMTP_FROM = "from@example.com"
            mock_settings.SMTP_HOST = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = "user"
            mock_settings.SMTP_PASSWORD = "pass"
            _run(d._send_smtp(["a@b.com"], "Subject", "Body"))

        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.sendmail.assert_called_once()


# ---------------------------------------------------------------------------
# send_daily_digest / send_weekly_digest / send_finding_alert (public API)
# ---------------------------------------------------------------------------

class TestPublicAPI:
    def test_send_daily_digest(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_db_result([("CRITICAL", 2), ("HIGH", 5)]))
        d = __import__("unimonitor.notifications.dispatcher", fromlist=["NotificationDispatcher"]).NotificationDispatcher(db=db, tenant_id="t1")
        settings_obj = _make_settings_obj(slack_webhook_url="https://hooks.slack.com/x")

        with patch.object(d, "_send_slack_webhook", new_callable=AsyncMock) as mock_slack:
            _run(d.send_daily_digest(settings_obj))
            mock_slack.assert_awaited_once()
            args = mock_slack.call_args[0]
            # args: (webhook_url, subject, body)
            subject = args[1]
            assert "Daily Digest" in subject
            assert "7" in subject  # 2+5

    def test_send_weekly_digest(self):
        db = AsyncMock()
        # First execute: finding counts. Second: latest run.
        run_mock = MagicMock()
        run_mock.security_score = 82.5
        db.execute = AsyncMock(
            side_effect=[
                _db_result([("HIGH", 3)]),
                _db_result(run_mock),
            ]
        )
        from unimonitor.notifications.dispatcher import NotificationDispatcher
        d = NotificationDispatcher(db=db, tenant_id="t1")
        settings_obj = _make_settings_obj(teams_webhook_url="https://teams.example.com/x")

        with patch.object(d, "_send_teams_webhook", new_callable=AsyncMock) as mock_teams:
            _run(d.send_weekly_digest(settings_obj))
            mock_teams.assert_awaited_once()
            subject = mock_teams.call_args[0][1]  # (url, subject, body)
            assert "Weekly" in subject

    def test_send_finding_alert(self):
        d, _ = _make_dispatcher()
        finding = MagicMock()
        finding.severity = "CRITICAL"
        finding.external_control_id = "CC6.1"
        finding.title = "MFA not enforced"
        finding.state = "not_implemented"
        finding.category = "Access Control"
        finding.description = "Multi-factor authentication is not enforced."
        settings_obj = _make_settings_obj(smtp_enabled=True, smtp_to_emails=["sec@corp.com"])

        with patch.object(d, "_send_smtp", new_callable=AsyncMock) as mock_smtp:
            _run(d.send_finding_alert(finding, settings_obj))
            mock_smtp.assert_awaited_once()
            # _send_smtp is called with (to_emails, subject, body)
            args = mock_smtp.call_args[0]
            subject = args[1]
            body = args[2]
            assert "CRITICAL" in subject
            assert "CC6.1" in subject
            assert "MFA not enforced" in body

    def test_send_finding_alert_missing_attrs(self):
        """Finding with minimal attributes should not raise."""
        d, _ = _make_dispatcher()
        finding = MagicMock()
        finding.id = "find-001"
        # Remove optional attributes to force getattr fallbacks
        del finding.external_control_id
        del finding.title
        del finding.state
        del finding.category
        del finding.description
        settings_obj = _make_settings_obj()
        _run(d.send_finding_alert(finding, settings_obj))  # no channels → no error

    def test_send_daily_digest_no_findings(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_db_result([]))
        from unimonitor.notifications.dispatcher import NotificationDispatcher
        d = NotificationDispatcher(db=db, tenant_id="t1")
        settings_obj = _make_settings_obj(slack_webhook_url="https://hooks.slack.com/x")

        with patch.object(d, "_send_slack_webhook", new_callable=AsyncMock) as mock_slack:
            _run(d.send_daily_digest(settings_obj))
            mock_slack.assert_awaited_once()
            subject = mock_slack.call_args[0][1]  # (url, subject, body)
            assert "0" in subject
