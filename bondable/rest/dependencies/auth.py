from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import logging

from bondable.bond.config import Config
from bondable.rest.models.auth import User

logger = logging.getLogger(__name__)
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
        
        if not email:
            logger.warning("Token payload missing 'sub' (email).")
            raise credentials_exception
            
        return User(email=email, name=name)
        
    except JWTError as e:
        logger.error(f"JWT Error during token decode: {e}", exc_info=True)
        raise credentials_exception
    except Exception as e:
        logger.error(f"Unexpected error during token validation: {e}", exc_info=True)
        raise credentials_exception