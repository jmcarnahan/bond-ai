"""
Integration tests for the Connections OAuth flow.
Tests the authorization URL generation and configuration loading.
"""

import logging
import os
import pytest
import tempfile

logger = logging.getLogger(__name__)
from datetime import timedelta
from urllib.parse import urlparse, parse_qs

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='_connections_oauth.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key-for-oauth-testing')

# Import after setting environment
from fastapi.testclient import TestClient
from bondable.rest.main import app, create_access_token
from bondable.bond.config import Config


# Test configuration
TEST_USER_EMAIL = "oauth-test@example.com"
TEST_USER_ID = "oauth-test-user-123"


# --- Fixtures ---

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    """Clean up test database after session."""
    yield
    db_path = TEST_METADATA_DB_URL.replace("sqlite:///", "")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
def test_client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create authentication headers with JWT token."""
    token_data = {
        "sub": TEST_USER_EMAIL,
        "name": "OAuth Test User",
        "provider": "okta",
        "user_id": TEST_USER_ID
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    return {"Authorization": f"Bearer {access_token}"}


# --- Configuration Loading Tests ---

class TestConnectionConfigLoading:
    """Test that connection configs are loaded correctly"""

    def test_get_mcp_config_returns_servers(self):
        """Test that MCP config is loaded and contains servers"""
        config = Config.config()
        mcp_config = config.get_mcp_config()

        assert mcp_config is not None
        assert 'mcpServers' in mcp_config

        servers = mcp_config.get('mcpServers', {})
        logger.debug("MCP Servers found: %s", list(servers.keys()))

    def test_atlassian_config_structure(self):
        """Test that Atlassian config has expected structure"""
        config = Config.config()
        mcp_config = config.get_mcp_config()
        servers = mcp_config.get('mcpServers', {})

        if 'atlassian' not in servers:
            pytest.skip("Atlassian not configured in MCP servers")

        atlassian = servers['atlassian']
        logger.debug("Atlassian config: %s", atlassian)

        # Check required fields
        assert 'url' in atlassian, "Missing 'url' in Atlassian config"

        # Check auth_type
        auth_type = atlassian.get('auth_type')
        logger.debug("auth_type: %s", auth_type)

        if auth_type == 'oauth2':
            oauth_config = atlassian.get('oauth_config', {})
            print(f"[DEBUG] oauth_config has {len(oauth_config)} keys")

            # Check OAuth fields
            assert 'authorize_url' in oauth_config, "Missing 'authorize_url' in oauth_config"
            assert 'token_url' in oauth_config, "Missing 'token_url' in oauth_config"

            # These are the problematic ones - check if they exist
            client_id = oauth_config.get('client_id')
            scopes = oauth_config.get('scopes')
            print(f"[DEBUG] has_client_id: {client_id is not None}")
            print(f"[DEBUG] has_scopes: {scopes is not None}")

            if client_id is None:
                print("[WARNING] client_id is None - this will cause 'client_id=None' in auth URL!")


# --- Authorization URL Tests ---

class TestAuthorizationUrl:
    """Test authorization URL generation"""

    def test_authorize_atlassian_returns_url(self, test_client, auth_headers):
        """Test that authorizing Atlassian returns an authorization URL"""
        response = test_client.get("/connections/atlassian/authorize", headers=auth_headers)

        print(f"\n[DEBUG] Response status: {response.status_code}")
        print(f"[DEBUG] Response body: {response.json()}")

        if response.status_code == 404:
            pytest.skip("Atlassian connection not configured")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"

        data = response.json()
        assert 'authorization_url' in data
        auth_url = data['authorization_url']
        print(f"[DEBUG] Authorization URL: {auth_url}")

        # Parse the URL
        parsed = urlparse(auth_url)
        params = parse_qs(parsed.query)
        print(f"[DEBUG] URL params: {params}")

        # Check for problematic values
        client_id = params.get('client_id', [''])[0]
        if client_id == 'None' or client_id == '':
            print(f"[ERROR] client_id is invalid: '{client_id}'")

        # Validate URL structure
        assert parsed.scheme in ['http', 'https'], f"Invalid scheme: {parsed.scheme}"
        assert parsed.netloc, "Missing netloc"
        assert 'response_type' in params, "Missing response_type param"
        assert 'state' in params, "Missing state param"
        assert 'code_challenge' in params, "Missing code_challenge (PKCE)"

    def test_authorize_url_has_valid_client_id(self, test_client, auth_headers):
        """Test that authorization URL has a valid (non-None) client_id"""
        response = test_client.get("/connections/atlassian/authorize", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Atlassian connection not configured")

        data = response.json()
        auth_url = data['authorization_url']

        parsed = urlparse(auth_url)
        params = parse_qs(parsed.query)

        client_id = params.get('client_id', [''])[0]

        # This is the key assertion that catches the bug
        assert client_id != 'None', \
            "client_id is 'None' string - oauth_config.client_id is missing from MCP config!"
        assert client_id != '', \
            "client_id is empty - oauth_config.client_id is missing from MCP config!"

        print(f"[DEBUG] client_id: {client_id}")


# --- Connection List Tests ---

class TestConnectionsList:
    """Test connection listing includes OAuth2 connections"""

    def test_list_shows_oauth2_connections(self, test_client, auth_headers):
        """Test that list includes OAuth2 connections like Atlassian"""
        response = test_client.get("/connections", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        print(f"\n[DEBUG] Connections: {[c['name'] for c in data['connections']]}")

        # Find Atlassian
        atlassian = next(
            (c for c in data['connections'] if c['name'] == 'atlassian'),
            None
        )

        if atlassian:
            print(f"[DEBUG] Atlassian connection: {atlassian}")
            assert atlassian['auth_type'] == 'oauth2'
            assert atlassian['requires_authorization'] == (not atlassian['connected'])


# --- Configuration Fix Suggestions ---

class TestConfigurationDiagnostics:
    """Diagnostic tests to help identify configuration issues"""

    def test_print_current_config(self):
        """Print current MCP config for debugging"""
        config = Config.config()
        mcp_config = config.get_mcp_config()

        print("\n" + "=" * 60)
        print("CURRENT MCP CONFIGURATION")
        print("=" * 60)

        servers = mcp_config.get('mcpServers', {})
        for name, server_config in servers.items():
            logger.debug("[%s]", name)
            logger.debug("  url: %s", server_config.get('url'))
            logger.debug("  transport: %s", server_config.get('transport'))
            logger.debug("  auth_type: %s", server_config.get('auth_type'))

            if server_config.get('auth_type') == 'oauth2':
                oauth = server_config.get('oauth_config', {})
                print(f"  oauth_config:")
                print(f"    has_authorize_url: {bool(oauth.get('authorize_url'))}")
                print(f"    has_token_url: {bool(oauth.get('token_url'))}")
                print(f"    has_client_id: {bool(oauth.get('client_id'))}")
                print(f"    has_scopes: {bool(oauth.get('scopes'))}")
                print(f"    has_redirect_uri: {bool(oauth.get('redirect_uri'))}")

        print("\n" + "=" * 60)

    def test_suggest_config_fix(self):
        """Print suggested configuration fix"""
        print("\n" + "=" * 60)
        print("SUGGESTED ATLASSIAN MCP CONFIG FIX")
        print("=" * 60)
        print("""
