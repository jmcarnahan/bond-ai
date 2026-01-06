"""
Authentication module for Bond AI.

This module provides OAuth2 authentication support with multiple providers.
"""

from .oauth2_provider import OAuth2Provider, OAuth2UserInfo
from .provider_factory import OAuth2ProviderFactory

# Legacy compatibility - lazy import
def _get_google_auth():
    from .google_auth_legacy import GoogleAuth
    return GoogleAuth

# Create a lazy property for backwards compatibility
class _LazyGoogleAuth:
    def __getattr__(self, name):
        GoogleAuth = _get_google_auth()
        return getattr(GoogleAuth, name)

# Export lazy GoogleAuth for backwards compatibility
GoogleAuth = _LazyGoogleAuth()

__all__ = [
    'OAuth2Provider',
    'OAuth2UserInfo',
    'OAuth2ProviderFactory',
    'GoogleAuth'  # Legacy
]
