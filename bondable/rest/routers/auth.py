from typing import Annotated
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
import logging

from bondable.bond.auth import GoogleAuth
from bondable.bond.config import Config
from bondable.rest.models.auth import User
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.utils.auth import create_access_token

router = APIRouter(tags=["Authentication"])
logger = logging.getLogger(__name__)
jwt_config = Config.config().get_jwt_config()


@router.get("/login")
async def login():
    """Initiate Google OAuth2 login flow."""
    try:
        auth = GoogleAuth.auth()
        authorization_url = auth.get_auth_url()
        logger.info(f"Redirecting user to Google for authentication: {authorization_url}")
        return RedirectResponse(url=authorization_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    except Exception as e:
        logger.error(f"Error generating Google auth URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not initiate authentication flow."
        )


@router.get("/auth/google/callback")
async def auth_callback(request: Request):
    """Handle Google OAuth2 callback."""
    auth_code = request.query_params.get('code')
    if not auth_code:
        logger.error("Authorization code not found in callback request.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code missing."
        )

    try:
        auth = GoogleAuth.auth()
        user_info = auth.get_user_info_from_code(auth_code)
        logger.info(f"Successfully authenticated user: {user_info.get('email')}")

        # Create JWT
        access_token_expires = timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_info.get("email"), "name": user_info.get("name")},
            expires_delta=access_token_expires
        )
        logger.info(f"Generated JWT for user: {user_info.get('email')}")

        # Redirect to Flutter app
        flutter_redirect_url = f"{jwt_config.JWT_REDIRECT_URI}/#/auth-callback?token={access_token}"
        return RedirectResponse(url=flutter_redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    except ValueError as e:
        logger.error(f"Authentication failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing Google callback: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Authentication failed.")


@router.get("/users/me", response_model=User)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    """Get current authenticated user information."""
    logger.info(f"Access granted to /users/me for user: {current_user.email}")
    return current_user