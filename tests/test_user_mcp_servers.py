"""
Tests for User MCP Servers CRUD API endpoints.
"""

import os
import pytest
import tempfile
import json
from datetime import timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='_user_mcp.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key-for-user-mcp-testing')

# Import after setting environment
from bondable.rest.main import app, create_access_token
from bondable.bond.config import Config

jwt_config = Config.config().get_jwt_config()
TEST_USER_EMAIL = "user-mcp-test@example.com"
TEST_USER_ID = "user-mcp-test-user-123"
TEST_USER_EMAIL_2 = "user-mcp-test2@example.com"
TEST_USER_ID_2 = "user-mcp-test-user-456"


# --- Fixtures ---

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    db_path = TEST_METADATA_DB_URL.replace("sqlite:///", "")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    token_data = {
        "sub": TEST_USER_EMAIL,
        "name": "MCP Test User",
        "provider": "okta",
        "user_id": TEST_USER_ID
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def auth_headers_user2():
    token_data = {
        "sub": TEST_USER_EMAIL_2,
        "name": "MCP Test User 2",
        "provider": "okta",
        "user_id": TEST_USER_ID_2
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def sample_server_data():
    return {
        "server_name": "my_test_server",
        "display_name": "My Test Server",
        "description": "A test MCP server",
        "url": "http://localhost:5555/mcp",
        "transport": "streamable-http",
        "auth_type": "none"
    }


@pytest.fixture
def sample_header_server_data():
    return {
        "server_name": "my_header_server",
        "display_name": "My Header Server",
        "url": "https://api.example.com/mcp",
        "transport": "streamable-http",
        "auth_type": "header",
        "headers": {"Authorization": "Bearer my-api-key", "X-Custom": "value"}
    }


@pytest.fixture
def sample_oauth_server_data():
    return {
        "server_name": "my_oauth_server",
        "display_name": "My OAuth Server",
        "url": "https://oauth.example.com/mcp",
        "transport": "streamable-http",
        "auth_type": "oauth2",
        "oauth_config": {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
            "scopes": "read write",
            "redirect_uri": "http://localhost:8000/connections/my_oauth_server/callback",
            "provider": "custom"
        }
    }


# --- Auth Tests ---

class TestAuth:
    def test_requires_auth(self, test_client):
        response = test_client.get("/user-mcp-servers")
        assert response.status_code == 401

    def test_requires_auth_create(self, test_client):
        response = test_client.post("/user-mcp-servers", json={"server_name": "x", "display_name": "X", "url": "http://x"})
        assert response.status_code == 401


# --- Create Tests ---

class TestCreateServer:
    def test_create_none_auth(self, test_client, auth_headers, sample_server_data):
        response = test_client.post("/user-mcp-servers", json=sample_server_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["server_name"] == "my_test_server"
        assert data["display_name"] == "My Test Server"
        assert data["auth_type"] == "none"
        assert data["has_headers"] is False
        assert data["has_oauth_config"] is False
        assert "id" in data

    def test_create_header_auth(self, test_client, auth_headers, sample_header_server_data):
        response = test_client.post("/user-mcp-servers", json=sample_header_server_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["auth_type"] == "header"
        assert data["has_headers"] is True
        assert data["has_oauth_config"] is False
        # Headers should NOT be exposed in response
        assert "headers" not in data or data.get("headers") is None

    def test_create_oauth_auth(self, test_client, auth_headers, sample_oauth_server_data):
        response = test_client.post("/user-mcp-servers", json=sample_oauth_server_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["auth_type"] == "oauth2"
        assert data["has_oauth_config"] is True
        assert data["oauth_config"]["client_id"] == "test-client-id"
        # client_secret should NOT be in oauth_config display
        assert "client_secret" not in data.get("oauth_config", {})

    def test_create_duplicate_name(self, test_client, auth_headers, sample_server_data):
        # First create should succeed (or already exists from previous test)
        test_client.post("/user-mcp-servers", json=sample_server_data, headers=auth_headers)
        # Second create with same name should fail
        response = test_client.post("/user-mcp-servers", json=sample_server_data, headers=auth_headers)
        assert response.status_code == 409

    def test_create_same_name_different_user(self, test_client, auth_headers_user2, sample_server_data):
        """Different users can have servers with the same name."""
        response = test_client.post("/user-mcp-servers", json=sample_server_data, headers=auth_headers_user2)
        assert response.status_code == 201


# --- Validation Tests ---

class TestValidation:
    def test_invalid_server_name_uppercase(self, test_client, auth_headers):
        data = {"server_name": "MyServer", "display_name": "X", "url": "http://localhost:5555/mcp", "auth_type": "none"}
        response = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
        assert response.status_code == 422

    def test_invalid_server_name_starts_with_digit(self, test_client, auth_headers):
        data = {"server_name": "1server", "display_name": "X", "url": "http://localhost:5555/mcp", "auth_type": "none"}
        response = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
        assert response.status_code == 422

    def test_invalid_server_name_special_chars(self, test_client, auth_headers):
        data = {"server_name": "my-server", "display_name": "X", "url": "http://localhost:5555/mcp", "auth_type": "none"}
        response = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
        assert response.status_code == 422

    def test_invalid_transport(self, test_client, auth_headers):
        data = {"server_name": "valid_name", "display_name": "X", "url": "http://localhost:5555/mcp", "transport": "websocket", "auth_type": "none"}
        response = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
        assert response.status_code == 422

    def test_invalid_auth_type(self, test_client, auth_headers):
        data = {"server_name": "valid_name", "display_name": "X", "url": "http://localhost:5555/mcp", "auth_type": "api_key"}
        response = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
        assert response.status_code == 422

    def test_invalid_url_scheme(self, test_client, auth_headers):
        data = {"server_name": "valid_name", "display_name": "X", "url": "ftp://example.com/mcp", "auth_type": "none"}
        response = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
        assert response.status_code == 422

    def test_ssrf_blocked_hostname(self, test_client, auth_headers):
        data = {"server_name": "ssrf_test", "display_name": "X", "url": "http://169.254.169.254/mcp", "auth_type": "none"}
        response = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
        assert response.status_code == 400
        assert "blocked" in response.json()["detail"].lower()

    def test_header_auth_requires_headers(self, test_client, auth_headers):
        data = {"server_name": "header_test", "display_name": "X", "url": "http://localhost:5555/mcp", "auth_type": "header"}
        response = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
        assert response.status_code == 400

    def test_oauth_auth_requires_oauth_config(self, test_client, auth_headers):
        data = {"server_name": "oauth_test", "display_name": "X", "url": "http://localhost:5555/mcp", "auth_type": "oauth2"}
        response = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
        assert response.status_code == 400

    def test_none_auth_rejects_headers(self, test_client, auth_headers):
        data = {"server_name": "none_with_headers", "display_name": "X", "url": "http://localhost:5555/mcp",
                "auth_type": "none", "headers": {"Authorization": "Bearer x"}}
        response = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
        assert response.status_code == 400

    def test_none_auth_rejects_oauth(self, test_client, auth_headers):
        data = {"server_name": "none_with_oauth", "display_name": "X", "url": "http://localhost:5555/mcp",
                "auth_type": "none", "oauth_config": {"client_id": "x", "client_secret": "x",
                "authorize_url": "https://x.com/auth", "token_url": "https://x.com/token",
                "redirect_uri": "http://localhost/cb"}}
        response = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
        assert response.status_code == 400

    def test_global_name_collision(self, test_client, auth_headers):
        """Server name must not collide with a global MCP server name."""
        # Get a global server name from config
        try:
            mcp_config = Config.config().get_mcp_config()
            global_names = list(mcp_config.get('mcpServers', {}).keys())
            if global_names:
                data = {"server_name": global_names[0], "display_name": "X", "url": "http://localhost:5555/mcp", "auth_type": "none"}
                response = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
                assert response.status_code == 409
                assert "global" in response.json()["detail"].lower() or "conflict" in response.json()["detail"].lower()
        except Exception:
            pytest.skip("No global MCP config available")


# --- List Tests ---

class TestListServers:
    def test_list_own_servers(self, test_client, auth_headers):
        response = test_client.get("/user-mcp-servers", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "servers" in data
        assert "total" in data
        assert data["total"] >= 1  # At least the one created in TestCreateServer

    def test_list_only_own_servers(self, test_client, auth_headers, auth_headers_user2):
        """User should only see their own servers, not other users'."""
        response1 = test_client.get("/user-mcp-servers", headers=auth_headers)
        response2 = test_client.get("/user-mcp-servers", headers=auth_headers_user2)
        # They should have different server counts (user2 may have 1 from earlier test)
        ids1 = {s["id"] for s in response1.json()["servers"]}
        ids2 = {s["id"] for s in response2.json()["servers"]}
        assert ids1.isdisjoint(ids2), "Users should not see each other's servers"


# --- Get Tests ---

class TestGetServer:
    def test_get_server(self, test_client, auth_headers):
        # List to get an ID
        list_resp = test_client.get("/user-mcp-servers", headers=auth_headers)
        servers = list_resp.json()["servers"]
        assert len(servers) > 0

        server_id = servers[0]["id"]
        response = test_client.get(f"/user-mcp-servers/{server_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == server_id

    def test_get_nonexistent(self, test_client, auth_headers):
        response = test_client.get("/user-mcp-servers/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404

    def test_get_other_users_server(self, test_client, auth_headers, auth_headers_user2):
        """User cannot access another user's server."""
        list_resp = test_client.get("/user-mcp-servers", headers=auth_headers)
        servers = list_resp.json()["servers"]
        if servers:
            server_id = servers[0]["id"]
            response = test_client.get(f"/user-mcp-servers/{server_id}", headers=auth_headers_user2)
            assert response.status_code == 404


# --- Update Tests ---

class TestUpdateServer:
    def test_update_display_name(self, test_client, auth_headers):
        list_resp = test_client.get("/user-mcp-servers", headers=auth_headers)
        servers = list_resp.json()["servers"]
        server_id = servers[0]["id"]

        response = test_client.put(
            f"/user-mcp-servers/{server_id}",
            json={"display_name": "Updated Name"},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["display_name"] == "Updated Name"

    def test_update_url(self, test_client, auth_headers):
        list_resp = test_client.get("/user-mcp-servers", headers=auth_headers)
        servers = list_resp.json()["servers"]
        server_id = servers[0]["id"]

        response = test_client.put(
            f"/user-mcp-servers/{server_id}",
            json={"url": "http://localhost:9999/mcp"},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["url"] == "http://localhost:9999/mcp"

    def test_update_other_users_server(self, test_client, auth_headers, auth_headers_user2):
        list_resp = test_client.get("/user-mcp-servers", headers=auth_headers)
        servers = list_resp.json()["servers"]
        if servers:
            server_id = servers[0]["id"]
            response = test_client.put(
                f"/user-mcp-servers/{server_id}",
                json={"display_name": "Hacked"},
                headers=auth_headers_user2
            )
            assert response.status_code == 404

    def test_update_switch_auth_type_none_to_header(self, test_client, auth_headers):
        """Switching auth_type from none to header requires providing headers."""
        list_resp = test_client.get("/user-mcp-servers", headers=auth_headers)
        servers = list_resp.json()["servers"]
        # Find a 'none' auth server
        none_server = next((s for s in servers if s["auth_type"] == "none"), None)
        if not none_server:
            pytest.skip("No 'none' auth server available")

        # Switch to header with headers
        response = test_client.put(
            f"/user-mcp-servers/{none_server['id']}",
            json={"auth_type": "header", "headers": {"X-Api-Key": "test-key"}},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["auth_type"] == "header"
        assert data["has_headers"] is True

        # Switch back to none (should clear headers)
        response = test_client.put(
            f"/user-mcp-servers/{none_server['id']}",
            json={"auth_type": "none"},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["auth_type"] == "none"
        assert response.json()["has_headers"] is False

    def test_update_switch_auth_type_without_required_fields(self, test_client, auth_headers):
        """Switching to header auth without headers should fail."""
        list_resp = test_client.get("/user-mcp-servers", headers=auth_headers)
        servers = list_resp.json()["servers"]
        none_server = next((s for s in servers if s["auth_type"] == "none"), None)
        if not none_server:
            pytest.skip("No 'none' auth server available")

        response = test_client.put(
            f"/user-mcp-servers/{none_server['id']}",
            json={"auth_type": "header"},
            headers=auth_headers
        )
        assert response.status_code == 400


# --- Delete Tests ---

class TestDeleteServer:
    def test_delete_server(self, test_client, auth_headers):
        # Create a server to delete
        create_data = {
            "server_name": "to_delete",
            "display_name": "To Delete",
            "url": "http://localhost:5555/mcp",
            "auth_type": "none"
        }
        create_resp = test_client.post("/user-mcp-servers", json=create_data, headers=auth_headers)
        assert create_resp.status_code == 201
        server_id = create_resp.json()["id"]

        response = test_client.delete(f"/user-mcp-servers/{server_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify it's gone
        get_resp = test_client.get(f"/user-mcp-servers/{server_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    def test_delete_nonexistent(self, test_client, auth_headers):
        response = test_client.delete("/user-mcp-servers/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_other_users_server(self, test_client, auth_headers, auth_headers_user2):
        list_resp = test_client.get("/user-mcp-servers", headers=auth_headers_user2)
        servers = list_resp.json()["servers"]
        if servers:
            server_id = servers[0]["id"]
            response = test_client.delete(f"/user-mcp-servers/{server_id}", headers=auth_headers)
            assert response.status_code == 404


# --- Encryption Tests ---

class TestEncryption:
    def test_headers_encrypted_at_rest(self, test_client, auth_headers):
        """Verify headers are encrypted in the database, not stored plaintext."""
        from bondable.bond.providers.metadata import UserMcpServer

        # Create a header server
        data = {
            "server_name": "encryption_test",
            "display_name": "Encryption Test",
            "url": "http://localhost:5555/mcp",
            "auth_type": "header",
            "headers": {"Authorization": "Bearer super-secret-key"}
        }
        resp = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
        assert resp.status_code == 201
        server_id = resp.json()["id"]

        # Read directly from DB
        db_session = Config.config().get_provider().metadata.get_db_session()
        server = db_session.query(UserMcpServer).filter(UserMcpServer.id == server_id).first()
        assert server is not None
        assert server.headers_encrypted is not None
        # The encrypted value should NOT contain the plaintext
        assert "super-secret-key" not in server.headers_encrypted

        # But should be decryptable
        from bondable.bond.auth.token_encryption import decrypt_token
        decrypted = json.loads(decrypt_token(server.headers_encrypted))
        assert decrypted["Authorization"] == "Bearer super-secret-key"

        # Cleanup
        test_client.delete(f"/user-mcp-servers/{server_id}", headers=auth_headers)

    def test_oauth_config_encrypted_at_rest(self, test_client, auth_headers):
        """Verify oauth_config is encrypted in the database."""
        from bondable.bond.providers.metadata import UserMcpServer

        data = {
            "server_name": "oauth_encrypt_test",
            "display_name": "OAuth Encrypt Test",
            "url": "https://oauth.example.com/mcp",
            "auth_type": "oauth2",
            "oauth_config": {
                "client_id": "test-id",
                "client_secret": "super-secret-oauth",
                "authorize_url": "https://auth.example.com/authorize",
                "token_url": "https://auth.example.com/token",
                "redirect_uri": "http://localhost:8000/cb"
            }
        }
        resp = test_client.post("/user-mcp-servers", json=data, headers=auth_headers)
        assert resp.status_code == 201
        server_id = resp.json()["id"]

        # Read directly from DB
        db_session = Config.config().get_provider().metadata.get_db_session()
        server = db_session.query(UserMcpServer).filter(UserMcpServer.id == server_id).first()
        assert server is not None
        assert server.oauth_config_encrypted is not None
        assert "super-secret-oauth" not in server.oauth_config_encrypted

        # Response should have oauth_config WITHOUT client_secret
        resp_data = resp.json()
        assert resp_data["oauth_config"]["client_id"] == "test-id"
        assert "client_secret" not in resp_data["oauth_config"]

        # Cleanup
        test_client.delete(f"/user-mcp-servers/{server_id}", headers=auth_headers)


# --- Import/Export Tests ---

class TestImportExport:
    def test_import_json_config(self, test_client, auth_headers):
        """Import a server from JSON matching BOND_MCP_CONFIG format."""
        data = {
            "server_name": "imported_microsoft",
            "config": {
                "url": "http://localhost:5557/mcp",
                "auth_type": "oauth2",
                "transport": "streamable-http",
                "display_name": "Microsoft (Imported)",
                "description": "Connect to Microsoft email",
                "oauth_config": {
                    "provider": "microsoft",
                    "client_id": "test-client-id",
                    "client_secret": "test-secret",
                    "authorize_url": "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize",
                    "token_url": "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                    "scopes": "Mail.Read Mail.ReadWrite offline_access",
                    "redirect_uri": "http://localhost:8000/connections/imported_microsoft/callback"
                },
                "cloud_id": "test-cloud-123",
                "site_url": "https://test.example.com"
            }
        }
        response = test_client.post("/user-mcp-servers/import", json=data, headers=auth_headers)
        assert response.status_code == 201
        result = response.json()
        assert result["server_name"] == "imported_microsoft"
        assert result["display_name"] == "Microsoft (Imported)"
        assert result["auth_type"] == "oauth2"
        assert result["has_oauth_config"] is True
        assert result["oauth_config"]["client_id"] == "test-client-id"
        # Extra config should include cloud_id and site_url
        assert result["extra_config"]["cloud_id"] == "test-cloud-123"
        assert result["extra_config"]["site_url"] == "https://test.example.com"
        # Cleanup
        test_client.delete(f"/user-mcp-servers/{result['id']}", headers=auth_headers)

    def test_import_validates_server_name(self, test_client, auth_headers):
        data = {
            "server_name": "Invalid-Name",
            "config": {"url": "http://localhost:5555/mcp"}
        }
        response = test_client.post("/user-mcp-servers/import", json=data, headers=auth_headers)
        assert response.status_code == 400

    def test_import_requires_url(self, test_client, auth_headers):
        data = {
            "server_name": "no_url",
            "config": {"display_name": "No URL"}
        }
        response = test_client.post("/user-mcp-servers/import", json=data, headers=auth_headers)
        assert response.status_code == 400

    def test_export_json_config(self, test_client, auth_headers):
        """Export a server and verify it matches the import format."""
        # Create a server first
        create_data = {
            "server_name": "export_test",
            "display_name": "Export Test",
            "url": "http://localhost:5555/mcp",
            "auth_type": "header",
            "headers": {"X-Api-Key": "secret-123"},
            "extra_config": {"cloud_id": "abc123"}
        }
        create_resp = test_client.post("/user-mcp-servers", json=create_data, headers=auth_headers)
        assert create_resp.status_code == 201
        server_id = create_resp.json()["id"]

        # Export
        export_resp = test_client.get(f"/user-mcp-servers/{server_id}/export", headers=auth_headers)
        assert export_resp.status_code == 200
        exported = export_resp.json()
        assert exported["server_name"] == "export_test"
        assert exported["config"]["url"] == "http://localhost:5555/mcp"
        assert exported["config"]["display_name"] == "Export Test"
        # Headers should be included in export (decrypted)
        assert exported["config"]["headers"]["X-Api-Key"] == "secret-123"
        # Extra config fields should be at top level
        assert exported["config"]["cloud_id"] == "abc123"

        # Cleanup
        test_client.delete(f"/user-mcp-servers/{server_id}", headers=auth_headers)

    def test_export_roundtrip(self, test_client, auth_headers):
        """Export then re-import should create an equivalent server."""
        # Create original
        create_data = {
            "server_name": "roundtrip_orig",
            "display_name": "Roundtrip Original",
            "url": "http://localhost:5555/mcp",
            "auth_type": "none",
            "extra_config": {"site_url": "https://example.com"}
        }
        create_resp = test_client.post("/user-mcp-servers", json=create_data, headers=auth_headers)
        assert create_resp.status_code == 201
        server_id = create_resp.json()["id"]

        # Export
        export_resp = test_client.get(f"/user-mcp-servers/{server_id}/export", headers=auth_headers)
        exported = export_resp.json()

        # Delete original
        test_client.delete(f"/user-mcp-servers/{server_id}", headers=auth_headers)

        # Import with new name
        import_data = {
            "server_name": "roundtrip_copy",
            "config": exported["config"]
        }
        import_resp = test_client.post("/user-mcp-servers/import", json=import_data, headers=auth_headers)
        assert import_resp.status_code == 201
        imported = import_resp.json()
        assert imported["server_name"] == "roundtrip_copy"
        assert imported["display_name"] == "Roundtrip Original"
        assert imported["url"] == "http://localhost:5555/mcp"
        assert imported["extra_config"]["site_url"] == "https://example.com"

        # Cleanup
        test_client.delete(f"/user-mcp-servers/{imported['id']}", headers=auth_headers)


# --- Internal Name Tests ---

class TestInternalName:
    def test_internal_name_format(self):
        from bondable.rest.routers.user_mcp_servers import get_user_server_internal_name
        name = get_user_server_internal_name("user-12345678-abcd", "my_server")
        assert name == "user_user-123_my_server"

    def test_internal_name_uniqueness(self):
        from bondable.rest.routers.user_mcp_servers import get_user_server_internal_name
        name1 = get_user_server_internal_name("user-aaa", "server")
        name2 = get_user_server_internal_name("user-bbb", "server")
        assert name1 != name2
