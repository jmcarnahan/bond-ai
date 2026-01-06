import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

LOGGER = logging.getLogger(__name__)


class OAuth2Provider(ABC):
    """
    Abstract base class for OAuth2 authentication providers.

    This class defines the interface that all OAuth2 providers must implement
    to support authentication in the Bond AI application.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the OAuth2 provider with configuration.

        Args:
            config: Provider-specific configuration dictionary
        """
        self.config = config
        LOGGER.debug(f"{self.__class__.__name__} initialized with config keys: {list(config.keys())}")

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Return the name of this OAuth2 provider.

        Returns:
            String identifier for this provider (e.g., 'google', 'okta')
        """
        pass

    @abstractmethod
    def get_auth_url(self) -> str:
        """
        Generate the authorization URL for initiating OAuth2 flow.

        Returns:
            Authorization URL string
        """
        pass

    @abstractmethod
    def get_user_info_from_code(self, auth_code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for user information.

        Args:
            auth_code: Authorization code received from OAuth2 callback

        Returns:
            Dictionary containing user information with at least:
            - email: User's email address
            - name: User's display name

        Raises:
            ValueError: If authentication fails or user is not authorized
            Exception: For other authentication errors
        """
        pass

    @abstractmethod
    def validate_user(self, user_info: Dict[str, Any]) -> bool:
        """
        Validate if the authenticated user is authorized to access the application.

        Args:
            user_info: User information dictionary

        Returns:
            True if user is authorized, False otherwise
        """
        pass

    def create_cookie(self, user_info: Dict[str, Any]) -> str:
        """
        Create a secure cookie string from user information.

        Args:
            user_info: User information dictionary

        Returns:
            Base64 encoded cookie string
        """
        import base64
        import json
        return base64.b64encode(json.dumps(user_info).encode("utf-8")).decode("utf-8")

    def get_user_info_from_cookie(self, cookie: str) -> Optional[Dict[str, Any]]:
        """
        Extract user information from a cookie string.

        Args:
            cookie: Base64 encoded cookie string

        Returns:
            User information dictionary or None if invalid
        """
        try:
            import base64
            import json
            user_info = json.loads(base64.b64decode(cookie).decode("utf-8"))
            LOGGER.info(f"Found user info in cookie: {user_info.get('name')} {user_info.get('email')}")
            return user_info
        except Exception as e:
            LOGGER.error(f"Error decoding cookie: {e}")
            return None

    @property
    def callback_path(self) -> str:
        """
        Return the callback path for this provider.

        Returns:
            Callback path string (e.g., '/auth/google/callback')
        """
        return f"/auth/{self.provider_name}/callback"


class OAuth2UserInfo:
    """
    Standardized user information container for OAuth2 providers.
    """

    def __init__(self, email: str, name: str, provider: str, raw_data: Dict[str, Any] = None):
        """
        Initialize user info.

        Args:
            email: User's email address
            name: User's display name
            provider: OAuth2 provider name
            raw_data: Original provider response data
        """
        self.email = email
        self.name = name
        self.provider = provider
        self.raw_data = raw_data or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JWT token creation."""
        return {
            "email": self.email,
            "name": self.name,
            "provider": self.provider
        }
