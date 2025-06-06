from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from jose import jwt
import uuid

from bondable.bond.config import Config
from bondable.bond.providers.metadata import User as UserModel

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


def get_or_create_user(db_session, email: str, name: str, sign_in_method: str) -> Tuple[str, bool]:
    """Get existing user or create new user in database."""
    existing_user = db_session.query(UserModel).filter_by(email=email).first()

    if existing_user:
        existing_user.updated_at = datetime.now()
        if name and existing_user.name != name:
            existing_user.name = name
        db_session.commit()
        return existing_user.id, False
    else:
        new_user = UserModel(
            id=str(uuid.uuid4()),
            email=email,
            name=name,
            sign_in_method=sign_in_method
        )
        db_session.add(new_user)
        db_session.commit()
        return new_user.id, True
