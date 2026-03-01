"""
Tests for Secrets Manager app config integration.

Covers:
- _load_app_config() caching, fallback, and error handling
- get_jwt_config() sourcing JWT secret from app config vs env var
- get_metadata_db_url() constructing URL from DATABASE_SECRET_ARN
- _get_okta_oauth2_config() / _get_cognito_oauth2_config() sourcing client IDs from app config
- _get_jwt_secret() in token_encryption.py falling back to app config
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock


class TestLoadAppConfig:
    """Test _load_app_config() caching and error handling."""

    def setup_method(self):
        """Reset the class-level cache before each test."""
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def teardown_method(self):
        """Clean up cache after each test."""
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def test_returns_empty_dict_when_env_var_not_set(self):
        """When APP_CONFIG_SECRET_NAME is not set, returns {} for local dev."""
        from bondable.bond.config import Config
        config = Config()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('APP_CONFIG_SECRET_NAME', None)
            result = config._load_app_config()
        assert result == {}

    def test_returns_parsed_secret_when_set(self):
        """When APP_CONFIG_SECRET_NAME is set, fetches and parses the secret."""
        from bondable.bond.config import Config
        secret_data = {
            'jwt_secret_key': 'test-jwt-key',
            'okta_client_id': 'test-okta-id',
            'okta_client_secret': 'test-value',  # nosec
            'cognito_client_id': 'test-cognito-id'
        }
        config = Config()
        with patch.dict(os.environ, {'APP_CONFIG_SECRET_NAME': 'test-secret', 'AWS_REGION': 'us-west-2'}):
            with patch.object(config, 'get_secret_value', return_value=json.dumps(secret_data)):
                result = config._load_app_config()
        assert result == secret_data

    def test_caches_result_across_calls(self):
        """Second call returns cached value without hitting Secrets Manager."""
        from bondable.bond.config import Config
        secret_data = {'jwt_secret_key': 'cached-secret'}
        config = Config()
        with patch.dict(os.environ, {'APP_CONFIG_SECRET_NAME': 'test-secret', 'AWS_REGION': 'us-west-2'}):
            with patch.object(config, 'get_secret_value', return_value=json.dumps(secret_data)) as mock_get:
                result1 = config._load_app_config()
                result2 = config._load_app_config()
        assert result1 == secret_data
        assert result2 == secret_data
        mock_get.assert_called_once()  # Only one Secrets Manager call

    def test_returns_empty_dict_on_secrets_manager_error(self):
        """On Secrets Manager failure, returns {} so callers can fall back to env vars."""
        from bondable.bond.config import Config
        config = Config()
        with patch.dict(os.environ, {'APP_CONFIG_SECRET_NAME': 'bad-secret', 'AWS_REGION': 'us-west-2'}):
            with patch.object(config, 'get_secret_value', side_effect=Exception("AccessDenied")):
                result = config._load_app_config()
        assert result == {}

    def test_returns_empty_dict_on_malformed_json(self):
        """On malformed JSON in secret, returns {} so callers can fall back."""
        from bondable.bond.config import Config
        config = Config()
        with patch.dict(os.environ, {'APP_CONFIG_SECRET_NAME': 'bad-json', 'AWS_REGION': 'us-west-2'}):
            with patch.object(config, 'get_secret_value', return_value='not-json{{{'):
                result = config._load_app_config()
        assert result == {}

    def test_caches_empty_dict_when_env_not_set(self):
        """Empty dict is cached too — no repeated env var lookups."""
        from bondable.bond.config import Config
        config = Config()
        os.environ.pop('APP_CONFIG_SECRET_NAME', None)
        config._load_app_config()
        assert Config._app_config_cache == {}
        # Second call should use cache
        Config._app_config_cache = {'injected': 'value'}
        result = config._load_app_config()
        assert result == {'injected': 'value'}  # Proves cache was used


class TestGetJwtConfig:
    """Test get_jwt_config() with app config secret vs env var."""

    def setup_method(self):
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def teardown_method(self):
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def test_uses_app_config_secret(self):
        """JWT secret from app config takes priority over env var."""
        from bondable.bond.config import Config
        config = Config()
        Config._app_config_cache = {'jwt_secret_key': 'from-secret'}
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'from-env'}):
            jwt_config = config.get_jwt_config()
        assert jwt_config.JWT_SECRET_KEY == 'from-secret'

    def test_falls_back_to_env_var(self):
        """When app config has no jwt_secret_key, falls back to env var."""
        from bondable.bond.config import Config
        config = Config()
        Config._app_config_cache = {}
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'from-env'}):
            jwt_config = config.get_jwt_config()
        assert jwt_config.JWT_SECRET_KEY == 'from-env'

    def test_raises_when_neither_source_has_secret(self):
        """Raises EnvironmentError when JWT secret is in neither source."""
        from bondable.bond.config import Config
        config = Config()
        Config._app_config_cache = {}
        env = os.environ.copy()
        env.pop('JWT_SECRET_KEY', None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(EnvironmentError, match="JWT secret not found"):
                config.get_jwt_config()


class TestGetMetadataDbUrl:
    """Test get_metadata_db_url() with env var, DATABASE_SECRET_ARN, and SQLite fallback."""

    def setup_method(self):
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def teardown_method(self):
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def test_uses_metadata_db_url_env_var(self):
        """Explicit METADATA_DB_URL env var takes priority (local dev)."""
        from bondable.bond.config import Config
        config = Config()
        with patch.dict(os.environ, {'METADATA_DB_URL': 'postgresql://localhost/mydb'}):
            result = config.get_metadata_db_url()
        assert result == 'postgresql://localhost/mydb'

    def test_constructs_url_from_database_secret(self):
        """Constructs PostgreSQL URL from DATABASE_SECRET_ARN secret."""
        from bondable.bond.config import Config
        db_secret = {
            'username': 'admin',
            'password': 'supersecret',
            'host': 'mydb.cluster-abc123.us-west-2.rds.amazonaws.com',
            'port': 5432,
            'dbname': 'bondai'
        }
        config = Config()
        env = os.environ.copy()
        env.pop('METADATA_DB_URL', None)
        env['DATABASE_SECRET_ARN'] = 'arn:aws:secretsmanager:us-west-2:123:secret:db-abc'
        env['AWS_REGION'] = 'us-west-2'
        with patch.dict(os.environ, env, clear=True):
            with patch.object(config, 'get_secret_value', return_value=json.dumps(db_secret)):
                result = config.get_metadata_db_url()
        assert result == 'postgresql://admin:supersecret@mydb.cluster-abc123.us-west-2.rds.amazonaws.com:5432/bondai?sslmode=require'

    def test_url_encodes_special_characters_in_password(self):
        """Passwords with special characters are URL-encoded."""
        from bondable.bond.config import Config
        db_secret = {
            'username': 'admin',
            'password': 'p@ss/word#123',
            'host': 'mydb.example.com',
            'port': 5432,
            'dbname': 'bondai'
        }
        config = Config()
        env = os.environ.copy()
        env.pop('METADATA_DB_URL', None)
        env['DATABASE_SECRET_ARN'] = 'arn:aws:secretsmanager:us-west-2:123:secret:db-abc'
        env['AWS_REGION'] = 'us-west-2'
        with patch.dict(os.environ, env, clear=True):
            with patch.object(config, 'get_secret_value', return_value=json.dumps(db_secret)):
                result = config.get_metadata_db_url()
        assert 'p%40ss%2Fword%23123' in result
        assert 'p@ss/word#123' not in result

    def test_falls_back_to_sqlite(self):
        """Falls back to SQLite when neither METADATA_DB_URL nor DATABASE_SECRET_ARN is set."""
        from bondable.bond.config import Config
        config = Config()
        env = os.environ.copy()
        env.pop('METADATA_DB_URL', None)
        env.pop('DATABASE_SECRET_ARN', None)
        with patch.dict(os.environ, env, clear=True):
            result = config.get_metadata_db_url()
        assert result == 'sqlite:////tmp/.metadata.db'

    def test_falls_back_to_sqlite_on_secret_error(self):
        """Falls back to SQLite when DATABASE_SECRET_ARN secret can't be read."""
        from bondable.bond.config import Config
        config = Config()
        env = os.environ.copy()
        env.pop('METADATA_DB_URL', None)
        env['DATABASE_SECRET_ARN'] = 'arn:aws:secretsmanager:us-west-2:123:secret:bad'
        env['AWS_REGION'] = 'us-west-2'
        with patch.dict(os.environ, env, clear=True):
            with patch.object(config, 'get_secret_value', side_effect=Exception("not found")):
                result = config.get_metadata_db_url()
        assert result == 'sqlite:////tmp/.metadata.db'

    def test_falls_back_to_sqlite_on_missing_fields(self):
        """Falls back to SQLite when secret is missing required fields."""
        from bondable.bond.config import Config
        config = Config()
        env = os.environ.copy()
        env.pop('METADATA_DB_URL', None)
        env['DATABASE_SECRET_ARN'] = 'arn:aws:secretsmanager:us-west-2:123:secret:incomplete'
        env['AWS_REGION'] = 'us-west-2'
        with patch.dict(os.environ, env, clear=True):
            with patch.object(config, 'get_secret_value', return_value=json.dumps({'username': 'admin'})):
                result = config.get_metadata_db_url()
        assert result == 'sqlite:////tmp/.metadata.db'


