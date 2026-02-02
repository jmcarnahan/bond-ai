#!/usr/bin/env python3
"""
Local OAuth MCP Server for Bond AI Connection Testing.

This server acts as BOTH an OAuth2 provider AND an MCP server to test
Bond AI's "Connect" functionality locally. Unlike sample_mcp_server.py
which uses Bond's JWT tokens, this server provides its own OAuth flow
with a browser consent page.

OAuth Endpoints:
    GET  /oauth/authorize - Shows consent page, redirects with authorization code
    POST /oauth/authorize - Handles consent form submission
    POST /oauth/token     - Exchanges authorization code for access token
    GET  /.well-known/oauth-authorization-server - OAuth metadata discovery

MCP Tools (require OAuth authentication):
    - current_time() - Get current server time
    - get_user_info() - Get authenticated user information
    - create_note(title, content) - Create a note (requires 'write' scope)

Usage:
    poetry run python scripts/oauth_mcp_server.py

Configuration (add to BOND_MCP_CONFIG in .env):
    {
      "mcpServers": {
        "local_oauth": {
          "url": "http://localhost:5556/mcp",
          "auth_type": "oauth2",
          "transport": "streamable-http",
          "display_name": "Local OAuth Test",
          "description": "Test OAuth connection flow locally",
          "oauth_client_id": "local-oauth-client",
          "oauth_authorize_url": "http://localhost:5556/oauth/authorize",
          "oauth_token_url": "http://localhost:5556/oauth/token",
          "oauth_scopes": "read write",
          "extra_config": {
            "client_secret": "local-oauth-secret"
          }
        }
      }
    }
"""

import secrets
import hashlib
import base64
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# In-Memory Token Store
# =============================================================================

@dataclass
class AuthorizationCode:
    """Represents an OAuth authorization code."""
    code: str
    client_id: str
    user_id: str
    user_email: str
    redirect_uri: str
    code_challenge: str
    scopes: list[str]
    expires_at: datetime


@dataclass
class AccessTokenData:
    """Represents an OAuth access token."""
    token: str
    client_id: str
    user_id: str
    user_email: str
    scopes: list[str]
    expires_at: datetime


@dataclass
class RefreshTokenData:
    """Represents an OAuth refresh token."""
    token: str
    client_id: str
    user_id: str
    user_email: str
    scopes: list[str]


@dataclass
class OAuthClient:
    """Represents a registered OAuth client."""
    client_id: str
    client_secret: str
    redirect_uris: list[str]
    scopes: list[str] = field(default_factory=lambda: ["read", "write"])


