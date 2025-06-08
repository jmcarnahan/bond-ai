from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt

from bondable.bond.config import Config

jwt_config = Config.config().get_jwt_config()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = (
        datetime.now(timezone.utc) + expires_delta
        if expires_delta
        else datetime.now(timezone.utc) + timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
