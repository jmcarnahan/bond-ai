from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError
import logging
import time
import threading

from bondable.bond.config import Config
from bondable.rest.models.auth import User

LOGGER = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google/callback", auto_error=False)
jwt_config = Config.config().get_jwt_config()

# Simple in-memory revocation cache: jti -> revoked_at timestamp
# Avoids a DB hit on every request. Entries expire after 30 seconds (re-checked from DB).
_revocation_cache: dict[str, float] = {}
_revocation_cache_lock = threading.Lock()
_REVOCATION_CACHE_TTL = 30  # seconds
_REVOCATION_CACHE_MAX_SIZE = 1000


def _extract_token(request: Request) -> Optional[str]:
    """Extract JWT token from Bearer header or bond_session cookie.

    Bearer header takes precedence over cookie.
    """
    # 1. Check Authorization header
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header[7:]

    # 2. Check bond_session cookie
    cookie_token = request.cookies.get("bond_session")
    if cookie_token:
        return cookie_token

    return None


def _is_token_revoked(jti: str, bond_provider=None) -> bool:
    """Check if a token's jti has been revoked, using a cache to avoid DB hits."""
    now = time.time()

    # Check cache first
    with _revocation_cache_lock:
        if jti in _revocation_cache:
            cached_at = _revocation_cache[jti]
            if now - cached_at < _REVOCATION_CACHE_TTL:
                return True
            # Expired cache entry — will re-check DB below

        # Prune oversized cache
        if len(_revocation_cache) > _REVOCATION_CACHE_MAX_SIZE:
            cutoff = now - _REVOCATION_CACHE_TTL
            expired_keys = [k for k, v in _revocation_cache.items() if v < cutoff]
            for k in expired_keys:
                del _revocation_cache[k]

    # Check DB
    if bond_provider is None:
        try:
            from bondable.rest.dependencies.providers import get_bond_provider
            bond_provider = get_bond_provider()
        except Exception as e:
            # Fail closed: if we can't check revocation, deny access (H2 fix)
            LOGGER.error(f"Cannot access revocation store — denying access: {e}")
            return True

    try:
        from bondable.bond.providers.metadata import RevokedToken
        with bond_provider.metadata.get_db_session() as session:
            revoked = session.query(RevokedToken).filter(RevokedToken.jti == jti).first()
            if revoked:
                with _revocation_cache_lock:
                    _revocation_cache[jti] = now
                return True
    except Exception as e:
        # Fail closed: if DB query fails, deny access rather than allowing revoked tokens
        LOGGER.error(f"Error checking token revocation — denying access: {e}")
        return True

    return False


async def get_current_user(request: Request) -> User:
    """Verify JWT token (from Bearer header or cookie) and return user data."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = _extract_token(request)
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(
            token,
            jwt_config.JWT_SECRET_KEY,
            algorithms=[jwt_config.JWT_ALGORITHM],
            audience="bond-ai-api",
            issuer="bond-ai",
            options={"require": ["exp", "sub"]}
        )
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

        # Check token revocation
        jti = payload.get("jti")
        if jti and _is_token_revoked(jti):
            LOGGER.warning(f"Rejected revoked token jti={jti}")
            raise credentials_exception

        # Extract Okta metadata if available
        return User(
            email=email,
            name=name,
            provider=provider,
            user_id=user_id,
            is_admin=Config.config().is_admin_user(email),
            okta_sub=payload.get("okta_sub"),
            given_name=payload.get("given_name"),
            family_name=payload.get("family_name"),
            locale=payload.get("locale")
        )

    except InvalidTokenError as e:
        LOGGER.error(f"JWT Error during token decode: {e}", exc_info=True)
        raise credentials_exception
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Unexpected error during token validation: {e}", exc_info=True)
        raise credentials_exception


async def get_current_user_with_token(request: Request) -> tuple[User, str]:
    """
    Verify JWT token and return both user data and the raw token.
    This is useful for passing authentication to MCP servers.
    """
    user = await get_current_user(request)
    token = _extract_token(request)
    return user, token
