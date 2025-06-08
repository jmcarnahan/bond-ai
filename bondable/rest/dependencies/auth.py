from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import logging

from bondable.bond.config import Config
from bondable.rest.models.auth import User

LOGGER = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google/callback")
jwt_config = Config.config().get_jwt_config()


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    """Verify JWT token and return user data."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, jwt_config.JWT_SECRET_KEY, algorithms=[jwt_config.JWT_ALGORITHM])
        email = payload.get("sub")
        name = payload.get("name")
        provider = payload.get("provider")
        user_id = payload.get("user_id")

        if not email:
            LOGGER.warning("Token payload missing 'sub' (email).")
            raise credentials_exception

        if not user_id:
            LOGGER.warning("Token payload missing 'user_id'. This is an old token format.")
            raise credentials_exception

        if not provider:
            LOGGER.warning("Token payload missing 'provider'.")
            raise credentials_exception

        return User(email=email, name=name, provider=provider, user_id=user_id)

    except JWTError as e:
        LOGGER.error(f"JWT Error during token decode: {e}", exc_info=True)
        raise credentials_exception
    except Exception as e:
        LOGGER.error(f"Unexpected error during token validation: {e}", exc_info=True)
        raise credentials_exception