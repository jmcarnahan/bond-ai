from typing import Annotated
from datetime import timedelta, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse, JSONResponse
import logging
import hashlib
import uuid
import os
import secrets

from slowapi import Limiter
from slowapi.util import get_remote_address

from bondable.bond.auth import OAuth2ProviderFactory
from bondable.bond.auth.oauth_utils import generate_pkce_pair, generate_oauth_state, validate_oauth_state
from bondable.bond.config import Config
from bondable.rest.models.auth import User
from bondable.rest.dependencies.auth import get_current_user
from bondable.rest.dependencies.providers import get_bond_provider
from bondable.rest.utils.auth import create_access_token
from bondable.utils.url_validation import is_safe_redirect_url
from pydantic import BaseModel

router = APIRouter(tags=["Authentication"])
LOGGER = logging.getLogger(__name__)
jwt_config = Config.config().get_jwt_config()
limiter = Limiter(key_func=get_remote_address)

# Cookie configuration
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() != "false"
AUTH_CODE_TTL_SECONDS = 60
AUTH_CODE_CLEANUP_MINUTES = 5


class TokenExchangeRequest(BaseModel):
    code: str


class ProvisionRequest(BaseModel):
    email: str
    name: str
    provider: str = "external"


def _save_auth_oauth_state(
    bond_provider,
    state: str,
    provider_name: str,
    code_verifier: str,
    redirect_uri: str = "",
    platform: str = ""
) -> bool:
    """Save OAuth state for primary auth flow.

    Uses AuthOAuthState table (no FK to users) since user hasn't authenticated yet.
    """
    try:
        from bondable.bond.providers.metadata import AuthOAuthState

        with bond_provider.metadata.get_db_session() as session:
            # Clean up old states (older than 10 minutes)
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
            session.query(AuthOAuthState).filter(
                AuthOAuthState.created_at < cutoff
            ).delete()

            oauth_state = AuthOAuthState(
                state=state,
                provider_name=provider_name,
                code_verifier=code_verifier,
                redirect_uri=redirect_uri,
                platform=platform,
            )
            session.add(oauth_state)
            session.commit()
            return True
    except Exception as e:
        LOGGER.error(f"Error saving auth OAuth state: {e}")
        return False


def _get_and_delete_auth_oauth_state(bond_provider, state: str):
    """Get and delete OAuth state for primary auth flow."""
    try:
        from bondable.bond.providers.metadata import AuthOAuthState

        with bond_provider.metadata.get_db_session() as session:
            oauth_state = session.query(AuthOAuthState).filter(
                AuthOAuthState.state == state
            ).first()

            if oauth_state is None:
                return None

            result = {
                "provider_name": oauth_state.provider_name,
                "code_verifier": oauth_state.code_verifier,
                "redirect_uri": oauth_state.redirect_uri,
                "platform": oauth_state.platform,
            }

            session.delete(oauth_state)
            session.commit()
            return result
    except Exception as e:
        LOGGER.error(f"Error getting auth OAuth state: {e}")
        return None


def _create_auth_code(bond_provider, access_token: str, user_id: str, platform: str = None) -> str:
    """Create a short-lived authorization code that can be exchanged for a token/cookie."""
    from bondable.bond.providers.metadata import AuthCode

    code = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=AUTH_CODE_TTL_SECONDS)

    with bond_provider.metadata.get_db_session() as session:
        # Lazily clean up expired auth codes older than 5 minutes
        cutoff = now - timedelta(minutes=AUTH_CODE_CLEANUP_MINUTES)
        session.query(AuthCode).filter(AuthCode.expires_at < cutoff).delete()

        auth_code = AuthCode(
            code=code,
            access_token=access_token,
            user_id=user_id,
            platform=platform,
            created_at=now,
            expires_at=expires_at,
        )
        session.add(auth_code)
        session.commit()

    return code


