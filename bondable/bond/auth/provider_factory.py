import logging
from typing import Dict, Any, Type, Callable, Union
from .oauth2_provider import OAuth2Provider

LOGGER = logging.getLogger(__name__)


class OAuth2ProviderFactory:
    """
    Factory class for creating OAuth2 authentication providers.
    
    This factory handles registration and creation of different OAuth2 providers
    based on configuration and provider type.
    """
    
    # Registry of available OAuth2 providers (lazy loading)
    _providers: Dict[str, Union[Type[OAuth2Provider], Callable[[], Type[OAuth2Provider]]]] = {}
    
    @classmethod
    def _register_builtin_providers(cls):
        """Register built-in OAuth2 providers with lazy loading."""
        if not cls._providers:
            def google_provider():
                from .google_oauth2 import GoogleOAuth2Provider
                return GoogleOAuth2Provider
            
            def okta_provider():
                from .okta_oauth2 import OktaOAuth2Provider
                return OktaOAuth2Provider

            def cognito_provider():
                from .cognito_oauth2 import CognitoOAuth2Provider
                return CognitoOAuth2Provider

            cls._providers["google"] = google_provider
            cls._providers["okta"] = okta_provider
            cls._providers["cognito"] = cognito_provider
    
    @classmethod
    def register_provider(cls, provider_name: str, provider_class: Union[Type[OAuth2Provider], Callable[[], Type[OAuth2Provider]]]):
        """
        Register a new OAuth2 provider.
        
        Args:
            provider_name: Name identifier for the provider
            provider_class: Provider class that implements OAuth2Provider or factory function
        """
        cls._providers[provider_name] = provider_class
        LOGGER.info(f"Registered OAuth2 provider: {provider_name}")
    
    @classmethod
    def _resolve_provider_class(cls, provider_name: str) -> Type[OAuth2Provider]:
        """Resolve provider class from registry (handling lazy loading)."""
        cls._register_builtin_providers()
        
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown OAuth2 provider: {provider_name}")
        
        provider_entry = cls._providers[provider_name]
        
        # If it's a callable (lazy loader), call it to get the class
        if callable(provider_entry) and not isinstance(provider_entry, type):
            provider_class = provider_entry()
        else:
            provider_class = provider_entry
        
        # Validate the class
        if not issubclass(provider_class, OAuth2Provider):
            raise TypeError(f"Provider class must inherit from OAuth2Provider")
        
        return provider_class
    
    @classmethod
    def create_provider(cls, provider_name: str, config: Dict[str, Any]) -> OAuth2Provider:
        """
        Create an OAuth2 provider instance.
        
        Args:
            provider_name: Name of the provider to create
            config: Provider-specific configuration
            
        Returns:
            Configured OAuth2Provider instance
            
        Raises:
            ValueError: If provider_name is not registered
        """
        provider_class = cls._resolve_provider_class(provider_name)
        LOGGER.info(f"Creating OAuth2 provider: {provider_name}")
        
        try:
            provider = provider_class(config)
            LOGGER.info(f"Successfully created {provider_name} OAuth2 provider")
            return provider
        except Exception as e:
            LOGGER.error(f"Failed to create {provider_name} OAuth2 provider: {e}")
            raise
    
    @classmethod
    def get_available_providers(cls) -> list[str]:
        """
        Get list of available OAuth2 provider names.
        
        Returns:
            List of registered provider names
        """
        cls._register_builtin_providers()
        return list(cls._providers.keys())
    
    @classmethod
    def get_provider_info(cls, provider_name: str) -> Dict[str, Any]:
        """
        Get information about a specific provider.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            Dictionary with provider information
        """
        provider_class = cls._resolve_provider_class(provider_name)
        return {
            "name": provider_name,
            "class": provider_class.__name__,
            "module": provider_class.__module__,
            "callback_path": f"/auth/{provider_name}/callback"
        }