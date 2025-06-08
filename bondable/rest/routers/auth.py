from typing import Annotated
from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
import logging
import uuid

from bondable.bond.auth import OAuth2ProviderFactory
from bondable.bond.config import Config
from bondable.rest.models.auth import User
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.dependencies.providers import get_bond_provider
from bondable.rest.utils.auth import create_access_token

router = APIRouter(tags=["Authentication"])
LOGGER = logging.getLogger(__name__)
jwt_config = Config.config().get_jwt_config()


@router.get("/login")
async def login():
    """Initiate Google OAuth2 login flow (legacy endpoint)."""
    return await login_provider("google")


@router.get("/login/{provider}")
async def login_provider(provider: str):
    """Initiate OAuth2 login flow for specified provider."""
    try:
        config = Config.config()
        provider_config = config.get_oauth2_config(provider)
        
        oauth_provider = OAuth2ProviderFactory.create_provider(provider, provider_config)
        authorization_url = oauth_provider.get_auth_url()
        
        LOGGER.info(f"Redirecting user to {provider} for authentication: {authorization_url}")
        return RedirectResponse(url=authorization_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    except ValueError as e:
        LOGGER.error(f"Invalid OAuth2 provider '{provider}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OAuth2 provider: {provider}"
        )
    except Exception as e:
        LOGGER.error(f"Error generating {provider} auth URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not initiate authentication flow."
        )


@router.get("/auth/google/callback")
async def auth_callback(request: Request, bond_provider = Depends(get_bond_provider)):
    """Handle Google OAuth2 callback (legacy endpoint)."""
    return await auth_callback_provider("google", request, bond_provider)


@router.get("/auth/{provider}/callback")
async def auth_callback_provider(provider: str, request: Request, bond_provider = Depends(get_bond_provider)):
    """Handle OAuth2 callback for specified provider."""
    auth_code = request.query_params.get('code')
    if not auth_code:
        LOGGER.error(f"Authorization code not found in {provider} callback request.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code missing."
        )

    try:
        config = Config.config()
        provider_config = config.get_oauth2_config(provider)
        
        oauth_provider = OAuth2ProviderFactory.create_provider(provider, provider_config)
        user_info = oauth_provider.get_user_info_from_code(auth_code)
        
        LOGGER.info(f"Successfully authenticated user with {provider}: {user_info.get('email')}")

        user_id, is_new = bond_provider.users.get_or_create_user(
            user_id=user_info.get("sub"),
            email=user_info.get("email"),
            name=user_info.get("name"),
            sign_in_method=provider
        )

        if is_new:
            LOGGER.info(f"Created new user: {user_info.get('email')} (id: {user_id})")
        else:
            LOGGER.info(f"Updated existing user: {user_info.get('email')} (id: {user_id})")

        access_token_expires = timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": user_info.get("email"), 
                "name": user_info.get("name"),
                "provider": provider,
                "user_id": user_id
            },
            expires_delta=access_token_expires
        )
        LOGGER.info(f"Generated JWT for user: {user_info.get('email')} (provider: {provider})")

        flutter_redirect_url = f"{jwt_config.JWT_REDIRECT_URI}/#/auth-callback?token={access_token}"
        return RedirectResponse(url=flutter_redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    except ValueError as e:
        LOGGER.error(f"Authentication failed for {provider}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        LOGGER.error(f"Error processing {provider} callback: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Authentication failed.")


@router.get("/providers")
async def list_auth_providers():
    """List available OAuth2 authentication providers."""
    try:
        config = Config.config()
        # Get only enabled providers from config
        enabled_configs = config.get_oauth2_config()
        
        provider_info = []
        for provider_name in enabled_configs.keys():
            try:
                info = OAuth2ProviderFactory.get_provider_info(provider_name)
                provider_info.append({
                    "name": provider_name,
                    "login_url": f"/login/{provider_name}",
                    "callback_url": info["callback_path"]
                })
            except Exception as e:
                LOGGER.warning(f"Could not get info for provider {provider_name}: {e}")
        
        # Set default to first enabled provider or google if available
        default_provider = "google" if "google" in enabled_configs else (
            list(enabled_configs.keys())[0] if enabled_configs else "google"
        )
        
        return {
            "providers": provider_info,
            "default": default_provider
        }
    except Exception as e:
        LOGGER.error(f"Error listing auth providers: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not list authentication providers."
        )


@router.get("/users/me", response_model=User)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    """Get current authenticated user information."""
    LOGGER.info(f"Access granted to /users/me for user: {current_user.user_id} ({current_user.email})")
    return current_user