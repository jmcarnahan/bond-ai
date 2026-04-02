"""Tests for local_auth.py -- local MSAL authentication."""

import http.client
import os
import threading
from unittest.mock import patch, MagicMock

import pytest


class TestGetLocalToken:
    """Test get_local_token() flow."""

    def test_raises_without_client_id(self):
        from ms_graph.local_auth import get_local_token

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(PermissionError, match="MS_CLIENT_ID"):
                get_local_token()

    def test_returns_cached_token_silent(self):
        from ms_graph.local_auth import get_local_token

        mock_app = MagicMock()
        mock_app.get_accounts.return_value = [{"username": "user@example.com"}]
        mock_app.acquire_token_silent.return_value = {"access_token": "cached-tok"}

        with patch.dict(os.environ, {"MS_CLIENT_ID": "test-id"}, clear=True), \
             patch("ms_graph.local_auth._create_msal_app", return_value=mock_app), \
             patch("ms_graph.local_auth._load_token_cache"), \
             patch("ms_graph.local_auth._save_token_cache"):
            token = get_local_token()

        assert token == "cached-tok"
        mock_app.acquire_token_silent.assert_called_once()

    def test_falls_back_to_browser_when_no_cache(self):
        from ms_graph.local_auth import get_local_token

        mock_app = MagicMock()
        mock_app.get_accounts.return_value = []

        with patch.dict(os.environ, {"MS_CLIENT_ID": "test-id"}, clear=True), \
             patch("ms_graph.local_auth._create_msal_app", return_value=mock_app), \
             patch("ms_graph.local_auth._load_token_cache"), \
             patch("ms_graph.local_auth._save_token_cache"), \
             patch("ms_graph.local_auth._acquire_token_browser",
                   return_value={"access_token": "browser-tok"}) as mock_browser:
            token = get_local_token()

        assert token == "browser-tok"
        mock_browser.assert_called_once()

    def test_falls_back_to_device_code_when_browser_fails(self):
        from ms_graph.local_auth import get_local_token

        mock_app = MagicMock()
        mock_app.get_accounts.return_value = []

        with patch.dict(os.environ, {"MS_CLIENT_ID": "test-id"}, clear=True), \
             patch("ms_graph.local_auth._create_msal_app", return_value=mock_app), \
             patch("ms_graph.local_auth._load_token_cache"), \
             patch("ms_graph.local_auth._save_token_cache"), \
             patch("ms_graph.local_auth._acquire_token_browser", return_value=None), \
             patch("ms_graph.local_auth._acquire_token_device_code",
                   return_value={"access_token": "device-tok"}) as mock_device:
            token = get_local_token()

        assert token == "device-tok"
        mock_device.assert_called_once()

    def test_raises_when_all_flows_fail(self):
        from ms_graph.local_auth import get_local_token

        mock_app = MagicMock()
        mock_app.get_accounts.return_value = []

        with patch.dict(os.environ, {"MS_CLIENT_ID": "test-id"}, clear=True), \
             patch("ms_graph.local_auth._create_msal_app", return_value=mock_app), \
             patch("ms_graph.local_auth._load_token_cache"), \
             patch("ms_graph.local_auth._acquire_token_browser", return_value=None), \
             patch("ms_graph.local_auth._acquire_token_device_code", return_value=None):
            with pytest.raises(PermissionError, match="authentication failed"):
                get_local_token()

    def test_silent_failure_falls_through_to_browser(self):
        """When acquire_token_silent returns None, browser flow should be tried."""
        from ms_graph.local_auth import get_local_token

        mock_app = MagicMock()
        mock_app.get_accounts.return_value = [{"username": "user@example.com"}]
        mock_app.acquire_token_silent.return_value = None

        with patch.dict(os.environ, {"MS_CLIENT_ID": "test-id"}, clear=True), \
             patch("ms_graph.local_auth._create_msal_app", return_value=mock_app), \
             patch("ms_graph.local_auth._load_token_cache"), \
             patch("ms_graph.local_auth._save_token_cache"), \
             patch("ms_graph.local_auth._acquire_token_browser",
                   return_value={"access_token": "browser-tok"}) as mock_browser:
            token = get_local_token()

        assert token == "browser-tok"
        mock_browser.assert_called_once()


class TestGetScopes:
    def test_consumer_scopes_without_tenant(self):
        from ms_graph.local_auth import _get_scopes

        with patch.dict(os.environ, {}, clear=True):
            scopes = _get_scopes()
        assert "Mail.Read" in scopes
        assert "Files.Read.All" in scopes
        assert "Team.ReadBasic.All" not in scopes
        assert "Sites.Read.All" not in scopes

    def test_org_scopes_with_tenant(self):
        from ms_graph.local_auth import _get_scopes

        with patch.dict(os.environ, {"MS_TENANT_ID": "my-tenant"}):
            scopes = _get_scopes()
        assert "Mail.Read" in scopes
        assert "Team.ReadBasic.All" in scopes
        assert "Sites.Read.All" in scopes


def _send_fake_redirect(port: int, code: str = "test-code", state: str = "test-state"):
    """Send a simulated OAuth redirect to the local callback server."""
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", f"/?code={code}&state={state}")
        conn.getresponse()
        conn.close()
    except Exception:
        pass


