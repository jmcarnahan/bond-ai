from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
import jwt

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

    # Ensure standard claims are present for security validation
    if "iss" not in to_encode:
        to_encode["iss"] = "bond-ai"
    if "aud" not in to_encode:
        to_encode["aud"] = ["bond-ai-api", "mcp-server"]
    if "jti" not in to_encode:
        to_encode["jti"] = str(uuid.uuid4())

    return jwt.encode(to_encode, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
