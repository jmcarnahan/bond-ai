import logging
import requests
from typing import Dict, Any
from urllib.parse import urlencode
from .oauth2_provider import OAuth2Provider

LOGGER = logging.getLogger(__name__)


class CognitoOAuth2Provider(OAuth2Provider):
    """
    AWS Cognito OAuth2 authentication provider implementation.

    Supports both public clients (SPAs without client secret) and
    confidential clients (with client secret).
    """

    @property
    def provider_name(self) -> str:
        return "cognito"

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Cognito OAuth2 provider.

        Expected config structure:
        {
            "domain": "https://your-domain.auth.us-west-2.amazoncognito.com",
            "client_id": "your_client_id",
            "client_secret": "",  # Optional for public clients (SPAs)
            "redirect_uri": "http://localhost:8000/auth/cognito/callback",
            "scopes": ["openid", "email", "phone"],
            "valid_emails": [],  # Optional: restrict access to specific emails
            "region": "us-west-2"
        }
        """
        super().__init__(config)

        required_keys = ["domain", "client_id", "redirect_uri", "scopes"]
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise ValueError(f"Missing required config keys for Cognito OAuth2: {missing_keys}")

        # Ensure domain doesn't have trailing slash
        self.domain = config["domain"].rstrip('/')
        self.region = config.get("region", "us-east-1")

        LOGGER.debug(f"Cognito OAuth2 initialized: domain={self.domain} redirect_uri={config['redirect_uri']} scopes={config['scopes']}")

    def get_auth_url(self) -> str:
        """Generate Cognito OAuth2 authorization URL."""
        auth_params = {
            'client_id': self.config["client_id"],
            'response_type': 'code',
            'scope': ' '.join(self.config["scopes"]),
            'redirect_uri': self.config["redirect_uri"],
        }

        auth_url = f"{self.domain}/oauth2/authorize?{urlencode(auth_params)}"
        LOGGER.debug(f"Generated Cognito auth URL: {auth_url}")
        return auth_url

    def _exchange_code_for_tokens(self, auth_code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and ID tokens."""
        token_url = f"{self.domain}/oauth2/token"

        token_data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self.config["redirect_uri"],
            'client_id': self.config["client_id"],
        }

        # Add client secret if configured (for confidential clients)
        client_secret = self.config.get("client_secret", "")
        if client_secret:
            token_data['client_secret'] = client_secret

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }

        log_token_data = token_data.copy()
        if 'client_secret' in log_token_data and log_token_data['client_secret']:
            log_token_data['client_secret'] = log_token_data['client_secret'][:6] + '...'
        log_token_data['code'] = log_token_data['code'][:8] + '...' if log_token_data.get('code') else None
        LOGGER.debug(f"Token exchange data: {log_token_data}")
        LOGGER.debug(f"Exchanging code for tokens at: {token_url}")

        response = requests.post(token_url, data=token_data, headers=headers)

        if response.status_code != 200:
            error_msg = f"Token exchange failed: {response.status_code} - {response.text}"
            LOGGER.error(error_msg)
            raise Exception(error_msg)

        return response.json()

    def _get_user_info_from_token(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Cognito using access token."""
        userinfo_url = f"{self.domain}/oauth2/userInfo"

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
            auth_code: Cognito OAuth2 authorization code

        Returns:
            Dictionary with user information including email, name, etc.

        Raises:
            ValueError: If user email is not in valid_emails list (when configured)
            Exception: For other authentication errors
        """
        try:
            LOGGER.info(f"Authenticating with Cognito auth code: {auth_code[:10]}...")

            # Exchange code for tokens
            tokens = self._exchange_code_for_tokens(auth_code)
            access_token = tokens.get('access_token')

            if not access_token:
                raise Exception("No access token received from Cognito")

            # Get user info using access token
            user_info = self._get_user_info_from_token(access_token)

            # Normalize the user info to match our expected format
            # Cognito may return 'cognito:username' for the username
            normalized_user_info = {
                'email': user_info.get('email'),
                'name': user_info.get('name') or user_info.get('email', '').split('@')[0],
                'sub': user_info.get('sub'),
                'given_name': user_info.get('given_name'),
                'family_name': user_info.get('family_name'),
                'email_verified': user_info.get('email_verified', False),
                'phone_number': user_info.get('phone_number'),
                'cognito_username': user_info.get('cognito:username') or user_info.get('username'),
            }

            LOGGER.info("Cognito authentication successful")

            # Validate user authorization
            if not self.validate_user(normalized_user_info):
                raise ValueError(f"User {normalized_user_info.get('email')} is not authorized to access this application")

            return normalized_user_info

        except Exception as e:
            LOGGER.error(f"Error authenticating with Cognito code {auth_code[:10]}...: {e}")
            raise e

    def validate_user(self, user_info: Dict[str, Any]) -> bool:
        """
        Validate if user is authorized based on email whitelist.

        Args:
            user_info: User information from Cognito

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

        is_valid = user_email.lower() in [e.lower() for e in valid_emails]
        if not is_valid:
            LOGGER.error("User email not in valid emails list")

        return is_valid
