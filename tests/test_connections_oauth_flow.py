"""
Integration tests for the Connections OAuth flow.
Tests the authorization URL generation and configuration loading.
"""

import os
import pytest
import tempfile
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
        print(f"\n[DEBUG] MCP Servers found: {list(servers.keys())}")

    def test_atlassian_config_structure(self):
        """Test that Atlassian config has expected structure"""
        config = Config.config()
        mcp_config = config.get_mcp_config()
        servers = mcp_config.get('mcpServers', {})

        if 'atlassian' not in servers:
            pytest.skip("Atlassian not configured in MCP servers")

        atlassian = servers['atlassian']
        print(f"\n[DEBUG] Atlassian config: {atlassian}")

        # Check required fields
        assert 'url' in atlassian, "Missing 'url' in Atlassian config"

        # Check auth_type
        auth_type = atlassian.get('auth_type')
        print(f"[DEBUG] auth_type: {auth_type}")

        if auth_type == 'oauth2':
            oauth_config = atlassian.get('oauth_config', {})
            print(f"[DEBUG] oauth_config keys: {list(oauth_config.keys())}")

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
            print(f"\n[{name}]")
            print(f"  url: {server_config.get('url')}")
            print(f"  transport: {server_config.get('transport')}")
            print(f"  auth_type: {server_config.get('auth_type')}")

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


# Run with: poetry run pytest tests/test_connections_oauth_flow.py -v -s