class TokenStore:
    """In-memory store for OAuth tokens and authorization codes."""

    def __init__(self):
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.access_tokens: dict[str, AccessTokenData] = {}
        self.refresh_tokens: dict[str, RefreshTokenData] = {}

        # Pre-registered test client
        self.clients: dict[str, OAuthClient] = {
            "local-oauth-client": OAuthClient(
                client_id="local-oauth-client",
                client_secret="local-oauth-secret",
                redirect_uris=[
                    "http://localhost:8000/connections/local_oauth/callback",
                    "http://127.0.0.1:8000/connections/local_oauth/callback",
                ],
                scopes=["read", "write"]
            )
        }

        # Simulated users for testing
        self.users = {
            "test-user-1": {
                "user_id": "test-user-1",
                "email": "testuser@localtest.com",
                "name": "Test User",
                "given_name": "Test",
                "family_name": "User"
            }
        }

    def get_client(self, client_id: str) -> Optional[OAuthClient]:
        return self.clients.get(client_id)

    def validate_client_secret(self, client_id: str, client_secret: str) -> bool:
        client = self.get_client(client_id)
        if not client:
            return False
        return secrets.compare_digest(client.client_secret, client_secret)

    def create_auth_code(
        self,
        client_id: str,
        user_id: str,
        redirect_uri: str,
        code_challenge: str,
        scopes: list[str]
    ) -> str:
        """Create and store an authorization code."""
        code = secrets.token_urlsafe(32)
        user = self.users.get(user_id, {"email": "unknown@test.com"})

        self.auth_codes[code] = AuthorizationCode(
            code=code,
            client_id=client_id,
            user_id=user_id,
            user_email=user.get("email", "unknown@test.com"),
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            scopes=scopes,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)
        )
        return code

    def consume_auth_code(self, code: str) -> Optional[AuthorizationCode]:
        """Retrieve and delete an authorization code."""
        auth_code = self.auth_codes.pop(code, None)
        if auth_code and auth_code.expires_at < datetime.now(timezone.utc):
            return None  # Expired
        return auth_code

    def create_access_token(
        self,
        client_id: str,
        user_id: str,
        user_email: str,
        scopes: list[str],
        expires_in: int = 3600
    ) -> tuple[str, str, int]:
        """Create access and refresh tokens. Returns (access_token, refresh_token, expires_in)."""
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)

        self.access_tokens[access_token] = AccessTokenData(
            token=access_token,
            client_id=client_id,
            user_id=user_id,
            user_email=user_email,
            scopes=scopes,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        )

        self.refresh_tokens[refresh_token] = RefreshTokenData(
            token=refresh_token,
            client_id=client_id,
            user_id=user_id,
            user_email=user_email,
            scopes=scopes
        )

        return access_token, refresh_token, expires_in

    def validate_access_token(self, token: str) -> Optional[AccessTokenData]:
        """Validate an access token and return its data if valid."""
        token_data = self.access_tokens.get(token)
        if not token_data:
            return None
        if token_data.expires_at < datetime.now(timezone.utc):
            del self.access_tokens[token]
            return None
        return token_data

    def get_refresh_token(self, token: str) -> Optional[RefreshTokenData]:
        """Get refresh token data."""
        return self.refresh_tokens.get(token)


# Global token store
token_store = TokenStore()


# =============================================================================
# PKCE Validation
# =============================================================================

def validate_pkce(code_verifier: str, code_challenge: str) -> bool:
    """
    Validate PKCE code_verifier against stored code_challenge.

    Bond AI generates PKCE using:
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(sha256(verifier)).rstrip('=')
    """
    expected_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('ascii')).digest()
    ).decode('ascii').rstrip('=')

    return secrets.compare_digest(expected_challenge, code_challenge)


# =============================================================================
# FastAPI OAuth Server
# =============================================================================

app = FastAPI(title="Local OAuth MCP Server")


@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    """OAuth 2.0 Authorization Server Metadata (RFC 8414)."""
    return JSONResponse({
        "issuer": "http://localhost:5556",
        "authorization_endpoint": "http://localhost:5556/oauth/authorize",
        "token_endpoint": "http://localhost:5556/oauth/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["read", "write"]
    })


