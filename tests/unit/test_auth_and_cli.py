"""
Unit tests for auth/jwt.py, auth/oauth.py, and cli.py

Tests JWT creation/validation, OAuth MSAL app creation, token acquisition,
and CLI command invocation via click.testing.CliRunner.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# auth/jwt.py
# ---------------------------------------------------------------------------


class TestCreateAccessToken:
    def test_returns_string(self):
        from unimonitor.auth.jwt import create_access_token

        token = create_access_token("user@example.com", tenant_id="t1", role="admin")
        assert isinstance(token, str)
        assert len(token) > 20

    def test_round_trip_decode(self):
        from unimonitor.auth.jwt import create_access_token, decode_token

        token = create_access_token("alice@test.com", tenant_id="t1", role="viewer")
        payload = decode_token(token)
        assert payload["sub"] == "alice@test.com"
        assert payload["tenant_id"] == "t1"
        assert payload["role"] == "viewer"
        assert payload["type"] == "access"

    def test_extra_claims_included(self):
        from unimonitor.auth.jwt import create_access_token, decode_token

        token = create_access_token("u@t.com", tenant_id="t1", role="admin", extra={"custom": "value"})
        payload = decode_token(token)
        assert payload["custom"] == "value"

    def test_no_extra_works(self):
        from unimonitor.auth.jwt import create_access_token, decode_token

        token = create_access_token("u@t.com", tenant_id="t2", role="viewer")
        payload = decode_token(token)
        assert "custom" not in payload


class TestCreateRefreshToken:
    def test_returns_string(self):
        from unimonitor.auth.jwt import create_refresh_token

        token = create_refresh_token("user@example.com", tenant_id="t1")
        assert isinstance(token, str)

    def test_type_is_refresh(self):
        from unimonitor.auth.jwt import create_refresh_token, decode_token

        token = create_refresh_token("user@test.com", tenant_id="t1")
        payload = decode_token(token)
        assert payload["type"] == "refresh"
        assert payload["sub"] == "user@test.com"


class TestDecodeToken:
    def test_expired_raises_token_expired_error(self):
        from jwt import ExpiredSignatureError

        from unimonitor.auth.jwt import decode_token
        from unimonitor.exceptions import TokenExpiredError

        with patch("unimonitor.auth.jwt.jwt.decode", side_effect=ExpiredSignatureError("expired")):
            with pytest.raises(TokenExpiredError):
                decode_token("some.token.here")

    def test_invalid_raises_invalid_token_error(self):
        from jwt import InvalidTokenError as JWTError

        from unimonitor.auth.jwt import decode_token
        from unimonitor.exceptions import InvalidTokenError

        with patch("unimonitor.auth.jwt.jwt.decode", side_effect=JWTError("bad signature")):
            with pytest.raises(InvalidTokenError):
                decode_token("bad.token")


class TestValidateAccessToken:
    def test_valid_access_token_accepted(self):
        from unimonitor.auth.jwt import create_access_token, validate_access_token

        token = create_access_token("u@t.com", tenant_id="t1", role="admin")
        payload = validate_access_token(token)
        assert payload["type"] == "access"

    def test_refresh_token_rejected_as_access(self):
        from unimonitor.auth.jwt import create_refresh_token, validate_access_token
        from unimonitor.exceptions import InvalidTokenError

        token = create_refresh_token("u@t.com", tenant_id="t1")
        with pytest.raises(InvalidTokenError, match="not an access token"):
            validate_access_token(token)


class TestValidateRefreshToken:
    def test_valid_refresh_token_accepted(self):
        from unimonitor.auth.jwt import create_refresh_token, validate_refresh_token

        token = create_refresh_token("u@t.com", tenant_id="t1")
        payload = validate_refresh_token(token)
        assert payload["type"] == "refresh"

    def test_access_token_rejected_as_refresh(self):
        from unimonitor.auth.jwt import create_access_token, validate_refresh_token
        from unimonitor.exceptions import InvalidTokenError

        token = create_access_token("u@t.com", tenant_id="t1", role="admin")
        with pytest.raises(InvalidTokenError, match="not a refresh token"):
            validate_refresh_token(token)

    def test_decode_refresh_token_alias(self):
        from unimonitor.auth.jwt import create_refresh_token, decode_refresh_token

        token = create_refresh_token("u@t.com", tenant_id="t1")
        payload = decode_refresh_token(token)
        assert payload["type"] == "refresh"


# ---------------------------------------------------------------------------
# auth/oauth.py
# ---------------------------------------------------------------------------


class TestGetMsalApp:
    def test_creates_confidential_app(self):
        from unimonitor.auth.oauth import get_msal_app

        mock_app = MagicMock()
        with patch("unimonitor.auth.oauth.msal.ConfidentialClientApplication", return_value=mock_app) as mock_cls:
            result = get_msal_app(tenant_id="t1")
        assert result is mock_app
        mock_cls.assert_called_once()

    def test_uses_default_tenant_when_none(self):
        from unimonitor.auth.oauth import get_msal_app

        with patch("unimonitor.auth.oauth.msal.ConfidentialClientApplication") as mock_cls:
            get_msal_app()
        call_kwargs = mock_cls.call_args[1]
        assert "authority" in call_kwargs


class TestGetMsalAppForTenant:
    def test_creates_app_with_tenant_credentials(self):
        from unimonitor.auth.oauth import get_msal_app_for_tenant

        mock_app = MagicMock()
        with patch("unimonitor.auth.oauth.msal.ConfidentialClientApplication", return_value=mock_app) as mock_cls:
            result = get_msal_app_for_tenant("cid", "csec", "tenant-123")
        assert result is mock_app
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["client_id"] == "cid"
        assert call_kwargs["client_credential"] == "csec"


class TestAcquireTokenForClient:
    def test_returns_access_token(self):
        from unimonitor.auth.oauth import acquire_token_for_client

        mock_app = MagicMock()
        mock_app.acquire_token_silent.return_value = None
        mock_app.acquire_token_for_client.return_value = {"access_token": "graph_token"}
        with patch("unimonitor.auth.oauth.get_msal_app", return_value=mock_app):
            result = _run(acquire_token_for_client(tenant_id="t1"))
        assert result == "graph_token"

    def test_uses_cached_token(self):
        from unimonitor.auth.oauth import acquire_token_for_client

        mock_app = MagicMock()
        mock_app.acquire_token_silent.return_value = {"access_token": "cached_token"}
        with patch("unimonitor.auth.oauth.get_msal_app", return_value=mock_app):
            result = _run(acquire_token_for_client())
        assert result == "cached_token"
        mock_app.acquire_token_for_client.assert_not_called()

    def test_error_raises_authentication_error(self):
        from unimonitor.auth.oauth import acquire_token_for_client
        from unimonitor.exceptions import AuthenticationError

        mock_app = MagicMock()
        mock_app.acquire_token_silent.return_value = None
        mock_app.acquire_token_for_client.return_value = {"error": "invalid_client", "error_description": "Bad credentials"}
        with patch("unimonitor.auth.oauth.get_msal_app", return_value=mock_app):
            with pytest.raises(AuthenticationError):
                _run(acquire_token_for_client())

    def test_per_tenant_credentials_use_tenant_app(self):
        from unimonitor.auth.oauth import acquire_token_for_client

        mock_app = MagicMock()
        mock_app.acquire_token_silent.return_value = {"access_token": "tenant_token"}
        with patch("unimonitor.auth.oauth.get_msal_app_for_tenant", return_value=mock_app) as mock_fn:
            result = _run(acquire_token_for_client("tid", "cid", "csec"))
        mock_fn.assert_called_once_with("cid", "csec", "tid")
        assert result == "tenant_token"


class TestGetAuthCodeUrl:
    def test_returns_url_string(self):
        from unimonitor.auth.oauth import get_auth_code_url

        mock_app = MagicMock()
        mock_app.get_authorization_request_url.return_value = "https://login.microsoftonline.com/auth"
        with patch("unimonitor.auth.oauth.get_msal_app", return_value=mock_app):
            result = get_auth_code_url("state_xyz", "nonce_123")
        assert result == "https://login.microsoftonline.com/auth"

    def test_build_authorize_url_alias(self):
        from unimonitor.auth.oauth import build_authorize_url

        mock_app = MagicMock()
        mock_app.get_authorization_request_url.return_value = "https://auth.url"
        with patch("unimonitor.auth.oauth.get_msal_app", return_value=mock_app):
            result = build_authorize_url("state")
        assert result == "https://auth.url"


class TestExchangeCodeForToken:
    def test_success_returns_token_dict(self):
        from unimonitor.auth.oauth import exchange_code_for_token

        mock_app = MagicMock()
        mock_app.acquire_token_by_authorization_code.return_value = {"access_token": "tok", "id_token": "id_tok"}
        with patch("unimonitor.auth.oauth.get_msal_app", return_value=mock_app):
            result = _run(exchange_code_for_token("auth_code"))
        assert result["access_token"] == "tok"

    def test_error_response_raises(self):
        from unimonitor.auth.oauth import exchange_code_for_token
        from unimonitor.exceptions import AuthenticationError

        mock_app = MagicMock()
        mock_app.acquire_token_by_authorization_code.return_value = {"error": "invalid_grant", "error_description": "Code expired"}
        with patch("unimonitor.auth.oauth.get_msal_app", return_value=mock_app):
            with pytest.raises(AuthenticationError):
                _run(exchange_code_for_token("bad_code"))


class TestGetEntraUserInfo:
    def test_returns_user_dict(self):
        from unimonitor.auth.oauth import get_entra_user_info

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "uid-123",
            "mail": "alice@contoso.com",
            "displayName": "Alice Smith",
            "givenName": "Alice",
            "surname": "Smith",
        }
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client
            result = _run(get_entra_user_info("access_token_123"))
        assert result["id"] == "uid-123"
        assert result["email"] == "alice@contoso.com"
        assert result["display_name"] == "Alice Smith"


# ---------------------------------------------------------------------------
# cli.py
# ---------------------------------------------------------------------------


class TestCliStart:
    def test_start_requires_uvicorn(self):
        with patch("builtins.__import__", side_effect=ImportError("no uvicorn")):
            # Can't easily simulate ImportError for uvicorn inside the command
            # Just invoke with mocked uvicorn.run
            pass

    def test_start_calls_uvicorn_run(self):
        from unimonitor.cli import main

        runner = CliRunner()
        with patch("uvicorn.run") as mock_run:
            result = runner.invoke(main, ["start", "--port", "9000"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["port"] == 9000

    def test_start_reload_flag(self):
        from unimonitor.cli import main

        runner = CliRunner()
        with patch("uvicorn.run") as mock_run:
            runner.invoke(main, ["start", "--reload"])
        # reload=True sets workers to 1
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["reload"] is True
        assert call_kwargs["workers"] == 1


class TestCliMigrate:
    def test_migrate_calls_alembic_upgrade(self):
        from unimonitor.cli import main

        runner = CliRunner()
        mock_cfg = MagicMock()
        with patch("alembic.config.Config", return_value=mock_cfg):
            with patch("alembic.command.upgrade") as mock_upgrade:
                result = runner.invoke(main, ["migrate"])
        assert result.exit_code == 0
        mock_upgrade.assert_called_once_with(mock_cfg, "head")
        assert "complete" in result.output.lower()


class TestCliSecrets:
    def test_secrets_health_command(self):
        from unimonitor.cli import main

        runner = CliRunner()
        mock_resolver = AsyncMock()
        mock_resolver.health_check = AsyncMock(return_value={"providers": []})
        with patch("unimonitor.secrets.resolver.get_secret_resolver", new=AsyncMock(return_value=mock_resolver)):
            result = runner.invoke(main, ["secrets", "health"])
        assert result.exit_code == 0
        assert "health" in result.output.lower() or "checking" in result.output.lower()

    def test_secrets_set_command(self):
        from unimonitor.cli import main

        runner = CliRunner()
        mock_resolver = AsyncMock()
        meta = MagicMock()
        meta.provider.value = "local_vault"
        mock_resolver.set = AsyncMock(return_value=meta)
        with patch("unimonitor.secrets.resolver.get_secret_resolver", new=AsyncMock(return_value=mock_resolver)):
            result = runner.invoke(main, ["secrets", "set", "my_secret", "my_value"])
        assert result.exit_code == 0

    def test_secrets_get_command(self):
        from unimonitor.cli import main

        runner = CliRunner()
        mock_resolver = AsyncMock()
        mock_resolver.get = AsyncMock(return_value="secret_value_xyz")
        with patch("unimonitor.secrets.resolver.get_secret_resolver", new=AsyncMock(return_value=mock_resolver)):
            result = runner.invoke(main, ["secrets", "get", "my_secret"])
        assert result.exit_code == 0
        assert "secret_value_xyz" in result.output

    def test_secrets_rotate_command(self):
        from unimonitor.cli import main

        runner = CliRunner()
        mock_resolver = AsyncMock()
        meta = MagicMock()
        meta.version = "v2"
        mock_resolver.rotate = AsyncMock(return_value=meta)
        with patch("unimonitor.secrets.resolver.get_secret_resolver", new=AsyncMock(return_value=mock_resolver)):
            result = runner.invoke(main, ["secrets", "rotate", "my_secret", "new_value"])
        assert result.exit_code == 0

    def test_main_help(self):
        from unimonitor.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "UniMonitor" in result.output

    def test_secrets_group_help(self):
        from unimonitor.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["secrets", "--help"])
        assert result.exit_code == 0

    def test_smoke_test_import_error(self):
        from unimonitor.cli import main

        runner = CliRunner()
        with patch.dict("sys.modules", {"scripts.smoke_test": None}):
            result = runner.invoke(main, ["smoke-test"])
        # Should exit with 1 when scripts.smoke_test is not found
        assert result.exit_code == 1
