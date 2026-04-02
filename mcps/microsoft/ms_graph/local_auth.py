"""
Local MSAL authentication for standalone use (Claude Code, CLI).

Provides browser-based authorization code + PKCE flow with device code fallback.
Shared between the MCP server (when no Bearer header is present) and the CLI.
"""

import logging
import os
import stat
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import msal

logger = logging.getLogger(__name__)

TOKEN_CACHE_PATH = Path.home() / ".ms_graph_tokens.json"

MAIL_SCOPES = [
    "Mail.Read",
    "Mail.ReadWrite",
    "Mail.Send",
    "MailboxSettings.Read",
    "User.Read",
]

TEAMS_SCOPES = [
    "Team.ReadBasic.All",
    "Channel.ReadBasic.All",
    "ChannelMessage.Send",
]

FILES_SCOPES = [
    "Files.Read.All",
]

SITES_SCOPES = [
    "Sites.Read.All",
]


def _get_scopes() -> list[str]:
    """Return scopes based on whether a tenant ID is set (org vs consumer)."""
    scopes = MAIL_SCOPES + FILES_SCOPES
    if os.environ.get("MS_TENANT_ID"):
        scopes += SITES_SCOPES + TEAMS_SCOPES
    return scopes


def _load_token_cache() -> msal.SerializableTokenCache:
    """Load the MSAL token cache from disk."""
    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE_PATH.exists():
        cache.deserialize(TOKEN_CACHE_PATH.read_text())
    return cache


def _save_token_cache(cache: msal.SerializableTokenCache) -> None:
    """Save cache to disk with 0600 permissions."""
    if cache.has_state_changed:
        TOKEN_CACHE_PATH.write_text(cache.serialize())
        TOKEN_CACHE_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _create_msal_app(
    client_id: str, cache: msal.SerializableTokenCache
) -> msal.PublicClientApplication:
    """Create an MSAL PublicClientApplication."""
    authority = (
        f"https://login.microsoftonline.com/"
        f"{os.environ.get('MS_TENANT_ID', 'consumers')}"
    )
    return msal.PublicClientApplication(
        client_id, authority=authority, token_cache=cache,
    )


def _acquire_token_browser(
    app: msal.PublicClientApplication, scopes: list[str]
) -> dict | None:
    """
    Authorization code flow with PKCE using a localhost redirect.

    Opens the user's browser to Microsoft login. A temporary HTTP server
    on localhost:0 (random free port) catches the redirect with the auth code.
    Returns the MSAL result dict or None if the flow fails.
    """
    auth_response = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(urlparse(self.path).query)
            # Flatten single-value lists for MSAL compatibility
            auth_response.update({k: v[0] if len(v) == 1 else v for k, v in qs.items()})

            if "code" in qs:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h2>Authentication successful.</h2>"
                    b"<p>You can close this tab.</p></body></html>"
                )
            else:
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h2>Authentication failed.</h2></body></html>"
                )

        def log_message(self, format, *args):
            pass  # suppress HTTP access logs

    server = None
    try:
        server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
        port = server.server_address[1]
        redirect_uri = f"http://localhost:{port}"

        flow = app.initiate_auth_code_flow(
            scopes=scopes,
            redirect_uri=redirect_uri,
        )

        if "auth_uri" not in flow:
            logger.warning("Failed to initiate auth code flow: %s", flow)
            return None

        auth_url = flow["auth_uri"]
        logger.info("Opening browser for Microsoft login...")
        print(
            f"\nOpening browser for Microsoft login...\n"
            f"If the browser doesn't open, visit:\n{auth_url}\n",
            flush=True,
        )
        webbrowser.open(auth_url)

        # Wait for the redirect (with timeout)
        server.timeout = 120
        server.handle_request()

        if "code" not in auth_response:
            error = auth_response.get("error", "timeout or no response")
            logger.warning("Browser auth failed: %s", error)
            print(f"Browser login not completed ({error}). Trying device code...",
                  flush=True)
            return None

        # Exchange auth code for tokens — pass full auth_response so MSAL
        # can validate state and use the code
        result = app.acquire_token_by_auth_code_flow(flow, auth_response)
        return result if "access_token" in result else None

    except Exception:
        logger.exception("Browser auth flow failed")
        return None
    finally:
        if server:
            server.server_close()


def _acquire_token_device_code(
    app: msal.PublicClientApplication, scopes: list[str]
) -> dict | None:
    """Device code flow fallback -- prints a code for the user to enter."""
    flow = app.initiate_device_flow(scopes=scopes)
    if "user_code" not in flow:
        logger.error("Device flow initiation failed: %s", flow)
        return None

    print(flow["message"], flush=True)
    result = app.acquire_token_by_device_flow(flow)
    return result if "access_token" in result else None


def get_local_token() -> str:
    """
    Acquire a Microsoft Graph access token using local MSAL auth.

    Resolution order:
    1. Cached token (acquire_token_silent)
    2. Browser-based authorization code + PKCE flow
    3. Device code flow fallback

    Raises:
        PermissionError: If all auth methods fail or MS_CLIENT_ID is not set.
    """
    client_id = os.environ.get("MS_CLIENT_ID")
    if not client_id:
        raise PermissionError(
            "MS_CLIENT_ID environment variable is required for local authentication."
        )

    cache = _load_token_cache()
    app = _create_msal_app(client_id, cache)
    scopes = _get_scopes()

    # 1. Try silent (cached)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(scopes, account=accounts[0])
        if result and "access_token" in result:
            _save_token_cache(cache)
            return result["access_token"]

    # 2. Try browser auth code + PKCE
    result = _acquire_token_browser(app, scopes)
    if result and "access_token" in result:
        _save_token_cache(cache)
        return result["access_token"]

    # 3. Fallback to device code
    result = _acquire_token_device_code(app, scopes)
    if result and "access_token" in result:
        _save_token_cache(cache)
        return result["access_token"]

    raise PermissionError(
        "Microsoft authentication failed. Could not acquire a token via "
        "browser or device code flow."
    )
