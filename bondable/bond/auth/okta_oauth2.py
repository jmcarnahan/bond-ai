import logging
import requests
from typing import Dict, Any
from urllib.parse import urlencode
from .oauth2_provider import OAuth2Provider

LOGGER = logging.getLogger(__name__)


class OktaOAuth2Provider(OAuth2Provider):
    """
    Okta OAuth2 authentication provider implementation.
    """
    
    @property
    def provider_name(self) -> str:
        return "okta"
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Okta OAuth2 provider.
        
        Expected config structure:
        {
            "domain": "https://trial-9457917.okta.com",
            "client_id": "your_client_id",
            "client_secret": "your_client_secret", 
            "redirect_uri": "http://localhost:8080/auth/okta/callback",
            "scopes": ["openid", "profile", "email"],
            "valid_emails": [],  # Optional: restrict access to specific emails
            "auth_server": "default"  # Optional: "default" or "" for org server
        }
        """
        super().__init__(config)
        
        required_keys = ["domain", "client_id", "client_secret", "redirect_uri", "scopes"]
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise ValueError(f"Missing required config keys for Okta OAuth2: {missing_keys}")
        
        # Ensure domain doesn't have trailing slash
        self.domain = config["domain"].rstrip('/')
        
        # Determine which authorization server to use
        # Use org server by default for trial accounts to avoid 'sub' claim issues
        self.auth_server = config.get("auth_server", "")
        if self.auth_server == "default":
            self.auth_server_path = "/oauth2/default"
        elif self.auth_server:
            self.auth_server_path = f"/oauth2/{self.auth_server}"
        else:
            # Use org authorization server (empty string means use org server)
            self.auth_server_path = "/oauth2"
        
        LOGGER.debug(f"Okta OAuth2 initialized: domain={self.domain} auth_server_path={self.auth_server_path} redirect_uri={config['redirect_uri']} scopes={config['scopes']}")
    
    def get_auth_url(self) -> str:
        """Generate Okta OAuth2 authorization URL."""
        auth_params = {
            'client_id': self.config["client_id"],
            'response_type': 'code',
            'scope': ' '.join(self.config["scopes"]),
            'redirect_uri': self.config["redirect_uri"],
            'state': 'bond-ai-auth'  # You might want to make this more secure/random
        }
        
        auth_url = f"{self.domain}{self.auth_server_path}/v1/authorize?{urlencode(auth_params)}"
        LOGGER.debug(f"Generated Okta auth URL: {auth_url}")
        return auth_url
    
    def _exchange_code_for_tokens(self, auth_code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and ID tokens."""
        token_url = f"{self.domain}{self.auth_server_path}/v1/token"
        
        token_data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self.config["redirect_uri"],
            'client_id': self.config["client_id"],
            'client_secret': self.config["client_secret"]
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        log_token_data = token_data.copy()
        log_token_data['client_secret'] = log_token_data['client_secret'][:6] + '...' if log_token_data['client_secret'] else None
        LOGGER.debug(f"Token exchange headers: {headers}")
        LOGGER.debug(f"Token exchange data: {log_token_data}")
        LOGGER.debug(f"Exchanging code for tokens at: {token_url}")

        response = requests.post(token_url, data=token_data, headers=headers)
        if response.status_code != 200:
            error_msg = f"Token exchange failed: {response.status_code} - {response.text}"
            LOGGER.error(error_msg)
            raise Exception(error_msg)
        
        return response.json()
    
    def _get_user_info_from_token(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Okta using access token."""
        userinfo_url = f"{self.domain}{self.auth_server_path}/v1/userinfo"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        LOGGER.debug(f"Fetching user info from: {userinfo_url}")
        response = requests.get(userinfo_url, headers=headers)
        
        if response.status_code != 200:
            error_msg = f"User info fetch failed: {response.status_code} - {response.text}"
            LOGGER.error(error_msg)
            raise Exception(error_msg)
        
        return response.json()
    
    def get_user_info_from_code(self, auth_code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for user information.
        
        Args:
            auth_code: Okta OAuth2 authorization code
            
        Returns:
            Dictionary with user information including email, name, etc.
            
        Raises:
            ValueError: If user email is not in valid_emails list (when configured)
            Exception: For other authentication errors
        """
        try:
            LOGGER.info(f"Authenticating with Okta auth code: {auth_code[:10]}...")
            
            # Exchange code for tokens
            tokens = self._exchange_code_for_tokens(auth_code)
            access_token = tokens.get('access_token')
            
            if not access_token:
                raise Exception("No access token received from Okta")
            
            # Get user info using access token
            user_info = self._get_user_info_from_token(access_token)
            
            # Normalize the user info to match our expected format
            normalized_user_info = {
                'email': user_info.get('email'),
                'name': user_info.get('preferred_username'),
                'sub': user_info.get('sub'),
                'given_name': user_info.get('given_name'),
                'family_name': user_info.get('family_name'),
                'locale': user_info.get('locale'),
                'zoneinfo': user_info.get('zoneinfo')
            }
            
            LOGGER.info(f"Okta authentication successful: {normalized_user_info.get('name')} {normalized_user_info.get('email')}")
            
            # Validate user authorization
            if not self.validate_user(normalized_user_info):
                raise ValueError(f"User {normalized_user_info.get('email')} is not authorized to access this application")
            
            return normalized_user_info
            
        except Exception as e:
            LOGGER.error(f"Error authenticating with Okta code {auth_code[:10]}...: {e}")
            raise e
    
    def validate_user(self, user_info: Dict[str, Any]) -> bool:
        """
        Validate if user is authorized based on email whitelist.
        
        Args:
            user_info: User information from Okta
            
        Returns:
            True if user is authorized, False otherwise
        """
        valid_emails = self.config.get("valid_emails", [])
        
        # If no valid_emails configured, allow all users
        if not valid_emails:
            return True
        
        user_email = user_info.get("email")
        if not user_email:
            LOGGER.error("No email found in user info")
            return False
        
        is_valid = user_email in valid_emails
        if not is_valid:
            LOGGER.error(f"Email {user_email} not in valid emails list: {valid_emails}")
        
        return is_valid