@app.get("/oauth/authorize", response_class=HTMLResponse)
async def authorize_get(
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    state: str = Query(...),
    code_challenge: str = Query(...),
    code_challenge_method: str = Query("S256"),
    scope: str = Query("read")
):
    """
    Authorization endpoint - displays consent page.

    Bond AI opens this URL in the user's browser after clicking "Connect".
    """
    logger.info(f"OAuth authorize request: client_id={client_id}, scope={scope}")

    # Validate client
    client = token_store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=400, detail="Invalid client_id")

    # Validate redirect_uri
    if redirect_uri not in client.redirect_uris:
        logger.warning(f"Invalid redirect_uri: {redirect_uri}")
        logger.warning(f"Allowed URIs: {client.redirect_uris}")
        raise HTTPException(status_code=400, detail=f"Invalid redirect_uri. Allowed: {client.redirect_uris}")

    # Validate response_type
    if response_type != "code":
        raise HTTPException(status_code=400, detail="Only response_type=code is supported")

    # Validate code_challenge_method
    if code_challenge_method != "S256":
        raise HTTPException(status_code=400, detail="Only code_challenge_method=S256 is supported")

    # Parse scopes
    requested_scopes = scope.split() if scope else ["read"]

    # Return HTML consent page
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Authorize - Local OAuth Test</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 500px;
                margin: 100px auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            .card {{
                background: white;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h2 {{
                margin-top: 0;
                color: #333;
            }}
            .app-name {{
                color: #007bff;
                font-weight: bold;
            }}
            .scopes {{
                background: #f8f9fa;
                border-radius: 4px;
                padding: 15px;
                margin: 20px 0;
            }}
            .scope-item {{
                margin: 5px 0;
                padding-left: 20px;
                position: relative;
            }}
            .scope-item:before {{
                content: "\\2713";
                position: absolute;
                left: 0;
                color: #28a745;
            }}
            .buttons {{
                display: flex;
                gap: 10px;
                margin-top: 20px;
            }}
            button {{
                flex: 1;
                padding: 12px 20px;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                cursor: pointer;
            }}
            .allow {{
                background: #007bff;
                color: white;
            }}
            .allow:hover {{
                background: #0056b3;
            }}
            .deny {{
                background: #dc3545;
                color: white;
            }}
            .deny:hover {{
                background: #c82333;
            }}
            .info {{
                font-size: 12px;
                color: #666;
                margin-top: 20px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Authorization Request</h2>
            <p>
                <span class="app-name">Bond AI</span> wants to access your Local OAuth Test account.
            </p>

            <div class="scopes">
                <strong>Requested permissions:</strong>
                {''.join(f'<div class="scope-item">{s}</div>' for s in requested_scopes)}
            </div>

            <form method="POST" action="/oauth/authorize">
                <input type="hidden" name="client_id" value="{client_id}">
                <input type="hidden" name="redirect_uri" value="{redirect_uri}">
                <input type="hidden" name="state" value="{state}">
                <input type="hidden" name="code_challenge" value="{code_challenge}">
                <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
                <input type="hidden" name="scope" value="{scope}">

                <div class="buttons">
                    <button type="submit" name="action" value="deny" class="deny">Deny</button>
                    <button type="submit" name="action" value="allow" class="allow">Allow</button>
                </div>
            </form>

            <p class="info">
                This is a local test OAuth server for Bond AI development.
            </p>
        </div>
    </body>
    </html>
    """


@app.post("/oauth/authorize")
async def authorize_post(
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    state: str = Form(...),
    code_challenge: str = Form(...),
    code_challenge_method: str = Form("S256"),
    scope: str = Form("read"),
    action: str = Form(...)
):
    """Handle consent form submission."""
    logger.info(f"OAuth authorize POST: action={action}, client_id={client_id}")

    # Handle denial
    if action == "deny":
        params = urlencode({"error": "access_denied", "state": state})
        return RedirectResponse(f"{redirect_uri}?{params}", status_code=302)

    # Validate client again
    client = token_store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=400, detail="Invalid client_id")

    # Parse scopes
    scopes = scope.split() if scope else ["read"]

    # Create authorization code
    # Use a fixed test user for simplicity
    user_id = "test-user-1"
    code = token_store.create_auth_code(
        client_id=client_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        scopes=scopes
    )

    logger.info(f"Created auth code for user {user_id}, redirecting to {redirect_uri}")

    # Redirect back to Bond AI with authorization code
    params = urlencode({"code": code, "state": state})
    return RedirectResponse(f"{redirect_uri}?{params}", status_code=302)


@app.post("/oauth/token")
async def token_exchange(
    grant_type: str = Form(...),
    code: str = Form(None),
    redirect_uri: str = Form(None),
    code_verifier: str = Form(None),
    client_id: str = Form(None),
    client_secret: str = Form(None),
    refresh_token: str = Form(None)
):
    """
    Token endpoint - exchanges authorization code for access token.

    Supports:
    - grant_type=authorization_code: Exchange code for token (with PKCE)
    - grant_type=refresh_token: Refresh an existing token
    """
    logger.info(f"Token request: grant_type={grant_type}, client_id={client_id}")

    if grant_type == "authorization_code":
        # Validate required parameters
        if not all([code, redirect_uri, code_verifier, client_id]):
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Missing required parameters"},
                status_code=400
            )

        # Validate client credentials if provided
        if client_secret and not token_store.validate_client_secret(client_id, client_secret):
            return JSONResponse(
                {"error": "invalid_client", "error_description": "Invalid client credentials"},
                status_code=401
            )

        # Retrieve and consume authorization code
        auth_code = token_store.consume_auth_code(code)
        if not auth_code:
            logger.warning("Invalid or expired authorization code")
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Invalid or expired authorization code"},
                status_code=400
            )

        # Validate client_id matches
        if auth_code.client_id != client_id:
            logger.warning(f"Client ID mismatch: {auth_code.client_id} != {client_id}")
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Client ID mismatch"},
                status_code=400
            )

        # Validate redirect_uri matches
        if auth_code.redirect_uri != redirect_uri:
            logger.warning(f"Redirect URI mismatch: {auth_code.redirect_uri} != {redirect_uri}")
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Redirect URI mismatch"},
                status_code=400
            )

        # Validate PKCE
        if not validate_pkce(code_verifier, auth_code.code_challenge):
            logger.warning("PKCE validation failed")
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "PKCE validation failed"},
                status_code=400
            )

        # Create tokens
        access_token, refresh_token_value, expires_in = token_store.create_access_token(
            client_id=auth_code.client_id,
            user_id=auth_code.user_id,
            user_email=auth_code.user_email,
            scopes=auth_code.scopes
        )

        logger.info(f"Issued access token for user {auth_code.user_id}")

        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "refresh_token": refresh_token_value,
            "scope": " ".join(auth_code.scopes)
        })

    elif grant_type == "refresh_token":
        if not refresh_token:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Missing refresh_token"},
                status_code=400
            )

        # Get refresh token data
        refresh_data = token_store.get_refresh_token(refresh_token)
        if not refresh_data:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Invalid refresh token"},
                status_code=400
            )

        # Create new access token
        access_token, _, expires_in = token_store.create_access_token(
            client_id=refresh_data.client_id,
            user_id=refresh_data.user_id,
            user_email=refresh_data.user_email,
            scopes=refresh_data.scopes
        )

        logger.info(f"Refreshed access token for user {refresh_data.user_id}")

        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "refresh_token": refresh_token,  # Return same refresh token
            "scope": " ".join(refresh_data.scopes)
        })

    return JSONResponse(
        {"error": "unsupported_grant_type"},
        status_code=400
    )


# =============================================================================
# FastMCP Server with OAuth-Protected Tools
# =============================================================================

mcp = FastMCP("Local OAuth Test Server")


def get_oauth_user() -> Optional[dict]:
    """
    Extract user info from OAuth Bearer token in Authorization header.

    Returns user dict if authenticated, None otherwise.
    """
    try:
        headers = get_http_headers()
        auth_header = headers.get('authorization') or headers.get('Authorization')

        if not auth_header:
            logger.debug("No Authorization header")
            return None

        if not auth_header.startswith('Bearer '):
            logger.debug("Authorization header doesn't start with 'Bearer '")
            return None

        token = auth_header[7:]
        token_data = token_store.validate_access_token(token)

        if not token_data:
            logger.debug("Invalid or expired access token")
            return None

        return {
            "user_id": token_data.user_id,
            "email": token_data.user_email,
            "scopes": token_data.scopes,
            "client_id": token_data.client_id
        }
    except Exception as e:
        logger.error(f"Error extracting OAuth user: {e}")
        return None


def require_oauth() -> dict:
    """
    Require OAuth authentication.

    Returns user dict if authenticated, raises PermissionError otherwise.
    """
    user = get_oauth_user()
    if not user:
        raise PermissionError(
            "OAuth authentication required. Please connect this service in Bond AI first."
        )
    return user


def require_scope(scope: str) -> dict:
    """
    Require OAuth authentication with a specific scope.

    Returns user dict if authenticated with scope, raises PermissionError otherwise.
    """
    user = require_oauth()
    if scope not in user["scopes"]:
        raise PermissionError(f"This action requires the '{scope}' scope.")
    return user


# =============================================================================
# MCP Tools (OAuth-Protected)
# =============================================================================

@mcp.tool()
def current_time() -> str:
    """
    Get the current server time.

    REQUIRES OAUTH AUTHENTICATION via Bond AI connection.
    """
    user = require_oauth()
    now = datetime.now().isoformat()
    logger.info(f"current_time called by {user['email']}")
    return f"Current time: {now} (authenticated as {user['email']})"


@mcp.tool()
def get_user_info() -> dict:
    """
    Get information about the authenticated user.

    REQUIRES OAUTH AUTHENTICATION via Bond AI connection.
    """
    user = require_oauth()
    logger.info(f"get_user_info called by {user['email']}")

    # Get full user info from store
    user_details = token_store.users.get(user["user_id"], {})

    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user_details.get("name", "Unknown"),
        "given_name": user_details.get("given_name"),
        "family_name": user_details.get("family_name"),
        "scopes": user["scopes"],
        "authenticated": True
    }


@mcp.tool()
def create_note(title: str, content: str) -> dict:
    """
    Create a note for the authenticated user.

    REQUIRES OAUTH AUTHENTICATION with 'write' scope.

    Args:
        title: The title of the note
        content: The content of the note
    """
    user = require_scope("write")
    logger.info(f"create_note called by {user['email']}: {title}")

    note_id = secrets.token_hex(8)
    return {
        "success": True,
        "note_id": note_id,
        "title": title,
        "content": content,
        "owner": user["email"],
        "created_at": datetime.now().isoformat()
    }


@mcp.tool()
def list_notes() -> dict:
    """
    List all notes for the authenticated user.

    REQUIRES OAUTH AUTHENTICATION with 'read' scope.
    """
    user = require_scope("read")
    logger.info(f"list_notes called by {user['email']}")

    # Return mock notes for testing
    return {
        "notes": [
            {"id": "note-001", "title": "Welcome", "preview": "Welcome to Local OAuth Test..."},
            {"id": "note-002", "title": "Test Note", "preview": "This is a test note..."}
        ],
        "total": 2,
        "owner": user["email"]
    }


# =============================================================================
# Mount MCP Server onto FastAPI
# =============================================================================

# Mount the FastMCP server at /mcp
app.mount("/mcp", mcp.http_app())


# =============================================================================
# Server Startup
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Local OAuth MCP Server for Bond AI Connection Testing")
    print("=" * 70)
    print()
    print("OAuth Endpoints:")
    print("  Authorization: http://localhost:5556/oauth/authorize")
    print("  Token:         http://localhost:5556/oauth/token")
    print("  Discovery:     http://localhost:5556/.well-known/oauth-authorization-server")
    print()
    print("MCP Endpoint:")
    print("  http://localhost:5556/mcp")
    print()
    print("Test Client Credentials:")
    print("  client_id:     local-oauth-client")
    print("  client_secret: local-oauth-secret")
    print()
    print("Test User:")
    print("  email: testuser@localtest.com")
    print("  name:  Test User")
    print()
    print("MCP Tools (require OAuth):")
    print("  - current_time()           : Get current time")
    print("  - get_user_info()          : Get authenticated user info")
    print("  - create_note(title, text) : Create a note (requires 'write' scope)")
    print("  - list_notes()             : List user's notes (requires 'read' scope)")
    print()
    print("Add to BOND_MCP_CONFIG in .env - see docstring at top of file")
    print("=" * 70)

    uvicorn.run(app, host="0.0.0.0", port=5556)