The Atlassian MCP config is missing 'client_id'.

From the ATLASSIAN_MCP_INTEGRATION_SESSION.md:
- Client ID: yuhIYKIc2ZfVVRC6
- Required Redirect URI: http://localhost:5598/oauth/callback
- Scopes: openid email profile

IMPORTANT: Atlassian MCP requires redirect to localhost:5598
which is handled by mcp-remote tool. You may need to:
1. Run: npx -y mcp-remote https://mcp.atlassian.com/v1/sse
2. OR configure Bond to handle callbacks on port 5598

Update your .env BOND_MCP_CONFIG to:

"atlassian": {
    "url": "https://mcp.atlassian.com/v1/sse",
    "auth_type": "oauth2",
    "transport": "sse",
    "display_name": "Atlassian",
    "description": "Connect to Atlassian Jira and Confluence",
    "oauth_config": {
        "provider": "atlassian_mcp",
        "client_id": "yuhIYKIc2ZfVVRC6",
        "authorize_url": "https://mcp.atlassian.com/v1/authorize",
        "token_url": "https://cf.mcp.atlassian.com/v1/token",
        "scopes": "openid email profile",
        "redirect_uri": "http://localhost:5598/oauth/callback"
    },
    "cloud_id": "ec8ace41-7cde-4e66-aaf1-6fca83a00c53"
}
""")
        print("=" * 60)


# ===========================================================================
# Dynamic Origin Host for MCP Connections (ZPA / Multi-Domain)
# ===========================================================================

from unittest.mock import patch, MagicMock


class TestConnectionDynamicRedirect:
    """Test dynamic redirect URI in connection authorize and callback endpoints."""

    @pytest.fixture(autouse=True)
    def _mock_auth(self):
        """Override get_current_user to avoid S3/revocation-store calls."""
        from bondable.rest.dependencies.auth import get_current_user
        from bondable.rest.models.auth import User
        mock_user = User(user_id=TEST_USER_ID, email=TEST_USER_EMAIL, name="Test User", provider="okta", is_admin=False)
        app.dependency_overrides[get_current_user] = lambda: mock_user
        yield
        app.dependency_overrides.pop(get_current_user, None)

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "app.zpa.example.com"})
    def test_authorize_with_zpa_host_uses_dynamic_redirect(self, test_client, auth_headers):
        """When Host is a ZPA domain and no config redirect_uri, should build dynamic redirect."""
        # Mock the connection config to have NO redirect_uri
        mock_config = {
            "name": "microsoft",
            "auth_type": "oauth2",
            "oauth_authorize_url": "https://login.microsoftonline.com/authorize",
            "oauth_client_id": "test-client-id",
            "oauth_redirect_uri": None,  # No configured redirect
            "oauth_scopes": "openid email",
        }
        with patch("bondable.rest.routers.connections._get_connection_config", return_value=mock_config), \
             patch("bondable.rest.routers.connections._save_oauth_state", return_value=True) as mock_save:
            response = test_client.get(
                "/connections/microsoft/authorize",
                headers={**auth_headers, "host": "app.zpa.example.com"},
            )

            assert response.status_code == 200
            data = response.json()
            auth_url = data["authorization_url"]

            # The redirect_uri in the auth URL should point to the ZPA domain
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(auth_url)
            params = parse_qs(parsed.query)
            assert params["redirect_uri"][0] == "https://app.zpa.example.com/connections/microsoft/callback"

            # Verify origin_host was passed to _save_oauth_state
            mock_save.assert_called_once()
            call_kwargs = mock_save.call_args
            # origin_host is a keyword arg
            assert call_kwargs.kwargs.get("origin_host") == "app.zpa.example.com"

    @patch.dict(os.environ, {"ALLOWED_REDIRECT_DOMAINS": "app.dev.example.com"})
    def test_authorize_with_configured_redirect_uri_takes_precedence(self, test_client, auth_headers):
        """When config has explicit redirect_uri, it should be used over dynamic."""
        mock_config = {
            "name": "special",
            "auth_type": "oauth2",
            "oauth_authorize_url": "https://auth.special.com/authorize",
            "oauth_client_id": "test-client-id",
            "oauth_redirect_uri": "https://custom.example.com/callback",  # Explicit config
            "oauth_scopes": "openid",
        }
        with patch("bondable.rest.routers.connections._get_connection_config", return_value=mock_config), \
             patch("bondable.rest.routers.connections._save_oauth_state", return_value=True):
            response = test_client.get(
                "/connections/special/authorize",
                headers={**auth_headers, "host": "app.dev.example.com"},
            )

            assert response.status_code == 200
            auth_url = response.json()["authorization_url"]

            # Should use the configured redirect, NOT the dynamic one
            assert "redirect_uri=https%3A%2F%2Fcustom.example.com%2Fcallback" in auth_url

    def test_authorize_without_matching_host_falls_back_to_jwt_redirect(self, test_client, auth_headers):
        """When host is not in allowed domains and no config redirect, falls back to JWT_REDIRECT_URI."""
        mock_config = {
            "name": "databricks",
            "auth_type": "oauth2",
            "oauth_authorize_url": "https://databricks.com/authorize",
            "oauth_client_id": "test-client-id",
            "oauth_redirect_uri": None,
            "oauth_scopes": "all-apis",
        }
        with patch("bondable.rest.routers.connections._get_connection_config", return_value=mock_config), \
             patch("bondable.rest.routers.connections._save_oauth_state", return_value=True):
            response = test_client.get(
                "/connections/databricks/authorize",
                headers={**auth_headers, "host": "testserver"},
            )

            assert response.status_code == 200
            auth_url = response.json()["authorization_url"]

            # Should contain JWT_REDIRECT_URI-based callback (localhost in tests)
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(auth_url)
            params = parse_qs(parsed.query)
            redirect = params["redirect_uri"][0]
            assert "/connections/databricks/callback" in redirect
            assert "agentstudio" not in redirect  # Should NOT use an EKS/ZPA domain

    def test_callback_with_origin_host_redirects_to_origin_domain(self, test_client):
        """After token exchange, should redirect to the origin host's frontend."""
        mock_config = {
            "name": "microsoft",
            "auth_type": "oauth2",
            "oauth_token_url": "https://login.microsoftonline.com/token",
            "oauth_client_id": "test-client-id",
        }

        # Create a proper async mock for httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test_token", "token_type": "Bearer"}
        mock_response.raise_for_status = MagicMock()

        async def mock_post(*args, **kwargs):
            return mock_response

        mock_client_instance = MagicMock()
        mock_client_instance.post = mock_post

        async def mock_aenter(self):
            return mock_client_instance

        async def mock_aexit(self, *args):
            pass

        with patch("bondable.rest.routers.connections._get_and_delete_oauth_state") as mock_state, \
             patch("bondable.rest.routers.connections._get_connection_config", return_value=mock_config), \
             patch("bondable.rest.routers.connections.httpx.AsyncClient") as mock_httpx, \
             patch("bondable.rest.routers.connections.get_mcp_token_cache") as mock_cache, \
             patch("bondable.rest.routers.connections.is_safe_redirect_url", return_value=True):

            mock_state.return_value = {
                "user_id": TEST_USER_ID,
                "connection_name": "microsoft",
                "code_verifier": "test_verifier",
                "redirect_uri": "https://app.zpa.example.com/connections/microsoft/callback",
                "origin_host": "app.zpa.example.com",
            }

            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = mock_aenter
            mock_ctx.__aexit__ = mock_aexit
            mock_httpx.return_value = mock_ctx

            response = test_client.get(
                "/connections/microsoft/callback?code=test_code&state=test_state",
                follow_redirects=False,
            )

            assert response.status_code == 302
            location = response.headers["location"]
            # Should redirect to ZPA domain
            assert location.startswith("https://app.zpa.example.com/connections?connection_success=")

    def test_callback_without_origin_host_uses_default_frontend(self, test_client):
        """When no origin_host in state, should redirect to JWT_REDIRECT_URI."""
        mock_config = {
            "name": "microsoft",
            "auth_type": "oauth2",
            "oauth_token_url": "https://login.microsoftonline.com/token",
            "oauth_client_id": "test-client-id",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test_token", "token_type": "Bearer"}
        mock_response.raise_for_status = MagicMock()

        async def mock_post(*args, **kwargs):
            return mock_response

        mock_client_instance = MagicMock()
        mock_client_instance.post = mock_post

        async def mock_aenter(self):
            return mock_client_instance

        async def mock_aexit(self, *args):
            pass

        with patch("bondable.rest.routers.connections._get_and_delete_oauth_state") as mock_state, \
             patch("bondable.rest.routers.connections._get_connection_config", return_value=mock_config), \
             patch("bondable.rest.routers.connections.httpx.AsyncClient") as mock_httpx, \
             patch("bondable.rest.routers.connections.get_mcp_token_cache") as mock_cache, \
             patch("bondable.rest.routers.connections.is_safe_redirect_url", return_value=True):

            mock_state.return_value = {
                "user_id": TEST_USER_ID,
                "connection_name": "microsoft",
                "code_verifier": "test_verifier",
                "redirect_uri": "http://localhost:3004/connections/microsoft/callback",
                "origin_host": "",
            }

            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = mock_aenter
            mock_ctx.__aexit__ = mock_aexit
            mock_httpx.return_value = mock_ctx

            response = test_client.get(
                "/connections/microsoft/callback?code=test_code&state=test_state",
                follow_redirects=False,
            )

            assert response.status_code == 302
            location = response.headers["location"]
            # Should NOT redirect to a ZPA/EKS domain — uses JWT_REDIRECT_URI default
            assert "agentstudio" not in location


# Run with: poetry run pytest tests/test_connections_oauth_flow.py -v -s