class TestAcquireTokenBrowser:
    """Test _acquire_token_browser() with a real localhost HTTP server."""

    def test_returns_none_when_initiate_fails(self):
        from ms_graph.local_auth import _acquire_token_browser

        mock_app = MagicMock()
        mock_app.initiate_auth_code_flow.return_value = {"error": "invalid_scope"}

        result = _acquire_token_browser(mock_app, ["Mail.Read"])
        assert result is None

    def test_returns_none_on_exception(self):
        from ms_graph.local_auth import _acquire_token_browser

        mock_app = MagicMock()
        mock_app.initiate_auth_code_flow.side_effect = RuntimeError("boom")

        result = _acquire_token_browser(mock_app, ["Mail.Read"])
        assert result is None

    def test_successful_browser_flow(self):
        """Full browser flow: server starts, redirect arrives, MSAL exchanges code."""
        from ms_graph.local_auth import _acquire_token_browser

        mock_app = MagicMock()
        mock_app.initiate_auth_code_flow.return_value = {
            "auth_uri": "https://login.microsoftonline.com/authorize?state=test-state",
            "state": "test-state",
        }
        mock_app.acquire_token_by_auth_code_flow.return_value = {
            "access_token": "browser-tok-123",
        }

        def fake_open(url):
            """Instead of opening browser, send redirect to the callback server."""
            redirect_uri = mock_app.initiate_auth_code_flow.call_args[1]["redirect_uri"]
            port = int(redirect_uri.rsplit(":", 1)[1])
            # Send the redirect in a separate thread so handle_request() can process it
            threading.Thread(
                target=_send_fake_redirect, args=(port,), daemon=True
            ).start()

        with patch("ms_graph.local_auth.webbrowser") as mock_wb:
            mock_wb.open.side_effect = fake_open
            result = _acquire_token_browser(mock_app, ["Mail.Read"])

        assert result == {"access_token": "browser-tok-123"}
        mock_app.acquire_token_by_auth_code_flow.assert_called_once()
        # Verify the auth_response passed to MSAL contains the code
        exchange_args = mock_app.acquire_token_by_auth_code_flow.call_args
        auth_response = exchange_args[0][1]
        assert auth_response["code"] == "test-code"
        assert auth_response["state"] == "test-state"

    def test_returns_none_when_msal_exchange_fails(self):
        """MSAL receives the code but token exchange returns an error."""
        from ms_graph.local_auth import _acquire_token_browser

        mock_app = MagicMock()
        mock_app.initiate_auth_code_flow.return_value = {
            "auth_uri": "https://login.microsoftonline.com/authorize?state=s",
            "state": "s",
        }
        mock_app.acquire_token_by_auth_code_flow.return_value = {
            "error": "invalid_grant",
            "error_description": "Code expired",
        }

        def fake_open(url):
            call_args = mock_app.initiate_auth_code_flow.call_args
            redirect_uri = call_args[1]["redirect_uri"]
            port = int(redirect_uri.rsplit(":", 1)[1])
            threading.Thread(
                target=_send_fake_redirect, args=(port,), daemon=True
            ).start()

        with patch("ms_graph.local_auth.webbrowser") as mock_wb:
            mock_wb.open.side_effect = fake_open
            result = _acquire_token_browser(mock_app, ["Mail.Read"])

        assert result is None

    def test_returns_none_when_redirect_has_error(self):
        """Microsoft returns an error instead of a code in the redirect."""
        from ms_graph.local_auth import _acquire_token_browser

        mock_app = MagicMock()
        mock_app.initiate_auth_code_flow.return_value = {
            "auth_uri": "https://login.microsoftonline.com/authorize",
            "state": "s",
        }

        def fake_open(url):
            call_args = mock_app.initiate_auth_code_flow.call_args
            redirect_uri = call_args[1]["redirect_uri"]
            port = int(redirect_uri.rsplit(":", 1)[1])

            def send_error(p):
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", p, timeout=5)
                    conn.request("GET", "/?error=access_denied&error_description=User+cancelled")
                    conn.getresponse()
                    conn.close()
                except Exception:
                    pass

            threading.Thread(target=send_error, args=(port,), daemon=True).start()

        with patch("ms_graph.local_auth.webbrowser") as mock_wb:
            mock_wb.open.side_effect = fake_open
            result = _acquire_token_browser(mock_app, ["Mail.Read"])

        assert result is None
        mock_app.acquire_token_by_auth_code_flow.assert_not_called()


class TestTokenCacheSecurity:
    def test_save_sets_0600_permissions(self, tmp_path):
        import ms_graph.local_auth as la

        mock_cache = MagicMock()
        mock_cache.has_state_changed = True
        mock_cache.serialize.return_value = '{"cache": "data"}'

        fake_path = tmp_path / ".ms_graph_tokens.json"
        with patch.object(la, "TOKEN_CACHE_PATH", fake_path):
            la._save_token_cache(mock_cache)

        assert fake_path.exists()
        mode = fake_path.stat().st_mode & 0o777
        assert mode == 0o600

    def test_save_skips_when_no_state_change(self, tmp_path):
        import ms_graph.local_auth as la

        mock_cache = MagicMock()
        mock_cache.has_state_changed = False

        fake_path = tmp_path / ".ms_graph_tokens.json"
        with patch.object(la, "TOKEN_CACHE_PATH", fake_path):
            la._save_token_cache(mock_cache)

        assert not fake_path.exists()
