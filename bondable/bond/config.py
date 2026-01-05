import logging
LOGGER = logging.getLogger(__name__)

from dotenv import load_dotenv
import os
import atexit
import json
import base64
import importlib
from google.cloud import secretmanager
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from bondable.bond.cache import bond_cache
import google.auth

load_dotenv()

from typing import Type, TypeVar
T = TypeVar("T")

class Config:
    
    provider = None
    secrets = None
    project_id = None

    def __init__(self): 
        atexit.register(self.__del__)
        LOGGER.info("Created Config instance")

    def __del__(self):
        LOGGER.info("Closing Config instance")
        try:
            if hasattr(self, 'secrets') and self.secrets is not None:
                self.secrets.transport.close()
        except Exception as e:
            LOGGER.error(f"Error closing Config instance {e}")
        finally:
            self.secrets = None

    # config should init with a service account
    # this should either be a base64 string or a file 
    # both coming in via a env var
    def get_secrets_client(self):
        """Initialize GCP credentials and secrets client on first use."""
        if self.secrets is not None:
            return self.secrets
        
        try:
            if 'GCLOUD_SA_CREDS_STRING' in os.environ:
                sa_creds_base64 = os.getenv("GCLOUD_SA_CREDS_STRING") # this is a bas64 string
                sa_creds = base64.b64decode(sa_creds_base64).decode("utf-8")
                credentials = service_account.Credentials.from_service_account_info(json.loads(sa_creds))
                self.project_id = os.getenv('GCLOUD_PROJECT_ID', credentials.project_id)
                self.secrets = secretmanager.SecretManagerServiceClient(credentials=credentials)
                LOGGER.info(f"Using GCLOUD credentials from GCLOUD_SA_CREDS_STRING for project_id: {self.project_id}")
            elif 'GCLOUD_SA_CREDS_PATH' in os.environ:
                sa_creds_path = os.getenv('GCLOUD_SA_CREDS_PATH')
                credentials = service_account.Credentials.from_service_account_file(sa_creds_path)
                self.project_id = os.getenv('GCLOUD_PROJECT_ID', credentials.project_id)
                self.secrets = secretmanager.SecretManagerServiceClient(credentials=credentials)
                LOGGER.info(f"Using GCLOUD credentials from GCLOUD_SA_CREDS_PATH for project_id: {self.project_id}")
            else:
                credentials, project_id = google.auth.default()
                self.project_id = os.getenv('GCLOUD_PROJECT_ID', project_id)
                self.secrets = secretmanager.SecretManagerServiceClient(credentials=credentials)
                LOGGER.info(f"Using GCLOUD default credentials for project_id: {self.project_id}")

            return self.secrets
            
        except Exception as e:
            LOGGER.error(f"Error loading GCP credentials: {e}")
            raise e



    def get_class_from_env(self, env_var: str, default: str, expected_type: Type[T]) -> T:
        path = os.getenv(env_var, default)
        LOGGER.info(f"Using provider class: {path}")

        try:
            module_path, class_name = path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            LOGGER.info(f"Loaded provider class: {cls}")
            
            if not issubclass(cls, expected_type):
                raise TypeError(f"Class {path} is not a subclass of {expected_type.__name__}")
            
            return cls
        except (ImportError, AttributeError, TypeError) as e:
            LOGGER.error(f"Failed to load or validate class {path}: {e}")
            raise


    def get_secret_value(self, secret_id, default=""):
        # Check if we're using AWS
        aws_region = os.getenv('AWS_REGION', '')
        if aws_region:
            # Use AWS Secrets Manager
            try:
                import boto3
                client = boto3.client('secretsmanager', region_name=aws_region)
                response = client.get_secret_value(SecretId=secret_id)
                return response['SecretString']
            except Exception as e:
                LOGGER.error(f"Error getting AWS secret value {secret_id}: {e}")
                return default
        else:
            # Use GCP Secrets Manager
            try:
                secrets = self.get_secrets_client()
                secret_name = f"projects/{self.project_id}/secrets/{secret_id}/versions/latest"
                response = secrets.access_secret_version(name=secret_name)
                return response.payload.data.decode("UTF-8")
            except Exception as e:
                LOGGER.error(f"Error getting GCP secret value {secret_id}: {e}")
                return default

    @classmethod
    @bond_cache
    def config(cls):
        return Config()
    
    def get_provider(self):
        """
        Have to lazy init the provider here to avoid circular imports.
        """
        if self.provider is None:
            from bondable.bond.providers.provider import Provider
            provider_class = self.get_class_from_env('BOND_PROVIDER_CLASS', 'bondable.bond.providers.openai.OAIAProvider.OAIAProvider', Provider)
            method = getattr(provider_class, 'provider', None)
            if method is None:
                return False
            self.provider = method()
            # Initialize Groups and Users if not already done
            if self.provider.groups is None:
                from bondable.bond.groups import Groups
                self.provider.groups = Groups(self.provider.metadata)
            if self.provider.users is None:
                from bondable.bond.users import Users
                self.provider.users = Users(self.provider.metadata)
        return self.provider

    def get_metadata_db_url(self):
        return os.getenv('METADATA_DB_URL', 'sqlite:////tmp/.metadata.db')

    def get_jwt_config(self):
        if 'JWT_SECRET_KEY' not in os.environ:
            raise EnvironmentError("JWT_SECRET_KEY environment variable not set.")
        jwt_config = {
            'JWT_SECRET_KEY': os.environ.get("JWT_SECRET_KEY"),
            'JWT_ALGORITHM': os.environ.get("JWT_ALGORITHM", "HS256"),
            'ACCESS_TOKEN_EXPIRE_MINUTES': int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 1440)),  # Default to 24 hours
            'JWT_ISSUER': os.environ.get("JWT_ISSUER", "bondable"),
            'JWT_REDIRECT_URI': os.environ.get("JWT_REDIRECT_URI", "http://localhost:5000"),
        }
        return type('JWTConfig', (object,), jwt_config)()

    def get_auth_info(self):
        """
        Legacy method for Google auth info. Use get_oauth2_config() for new implementations.
        """
        return self.get_oauth2_config("google")
    
    def get_oauth2_config(self, provider_name: str = None) -> dict:
        """
        Get OAuth2 configuration for the specified provider or all providers.
        
        Args:
            provider_name: Specific provider to get config for, or None for all
            
        Returns:
            Dictionary with OAuth2 configuration
        """
        # Get enabled providers from environment
        enabled_providers = self._get_enabled_oauth2_providers()
        
        configs = {}
        
        # Only include enabled providers
        if "google" in enabled_providers:
            if provider_name == "google" or provider_name is None:
                google_config = self._get_google_oauth2_config()
                if provider_name == "google":
                    return google_config
                configs["google"] = google_config
        
        if "okta" in enabled_providers:
            if provider_name == "okta" or provider_name is None:
                okta_config = self._get_okta_oauth2_config()
                if provider_name == "okta":
                    return okta_config
                configs["okta"] = okta_config

        if "cognito" in enabled_providers:
            if provider_name == "cognito" or provider_name is None:
                cognito_config = self._get_cognito_oauth2_config()
                if provider_name == "cognito":
                    return cognito_config
                configs["cognito"] = cognito_config

        if provider_name:
            if provider_name not in configs:
                raise ValueError(f"OAuth2 provider '{provider_name}' is not enabled or configured")
            return configs[provider_name]
        
        return configs
    
    def _get_enabled_oauth2_providers(self) -> list:
        """
        Get list of enabled OAuth2 providers from environment variables.
        
        Environment variables:
        - OAUTH2_ENABLED_PROVIDERS: Comma-separated list of providers (e.g., "google,okta")
        - OAUTH2_ENABLE_GOOGLE: Enable Google OAuth2 (true/false)
        - OAUTH2_ENABLE_OKTA: Enable Okta OAuth2 (true/false)
        
        Returns:
            List of enabled provider names
        """
        # First check if there's an explicit list of enabled providers
        enabled_providers_str = os.getenv('OAUTH2_ENABLED_PROVIDERS', '')
        if enabled_providers_str:
            providers = [p.strip().lower() for p in enabled_providers_str.split(',') if p.strip()]
            LOGGER.info(f"OAuth2 providers from OAUTH2_ENABLED_PROVIDERS: {providers}")
            return providers
        
        # Otherwise check individual provider flags
        providers = []
        
        # Check Google
        google_enabled = os.getenv('OAUTH2_ENABLE_GOOGLE', 'true').lower() in ['true', '1', 'yes', 'on']
        if google_enabled:
            # Only enable if credentials are configured
            if os.getenv('GOOGLE_AUTH_CREDS_SECRET_ID') or os.getenv('GOOGLE_CLIENT_ID'):
                providers.append('google')
            else:
                LOGGER.warning("Google OAuth2 enabled but no credentials configured")
        
        # Check Okta
        okta_enabled = os.getenv('OAUTH2_ENABLE_OKTA', 'true').lower() in ['true', '1', 'yes', 'on']
        if okta_enabled:
            # Only enable if credentials are configured
            if os.getenv('OKTA_DOMAIN') and os.getenv('OKTA_CLIENT_ID'):
                providers.append('okta')
            else:
                LOGGER.warning("Okta OAuth2 enabled but not fully configured")

        # Check Cognito
        cognito_enabled = os.getenv('OAUTH2_ENABLE_COGNITO', 'false').lower() in ['true', '1', 'yes', 'on']
        if cognito_enabled:
            # Only enable if credentials are configured
            if os.getenv('COGNITO_DOMAIN') and os.getenv('COGNITO_CLIENT_ID'):
                providers.append('cognito')
            else:
                LOGGER.warning("Cognito OAuth2 enabled but not fully configured")

        # Default to at least Google if nothing is configured
        if not providers:
            LOGGER.warning("No OAuth2 providers enabled, defaulting to Google")
            providers = ['google']
        
        LOGGER.info(f"Enabled OAuth2 providers: {providers}")
        return providers
    
    def _get_google_oauth2_config(self) -> dict:
        """Get Google OAuth2 configuration."""
        # First check if credentials are provided directly via environment variable
        if 'GOOGLE_AUTH_CREDS_JSON' in os.environ:
            auth_creds_str = os.getenv('GOOGLE_AUTH_CREDS_JSON')
            LOGGER.info("Using Google OAuth2 credentials from GOOGLE_AUTH_CREDS_JSON environment variable")
        else:
            # Fall back to Secret Manager
            auth_creds_str = self.get_secret_value(os.getenv('GOOGLE_AUTH_CREDS_SECRET_ID', 'google_auth_creds'), "{}")
            LOGGER.info("Using Google OAuth2 credentials from Secret Manager")
        
        auth_creds = json.loads(auth_creds_str)
        redirect_uri = os.getenv('GOOGLE_AUTH_REDIRECT_URI', 'http://localhost:8000/auth/google/callback')
        scopes_str = os.getenv('GOOGLE_AUTH_SCOPES', 'openid, https://www.googleapis.com/auth/userinfo.email, https://www.googleapis.com/auth/userinfo.profile')
        scopes = [scope.strip() for scope in scopes_str.split(",")]
        valid_emails = []
        if 'GOOGLE_AUTH_VALID_EMAILS' in os.environ:
            valid_emails = [email.strip() for email in os.getenv('GOOGLE_AUTH_VALID_EMAILS').split(",")]
        
        config = {
            "auth_creds": auth_creds,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
            "valid_emails": valid_emails
        }
        LOGGER.info(f"Google OAuth2 config: redirect_uri={redirect_uri} scopes={scopes} valid_emails={len(valid_emails)} emails")
        return config
    
    def _get_okta_oauth2_config(self) -> dict:
        """Get Okta OAuth2 configuration."""
        domain = os.getenv('OKTA_DOMAIN', '')
        client_id = os.getenv('OKTA_CLIENT_ID', '')
        
        # Check if client secret is in environment variable or needs to be fetched from Secrets Manager
        client_secret = os.getenv('OKTA_CLIENT_SECRET', '')
        if not client_secret:
            # Try to get from Secrets Manager
            secret_name = os.getenv('OKTA_SECRET_NAME', '')
            if secret_name:
                LOGGER.info(f"Getting Okta client secret from Secrets Manager: {secret_name}")
                try:
                    secret_json = self.get_secret_value(secret_name, '{}')
                    secret_data = json.loads(secret_json)
                    client_secret = secret_data.get('client_secret', '')
                    if not client_secret:
                        LOGGER.error(f"No 'client_secret' field found in secret {secret_name}")
                except Exception as e:
                    LOGGER.error(f"Failed to get Okta client secret from Secrets Manager: {e}")
            else:
                LOGGER.warning("No OKTA_CLIENT_SECRET or OKTA_SECRET_NAME configured")
        
        redirect_uri = os.getenv('OKTA_REDIRECT_URI', 'http://localhost:8000/auth/okta/callback')
        scopes_str = os.getenv('OKTA_SCOPES', 'openid, profile, email')
        scopes = [scope.strip() for scope in scopes_str.split(",")]
        valid_emails = []
        if 'OKTA_VALID_EMAILS' in os.environ:
            valid_emails = [email.strip() for email in os.getenv('OKTA_VALID_EMAILS').split(",")]
        
        # Get authorization server configuration (default to org server for trial accounts)
        auth_server = os.getenv('OKTA_AUTH_SERVER', '')  # Empty string means use org server
        
        config = {
            "domain": domain,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
            "valid_emails": valid_emails,
            "auth_server": auth_server  # Use org server by default to avoid 'sub' claim issues
        }
        LOGGER.info(f"Okta OAuth2 config: domain={domain} auth_server={auth_server if auth_server else 'org'} redirect_uri={redirect_uri} scopes={scopes} valid_emails={len(valid_emails)} emails")
        return config

    def _get_cognito_oauth2_config(self) -> dict:
        """Get AWS Cognito OAuth2 configuration."""
        domain = os.getenv('COGNITO_DOMAIN', '')
        client_id = os.getenv('COGNITO_CLIENT_ID', '')
        region = os.getenv('COGNITO_REGION', 'us-east-1')

        # Client secret is optional for public clients (SPAs)
        client_secret = os.getenv('COGNITO_CLIENT_SECRET', '')
        if not client_secret:
            # Try to get from Secrets Manager
            secret_name = os.getenv('COGNITO_SECRET_NAME', '')
            if secret_name:
                LOGGER.info("Getting Cognito client secret from Secrets Manager")
                try:
                    secret_json = self.get_secret_value(secret_name, '{}')
                    secret_data = json.loads(secret_json)
                    client_secret = secret_data.get('client_secret', '')
                except Exception as e:
                    LOGGER.error(f"Failed to get Cognito client secret from Secrets Manager: {e}")

        redirect_uri = os.getenv('COGNITO_REDIRECT_URI', 'http://localhost:8000/auth/cognito/callback')
        scopes_str = os.getenv('COGNITO_SCOPES', 'openid, email, phone')
        scopes = [scope.strip() for scope in scopes_str.split(",")]
        valid_emails = []
        if 'COGNITO_VALID_EMAILS' in os.environ:
            valid_emails = [email.strip() for email in os.getenv('COGNITO_VALID_EMAILS').split(",")]

        config = {
            "domain": domain,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
            "valid_emails": valid_emails,
            "region": region
        }
        LOGGER.info(f"Cognito OAuth2 config: domain={domain} region={region} redirect_uri={redirect_uri} scopes={scopes} valid_emails={len(valid_emails)} emails")
        return config

    def get_mcp_config(self):
        """
        Get MCP configuration in fastmcp format from environment variables.
        
        Example:
        BOND_MCP_CONFIG='{
            "mcpServers": {
                "weather": {
                    "url": "https://weather-api.example.com/mcp",
                    "transport": "streamable-http"
                },
                "assistant": {
                    "command": "python",
                    "args": ["./my_assistant_server.py"],
                    "env": {"DEBUG": "true"}
                }
            }
        }'
        
        Returns:
            Dict in fastmcp config format
        """
        # Default to local hello server in fastmcp config format
        default_config = '''{
            "mcpServers": {
                "hello": {
                    "command": "python",
                    "args": ["hello_mcp_server.py"]
                }
            }
        }'''
        mcp_config_str = os.getenv('BOND_MCP_CONFIG', default_config)
        try:
            mcp_config = json.loads(mcp_config_str)
            server_count = len(mcp_config.get("mcpServers", {}))
            LOGGER.info(f"Loaded MCP config with {server_count} servers")
            return mcp_config
        except json.JSONDecodeError as e:
            LOGGER.error(f"Error parsing BOND_MCP_CONFIG: {e}")
            return {"mcpServers": {}}



        