@router.post("/auth/token")
@limiter.limit("20/minute")
async def exchange_auth_code(request: Request, body: TokenExchangeRequest, bond_provider=Depends(get_bond_provider)):
    """Exchange an authorization code for a session cookie (web) or bearer token (mobile)."""
    import jwt as pyjwt
    from bondable.bond.providers.metadata import AuthCode

    now = datetime.now(timezone.utc)

    with bond_provider.metadata.get_db_session() as session:
        # Atomic single-use enforcement: UPDATE ... WHERE used_at IS NULL
        # This prevents race conditions on both SQLite and PostgreSQL.
        result = session.query(AuthCode).filter(
            AuthCode.code == body.code,
            AuthCode.used_at.is_(None),
        ).update({"used_at": now}, synchronize_session="fetch")
        session.commit()

        if result == 0:
            # Either code doesn't exist, is already used, or expired — check which
            auth_code = session.query(AuthCode).filter(AuthCode.code == body.code).first()
            if auth_code is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid authorization code.")
            if auth_code.used_at is not None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization code has already been used.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization code error.")

        # Re-read the row to get access_token and platform
        auth_code = session.query(AuthCode).filter(AuthCode.code == body.code).first()

        # Check expiry
        expires_at = auth_code.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization code has expired.")

        access_token = auth_code.access_token
        platform = auth_code.platform

    if platform == "mobile":
        return {"access_token": access_token, "token_type": "bearer"}

    # Web: set HttpOnly session cookie + non-HttpOnly CSRF cookie
    # Decode JWT to get expiry for cookie max-age
    try:
        payload = pyjwt.decode(access_token, options={"verify_signature": False})
        exp = payload.get("exp", 0)
        max_age = max(int(exp - now.timestamp()), 0)
    except Exception:
        max_age = jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    csrf_token = secrets.token_urlsafe(32)

    response = JSONResponse(content={"token_type": "cookie"})
    response.set_cookie(
        key="bond_session",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
        max_age=max_age,
    )
    response.set_cookie(
        key="bond_csrf",
        value=csrf_token,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
        max_age=max_age,
    )
    return response


@router.post("/auth/logout")
async def logout(request: Request, current_user: Annotated[User, Depends(get_current_user)], bond_provider=Depends(get_bond_provider)):
    """Revoke the current token and clear session cookies."""
    import jwt as pyjwt
    from bondable.bond.providers.metadata import RevokedToken
    from bondable.rest.dependencies.auth import _extract_token

    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No token found.")

    try:
        payload = pyjwt.decode(
            token,
            jwt_config.JWT_SECRET_KEY,
            algorithms=[jwt_config.JWT_ALGORITHM],
            audience="bond-ai-api",
            issuer="bond-ai",
        )
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token missing jti claim.")

        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc) + timedelta(hours=1)

        with bond_provider.metadata.get_db_session() as session:
            existing = session.query(RevokedToken).filter(RevokedToken.jti == jti).first()
            if not existing:
                revoked = RevokedToken(
                    jti=jti,
                    user_id=current_user.user_id,
                    expires_at=expires_at,
                )
                session.add(revoked)
                session.commit()

        # Invalidate the in-memory revocation cache (uses time.time() float for consistency)
        import time as _time
        from bondable.rest.dependencies.auth import _revocation_cache
        _revocation_cache[jti] = _time.time()

    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error during logout: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed.")

    response = JSONResponse(content={"status": "logged_out"})

    # If web (cookie auth), clear cookies
    if request.cookies.get("bond_session"):
        response.delete_cookie(key="bond_session", path="/")
        response.delete_cookie(key="bond_csrf", path="/")

    return response


@router.get("/login")
@limiter.limit("10/minute")
async def login(request: Request, bond_provider=Depends(get_bond_provider)):
    """Initiate OAuth2 login flow (legacy endpoint)."""
    config = Config.config()
    providers = config._get_enabled_oauth2_providers()
    provider = providers[0] if providers else "cognito"
    return await login_provider(provider, request, bond_provider)