class TestOktaConfigFromAppConfig:
    """Test _get_okta_oauth2_config() sources from app config secret."""

    def setup_method(self):
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def teardown_method(self):
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def test_uses_app_config_for_client_id_and_secret(self):
        """Okta client_id and client_secret sourced from app config."""
        from bondable.bond.config import Config
        Config._app_config_cache = {
            'okta_client_id': 'id-from-secret',
            'okta_client_secret': 'secret-from-secret'
        }
        config = Config()
        with patch.dict(os.environ, {'OKTA_DOMAIN': 'https://test.okta.com'}):
            result = config._get_okta_oauth2_config()
        assert result['client_id'] == 'id-from-secret'
        assert result['client_secret'] == 'secret-from-secret'

    def test_falls_back_to_env_vars(self):
        """Falls back to env vars when app config is empty."""
        from bondable.bond.config import Config
        Config._app_config_cache = {}
        config = Config()
        with patch.dict(os.environ, {
            'OKTA_DOMAIN': 'https://test.okta.com',
            'OKTA_CLIENT_ID': 'id-from-env',
            'OKTA_CLIENT_SECRET': 'secret-from-env'
        }):
            result = config._get_okta_oauth2_config()
        assert result['client_id'] == 'id-from-env'
        assert result['client_secret'] == 'secret-from-env'

    def test_falls_back_to_okta_secret_name(self):
        """Falls back to OKTA_SECRET_NAME when app config and env vars are empty."""
        from bondable.bond.config import Config
        Config._app_config_cache = {}
        config = Config()
        env = {
            'OKTA_DOMAIN': 'https://test.okta.com',
            'OKTA_SECRET_NAME': 'my-okta-secret',
            'AWS_REGION': 'us-west-2'
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop('OKTA_CLIENT_ID', None)
            os.environ.pop('OKTA_CLIENT_SECRET', None)
            with patch.object(config, 'get_secret_value', return_value=json.dumps({'client_secret': 'from-sm'})):
                result = config._get_okta_oauth2_config()
        assert result['client_secret'] == 'from-sm'


class TestCognitoConfigFromAppConfig:
    """Test _get_cognito_oauth2_config() sources from app config secret."""

    def setup_method(self):
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def teardown_method(self):
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def test_uses_app_config_for_client_id(self):
        """Cognito client_id sourced from app config."""
        from bondable.bond.config import Config
        Config._app_config_cache = {'cognito_client_id': 'cog-id-from-secret'}
        config = Config()
        with patch.dict(os.environ, {'COGNITO_DOMAIN': 'https://test.auth.us-west-2.amazoncognito.com'}):
            result = config._get_cognito_oauth2_config()
        assert result['client_id'] == 'cog-id-from-secret'

    def test_falls_back_to_env_var(self):
        """Falls back to env var when app config is empty."""
        from bondable.bond.config import Config
        Config._app_config_cache = {}
        config = Config()
        with patch.dict(os.environ, {
            'COGNITO_DOMAIN': 'https://test.auth.us-west-2.amazoncognito.com',
            'COGNITO_CLIENT_ID': 'cog-id-from-env'
        }):
            result = config._get_cognito_oauth2_config()
        assert result['client_id'] == 'cog-id-from-env'


class TestGetMcpConfigFromAppConfig:
    """Test get_mcp_config() sources from app config secret vs env var."""

    def setup_method(self):
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def teardown_method(self):
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def test_uses_app_config_secret(self):
        """MCP config from app config secret takes priority over env var."""
        from bondable.bond.config import Config
        mcp_data = {"mcpServers": {"weather": {"url": "https://weather.example.com/mcp"}}}
        Config._app_config_cache = {'bond_mcp_config': mcp_data}
        config = Config()
        with patch.dict(os.environ, {'BOND_MCP_CONFIG': '{"mcpServers": {}}'}):
            result = config.get_mcp_config()
        assert result == mcp_data
        assert "weather" in result["mcpServers"]

    def test_falls_back_to_env_var(self):
        """Falls back to BOND_MCP_CONFIG env var when app config has no bond_mcp_config."""
        from bondable.bond.config import Config
        Config._app_config_cache = {}
        config = Config()
        env_config = '{"mcpServers": {"assistant": {"command": "python", "args": ["server.py"]}}}'
        with patch.dict(os.environ, {'BOND_MCP_CONFIG': env_config}):
            result = config.get_mcp_config()
        assert "assistant" in result["mcpServers"]

    def test_falls_back_to_default_when_no_source(self):
        """Falls back to default hello server when neither source has MCP config."""
        from bondable.bond.config import Config
        Config._app_config_cache = {}
        config = Config()
        env = os.environ.copy()
        env.pop('BOND_MCP_CONFIG', None)
        with patch.dict(os.environ, env, clear=True):
            result = config.get_mcp_config()
        assert "hello" in result["mcpServers"]

    def test_handles_invalid_env_var_json(self):
        """Returns empty config when BOND_MCP_CONFIG env var is invalid JSON."""
        from bondable.bond.config import Config
        Config._app_config_cache = {}
        config = Config()
        with patch.dict(os.environ, {'BOND_MCP_CONFIG': 'not-json{{{'}):
            result = config.get_mcp_config()
        assert result == {"mcpServers": {}}

    def test_app_config_with_multiple_servers(self):
        """App config with multiple MCP servers is returned correctly."""
        from bondable.bond.config import Config
        mcp_data = {
            "mcpServers": {
                "weather": {"url": "https://weather.example.com/mcp"},
                "assistant": {"command": "python", "args": ["server.py"]}
            }
        }
        Config._app_config_cache = {'bond_mcp_config': mcp_data}
        config = Config()
        result = config.get_mcp_config()
        assert len(result["mcpServers"]) == 2

    def test_empty_dict_bond_mcp_config_falls_through(self):
        """Empty dict bond_mcp_config (Terraform default) falls through to env var."""
        from bondable.bond.config import Config
        Config._app_config_cache = {'bond_mcp_config': {}}
        config = Config()
        env_config = '{"mcpServers": {"from_env": {"url": "https://env.example.com/mcp"}}}'
        with patch.dict(os.environ, {'BOND_MCP_CONFIG': env_config}):
            result = config.get_mcp_config()
        assert "from_env" in result["mcpServers"]

    def test_empty_dict_bond_mcp_config_no_env_var_uses_default(self):
        """Empty dict bond_mcp_config + no env var falls to default hello server."""
        from bondable.bond.config import Config
        Config._app_config_cache = {'bond_mcp_config': {}}
        config = Config()
        env = os.environ.copy()
        env.pop('BOND_MCP_CONFIG', None)
        with patch.dict(os.environ, env, clear=True):
            result = config.get_mcp_config()
        assert "hello" in result["mcpServers"]

    def test_secrets_manager_failure_falls_back_to_env_var(self):
        """When _load_app_config() fails, falls back to BOND_MCP_CONFIG env var."""
        from bondable.bond.config import Config
        config = Config()
        env_config = '{"mcpServers": {"fallback": {"url": "https://fallback.example.com/mcp"}}}'
        with patch.dict(os.environ, {'APP_CONFIG_SECRET_NAME': 'bad-secret', 'AWS_REGION': 'us-west-2', 'BOND_MCP_CONFIG': env_config}):
            with patch.object(config, 'get_secret_value', side_effect=Exception("AccessDenied")):
                result = config.get_mcp_config()
        assert "fallback" in result["mcpServers"]

    def test_production_shaped_config(self):
        """Config matching real production shape (url, transport, display_name, description)."""
        from bondable.bond.config import Config
        mcp_data = {
            "mcpServers": {
                "sbel": {
                    "url": "https://example.us-west-2.awsapprunner.com/mcp",
                    "transport": "streamable-http",
                    "display_name": "SBEL Lending Data",
                    "description": "Query loan products across lenders"
                }
            }
        }
        Config._app_config_cache = {'bond_mcp_config': mcp_data}
        config = Config()
        result = config.get_mcp_config()
        assert result["mcpServers"]["sbel"]["transport"] == "streamable-http"
        assert result["mcpServers"]["sbel"]["display_name"] == "SBEL Lending Data"


class TestTokenEncryptionJwtFallback:
    """Test _get_jwt_secret() in token_encryption.py falls back to app config."""

    def setup_method(self):
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def teardown_method(self):
        from bondable.bond.config import Config
        Config._app_config_cache = None

    def test_uses_env_var_when_set(self):
        """Returns JWT_SECRET_KEY env var when present."""
        from bondable.bond.auth.token_encryption import _get_jwt_secret
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'env-secret'}):
            result = _get_jwt_secret()
        assert result == 'env-secret'

    def test_falls_back_to_app_config(self):
        """Falls back to app config secret when env var is absent."""
        from bondable.bond.config import Config
        from bondable.bond.auth.token_encryption import _get_jwt_secret
        Config._app_config_cache = {'jwt_secret_key': 'secret-from-app-config'}
        env = os.environ.copy()
        env.pop('JWT_SECRET_KEY', None)
        with patch.dict(os.environ, env, clear=True):
            result = _get_jwt_secret()
        assert result == 'secret-from-app-config'

    def test_raises_when_neither_source_has_secret(self):
        """Raises TokenEncryptionError when JWT secret is nowhere."""
        from bondable.bond.config import Config
        from bondable.bond.auth.token_encryption import _get_jwt_secret, TokenEncryptionError
        Config._app_config_cache = {}
        env = os.environ.copy()
        env.pop('JWT_SECRET_KEY', None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(TokenEncryptionError, match="JWT secret not found"):
                _get_jwt_secret()
