import logging
from typing import Dict, Any
from google_auth_oauthlib.flow import Flow
from google.auth.transport import requests
from google.oauth2 import id_token
from .oauth2_provider import OAuth2Provider, OAuth2UserInfo

LOGGER = logging.getLogger(__name__)


class GoogleOAuth2Provider(OAuth2Provider):
    """
    Google OAuth2 authentication provider implementation.
    """

    @property
    def provider_name(self) -> str:
        return "google"

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Google OAuth2 provider.

        Expected config structure:
        {
            "auth_creds": {...},  # Google OAuth2 client configuration
            "redirect_uri": "http://localhost:8080/auth/google/callback",
            "scopes": ["openid", "email", "profile"],
            "valid_emails": []  # Optional: restrict access to specific emails
        }
        """
        super().__init__(config)

        required_keys = ["auth_creds", "redirect_uri", "scopes"]
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise ValueError(f"Missing required config keys for Google OAuth2: {missing_keys}")

        LOGGER.debug(f"Google OAuth2 initialized: redirect_uri={config['redirect_uri']} scopes={config['scopes']}")

    def _get_flow(self) -> Flow:
        """Create and configure Google OAuth2 flow."""
        return Flow.from_client_config(
            client_config=self.config["auth_creds"],
            scopes=self.config["scopes"],
            redirect_uri=self.config["redirect_uri"]
        )

    def get_auth_url(self) -> str:
        """Generate Google OAuth2 authorization URL."""
        flow = self._get_flow()
        authorization_url, state = flow.authorization_url(
            # Enable offline access for refresh tokens
            access_type='offline',
            # Enable incremental authorization
            include_granted_scopes='true',
            # Force consent prompt to ensure fresh tokens
            prompt='consent'
        )
        LOGGER.debug(f"Generated Google auth URL: {authorization_url}")
        return authorization_url

    def _fetch_google_token(self, auth_code: str):
        """Exchange authorization code for Google OAuth2 credentials."""
        flow = self._get_flow()
        flow.fetch_token(code=auth_code)
        return flow.credentials

    def _get_google_user_info(self, creds) -> Dict[str, Any]:
        """Extract user information from Google ID token."""
        request = requests.Request()
        user_info = id_token.verify_oauth2_token(
            creds.id_token,
            request,
            clock_skew_in_seconds=10
        )
        return user_info

    def get_user_info_from_code(self, auth_code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for user information.

        Args:
            auth_code: Google OAuth2 authorization code

        Returns:
            Dictionary with user information including email, name, etc.

        Raises:
            ValueError: If user email is not in valid_emails list (when configured)
            Exception: For other authentication errors
        """
        try:
            LOGGER.info(f"Authenticating with Google auth code: {auth_code[:10]}...")

            # Exchange code for credentials
            creds = self._fetch_google_token(auth_code)

            # Extract user info from ID token
            user_info = self._get_google_user_info(creds)

            LOGGER.info(f"Google authentication successful: {user_info.get('name')} {user_info.get('email')}")

            # Validate user authorization
            if not self.validate_user(user_info):
                raise ValueError(f"User {user_info.get('email')} is not authorized to access this application")

            return user_info

        except Exception as e:
            LOGGER.error(f"Error authenticating with Google code {auth_code[:10]}...: {e}")
            raise e

    def validate_user(self, user_info: Dict[str, Any]) -> bool:
        """
        Validate if user is authorized based on email whitelist.

        Args:
            user_info: User information from Google

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