@router.get("/login/{provider}")
@limiter.limit("10/minute")
async def login_provider(provider: str, request: Request, bond_provider=Depends(get_bond_provider)):
    """Initiate OAuth2 login flow for specified provider."""
    try:
        config = Config.config()
        provider_config = config.get_oauth2_config(provider)

        # Check if this is a mobile request with custom redirect
        platform = request.query_params.get('platform')
        redirect_uri = request.query_params.get('redirect_uri')

        # T-O1: Validate redirect_uri against allowlist
        if redirect_uri and not is_safe_redirect_url(redirect_uri):
            LOGGER.warning(f"Rejected login with unsafe redirect_uri: {redirect_uri}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid redirect_uri: domain not in allowed list"
            )

        # T-O2: Generate secure OAuth state (replaces hardcoded 'bond-ai-auth')
        oauth_state = generate_oauth_state(provider)

        # T-O4: Generate PKCE code verifier and challenge
        code_verifier, code_challenge = generate_pkce_pair()

        # Store state, PKCE verifier, and mobile params in database
        _save_auth_oauth_state(
            bond_provider=bond_provider,
            state=oauth_state,
            provider_name=provider,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri or "",
            platform=platform or ""
        )

        # Create the provider and get auth URL with PKCE and state
        oauth_provider = OAuth2ProviderFactory.create_provider(provider, provider_config)
        authorization_url = oauth_provider.get_auth_url(
            state=oauth_state,
            code_challenge=code_challenge,
            code_challenge_method="S256"
        )

        LOGGER.info(f"Redirecting user to {provider} for authentication")
        return RedirectResponse(url=authorization_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    except HTTPException:
        raise
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
@limiter.limit("10/minute")
async def auth_callback(request: Request, bond_provider = Depends(get_bond_provider)):
    """Handle Google OAuth2 callback (legacy endpoint)."""
    return await auth_callback_provider("google", request, bond_provider)


@router.get("/auth/{provider}/callback")
@limiter.limit("10/minute")
async def auth_callback_provider(provider: str, request: Request, bond_provider = Depends(get_bond_provider)):
    """Handle OAuth2 callback for specified provider."""
    auth_code = request.query_params.get('code')
    if not auth_code:
        LOGGER.error(f"Authorization code not found in {provider} callback request.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code missing."
        )

    # T-O2: Validate OAuth state parameter
    state = request.query_params.get('state', '')
    state_data = _get_and_delete_auth_oauth_state(bond_provider, state)
    if state_data is None:
        LOGGER.warning(f"Invalid OAuth state in {provider} callback - possible CSRF attack or expired state")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter - possible CSRF attack or expired session. Please try logging in again."
        )

    # Extract stored data from state
    code_verifier = state_data.get("code_verifier")
    platform = state_data.get("platform")
    redirect_uri = state_data.get("redirect_uri")

    try:
        config = Config.config()
        provider_config = config.get_oauth2_config(provider)

        oauth_provider = OAuth2ProviderFactory.create_provider(provider, provider_config)

        # T-O4: Pass code_verifier for PKCE token exchange
        user_info = oauth_provider.get_user_info_from_code(auth_code, code_verifier=code_verifier)

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

        # Build JWT payload with user info and Okta metadata
        jwt_data = {
            "sub": user_info.get("email"),
            "name": user_info.get("name"),
            "provider": provider,
            "user_id": user_id,
            # Standard JWT claims for API and MCP authentication
            "iss": "bond-ai",
            "aud": ["bond-ai-api", "mcp-server"]
        }

        # Add Okta-specific metadata if available
        if provider == "okta":
            if user_info.get("sub"):  # Okta sub (unique identifier)
                jwt_data["okta_sub"] = user_info.get("sub")
            if user_info.get("given_name"):
                jwt_data["given_name"] = user_info.get("given_name")
            if user_info.get("family_name"):
                jwt_data["family_name"] = user_info.get("family_name")
            if user_info.get("locale"):
                jwt_data["locale"] = user_info.get("locale")

        access_token = create_access_token(
            data=jwt_data,
            expires_delta=access_token_expires
        )
        LOGGER.info(f"Generated JWT for user: {user_info.get('email')} (provider: {provider})")

        LOGGER.info(f"Auth callback - platform: {platform}")

        # Create a short-lived auth code instead of passing the JWT directly
        auth_code_platform = "mobile" if (platform == 'mobile' and redirect_uri) else None
        opaque_code = _create_auth_code(
            bond_provider=bond_provider,
            access_token=access_token,
            user_id=user_id,
            platform=auth_code_platform,
        )

        # Handle mobile deep link redirect
        if platform == 'mobile' and redirect_uri:
            # T-O1: Validate redirect_uri before redirecting
            import urllib.parse
            decoded_redirect_uri = urllib.parse.unquote(redirect_uri)
            if not is_safe_redirect_url(decoded_redirect_uri):
                LOGGER.warning(f"Rejected unsafe redirect_uri in callback")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid redirect_uri: domain not in allowed list"
                )
            flutter_redirect_url = f"{decoded_redirect_uri}?code={opaque_code}&platform=mobile"
            LOGGER.info(f"Mobile redirect")
        else:
            # Check if this is a web app request (no hash routing)
            user_agent = request.headers.get("user-agent", "").lower()

            # For mobile app or when hash routing is not needed
            if "flutter" in user_agent or jwt_config.JWT_REDIRECT_URI.endswith(":3000"):
                # Use regular routing for mobile app
                flutter_redirect_url = f"{jwt_config.JWT_REDIRECT_URI}/auth-callback?code={opaque_code}"
            else:
                # Use hash routing for web app
                flutter_redirect_url = f"{jwt_config.JWT_REDIRECT_URI}/#/auth-callback?code={opaque_code}"

        LOGGER.info(f"Redirecting to auth callback")
        return RedirectResponse(url=flutter_redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    except HTTPException:
        raise
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

        # Use known provider list to avoid taint from secret-backed config
        known_providers = ["google", "okta", "cognito"]
        provider_names = [p for p in known_providers if p in enabled_configs]

        provider_info = []
        for provider_name in provider_names:
            try:
                info = OAuth2ProviderFactory.get_provider_info(provider_name)
                provider_info.append({
                    "name": provider_name,
                    "login_url": f"/login/{provider_name}",
                    "callback_url": info["callback_path"]
                })
            except Exception as e:
                LOGGER.warning(f"Could not get info for provider {provider_name}")

        # Set default to first enabled provider or google if available
        default_provider = "google" if "google" in provider_names else (
            provider_names[0] if provider_names else "google"
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


@router.post("/auth/provision")
async def provision_user(
    body: ProvisionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider=Depends(get_bond_provider),
):
    """Provision a user account by email (admin only).

    Creates the user if they don't exist, returns existing user_id if they do.
    The returned user_id may differ from the generated hash if the user was
    previously created via OAuth (preserves existing FK relationships).
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can provision accounts",
        )

    generated_id = hashlib.sha256(body.email.encode()).hexdigest()

    user_id, is_new = bond_provider.users.get_or_create_user(
        user_id=generated_id,
        email=body.email,
        name=body.name,
        sign_in_method=body.provider,
    )

    LOGGER.info(f"Admin {current_user.user_id} provisioned user {user_id} (is_new={is_new})")

    return {"user_id": user_id, "email": body.email, "is_new": is_new}


@router.delete("/users/{email}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_by_email(
    email: str,
    current_user: Annotated[User, Depends(get_current_user)],
    bond_provider = Depends(get_bond_provider)
):
    """Delete user by email (admin only)."""
    # Admin authorization check using unified config
    from bondable.bond.config import Config

    # Check if there are any admin users configured
    admin_users = Config.config().get_admin_users()
    if not admin_users:
        LOGGER.error("No admin users configured (ADMIN_USERS or ADMIN_EMAIL); user deletion endpoint is disabled.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin configuration error. Please contact the system administrator."
        )

    # Check if current user is an admin
    if not Config.config().is_admin_user(current_user.email):
        LOGGER.warning(f"Unauthorized delete attempt by {current_user.email} for user {email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can delete other users"
        )

    try:
        LOGGER.info(f"Admin {current_user.email} requested deletion of user: {email}")

        success = bond_provider.users.delete_user_by_email(email, provider=bond_provider)

        if not success:
            LOGGER.warning(f"User with email {email} not found for deletion")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        LOGGER.info(f"Successfully deleted user: {email} by admin {current_user.email}")

    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error deleting user {email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete user"
        )
