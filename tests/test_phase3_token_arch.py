"""
Comprehensive tests for Phase 3 token architecture:
- Authorization code exchange (auth callback -> code -> token/cookie)
- Cookie-based authentication (dual auth: cookie + bearer)
- Token revocation via POST /auth/logout
- CSRF middleware (double-submit cookie pattern)
- Edge cases (concurrent redemption, malformed cookies, revocation cleanup)
"""
import pytest
import os
import tempfile
import secrets
import time
from datetime import timedelta, datetime, timezone
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

# --- Test Database Setup (must happen before app import) ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ['OAUTH2_ENABLED_PROVIDERS'] = 'cognito'
os.environ['COOKIE_SECURE'] = 'false'  # Allow non-HTTPS cookies in tests

from bondable.rest.main import app
from bondable.rest.utils.auth import create_access_token
from bondable.bond.config import Config
from starlette.testclient import TestClient

jwt_config = Config.config().get_jwt_config()
TEST_USER_EMAIL = "test@example.com"
TEST_USER_ID = "test-user-id-123"


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    """Clean up test database after session."""
    yield
    db_path = TEST_METADATA_DB_URL.replace("sqlite:///", "")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
def test_client():
    return TestClient(app)


def _make_token(user_id=TEST_USER_ID, email=TEST_USER_EMAIL, expires_minutes=15):
    """Create a valid JWT for testing."""
    return create_access_token(
        data={
            "sub": email,
            "name": "Test User",
            "provider": "cognito",
            "user_id": user_id,
            "iss": "bond-ai",
            "aud": ["bond-ai-api", "mcp-server"],
        },
        expires_delta=timedelta(minutes=expires_minutes),
    )


def _make_auth_code(bond_provider, token=None, user_id=TEST_USER_ID, platform=None):
    """Insert an auth code into the database and return the code string."""
    from bondable.bond.providers.metadata import AuthCode

    if token is None:
        token = _make_token(user_id=user_id)
    code = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    with bond_provider.metadata.get_db_session() as session:
        auth_code = AuthCode(
            code=code,
            access_token=token,
            user_id=user_id,
            platform=platform,
            created_at=now,
            expires_at=now + timedelta(seconds=60),
        )
        session.add(auth_code)
        session.commit()
    return code


def _make_expired_auth_code(bond_provider, user_id=TEST_USER_ID):
    """Insert an already-expired auth code."""
    from bondable.bond.providers.metadata import AuthCode

    token = _make_token(user_id=user_id)
    code = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    with bond_provider.metadata.get_db_session() as session:
        auth_code = AuthCode(
            code=code,
            access_token=token,
            user_id=user_id,
            platform=None,
            created_at=now - timedelta(seconds=120),
            expires_at=now - timedelta(seconds=60),
        )
        session.add(auth_code)
        session.commit()
    return code


@pytest.fixture
def bond_provider():
    from bondable.rest.dependencies.providers import get_bond_provider
    return get_bond_provider()


# ===========================================================================
# TestAuthCodeExchange
# ===========================================================================
class TestAuthCodeExchange:
    """Authorization code exchange tests."""

    def test_auth_callback_returns_code_not_token(self, test_client, bond_provider):
        """Auth callback should redirect with ?code= not ?token=."""
        mock_user_info = {
            "sub": "cognito-123",
            "email": "callbacktest@example.com",
            "name": "Callback Test",
        }
        mock_provider = MagicMock()
        mock_provider.get_user_info_from_code.return_value = mock_user_info

        mock_users = MagicMock()
        mock_users.get_or_create_user.return_value = ("user-cb-123", False)

        # Pre-insert OAuth state (using AuthOAuthState — no FK to users)
        from bondable.bond.providers.metadata import AuthOAuthState
        state_val = secrets.token_urlsafe(16)
        with bond_provider.metadata.get_db_session() as session:
            session.add(AuthOAuthState(
                state=state_val,
                provider_name="cognito",
                code_verifier="test_verifier",
                redirect_uri="",
                platform="",
            ))
            session.commit()

        with patch("bondable.rest.routers.auth.OAuth2ProviderFactory") as mock_factory:
            mock_factory.create_provider.return_value = mock_provider

            from bondable.rest.dependencies.providers import get_bond_provider as real_get
            real_bp = real_get()
            real_bp.users = mock_users

            from bondable.rest.dependencies.providers import get_bond_provider
            app.dependency_overrides[get_bond_provider] = lambda: real_bp

            try:
                response = test_client.get(
                    f"/auth/cognito/callback?code=test_auth_code&state={state_val}",
                    follow_redirects=False,
                )
                assert response.status_code == 307
                location = response.headers["location"]
                assert "code=" in location
                assert "token=" not in location
            finally:
                app.dependency_overrides.clear()

    def test_code_exchange_returns_jwt_for_mobile(self, test_client, bond_provider):
        """POST /auth/token with mobile code returns bearer token."""
        code = _make_auth_code(bond_provider, platform="mobile")
        response = test_client.post("/auth/token", json={"code": code})
        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert "access_token" in data

    def test_code_exchange_sets_cookies_for_web(self, test_client, bond_provider):
        """POST /auth/token with web code sets HttpOnly cookies."""
        code = _make_auth_code(bond_provider, platform=None)
        response = test_client.post("/auth/token", json={"code": code})
        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "cookie"

        # Check cookies were set
        cookies = response.cookies
        assert "bond_session" in cookies
        assert "bond_csrf" in cookies

    def test_code_is_single_use(self, test_client, bond_provider):
        """Second exchange with same code returns 400."""
        code = _make_auth_code(bond_provider)
        resp1 = test_client.post("/auth/token", json={"code": code})
        assert resp1.status_code == 200

        resp2 = test_client.post("/auth/token", json={"code": code})
        assert resp2.status_code == 400
        assert "already been used" in resp2.json()["detail"]

    def test_expired_code_rejected(self, test_client, bond_provider):
        """Code older than 60s returns 400."""
        code = _make_expired_auth_code(bond_provider)
        response = test_client.post("/auth/token", json={"code": code})
        assert response.status_code == 400
        assert "expired" in response.json()["detail"]

    def test_invalid_code_rejected(self, test_client):
        """Nonexistent code returns 400."""
        response = test_client.post("/auth/token", json={"code": "nonexistent-code"})
        assert response.status_code == 400
        assert "Invalid" in response.json()["detail"]


# ===========================================================================
# TestCookieAuth
# ===========================================================================
class TestCookieAuth:
    """Cookie-based authentication tests."""

    def test_request_with_cookie_succeeds(self, test_client):
        """bond_session cookie authenticates request."""
        token = _make_token()
        test_client.cookies.set("bond_session", token)
        try:
            response = test_client.get("/users/me")
            assert response.status_code == 200
            assert response.json()["email"] == TEST_USER_EMAIL
        finally:
            test_client.cookies.clear()

    def test_request_with_bearer_still_works(self, test_client):
        """Backward compat: Bearer token still works."""
        token = _make_token()
        response = test_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["email"] == TEST_USER_EMAIL

    def test_request_without_auth_returns_401(self, test_client):
        """No cookie, no bearer returns 401."""
        response = test_client.get("/users/me")
        assert response.status_code == 401

    def test_session_persists_across_requests(self, test_client, bond_provider):
        """Simulate browser refresh: login via code exchange, then make requests with only cookies.

        This tests the critical flow: login → refresh → stay logged in.
        After code exchange sets cookies, subsequent requests (like after a page refresh)
        should authenticate via the bond_session cookie without any Authorization header.
        """
        # Clear revocation cache to avoid interference from other tests
        from bondable.rest.dependencies.auth import _revocation_cache
        _revocation_cache.clear()

        # Step 1: Exchange auth code for cookies (simulates initial login)
        code = _make_auth_code(bond_provider, platform=None)  # web platform
        exchange_resp = test_client.post("/auth/token", json={"code": code})
        assert exchange_resp.status_code == 200
        assert exchange_resp.json()["token_type"] == "cookie"

        # Verify cookies were set
        assert "bond_session" in exchange_resp.cookies
        assert "bond_csrf" in exchange_resp.cookies

        # Step 2: Simulate "browser refresh" — set cookies explicitly on client
        # (TestClient may not auto-persist Set-Cookie from responses in all cases)
        bond_session_value = exchange_resp.cookies.get("bond_session")
        bond_csrf_value = exchange_resp.cookies.get("bond_csrf")
        assert bond_session_value is not None, "bond_session cookie not in response"
        assert bond_csrf_value is not None, "bond_csrf cookie not in response"

        test_client.cookies.set("bond_session", bond_session_value)
        test_client.cookies.set("bond_csrf", bond_csrf_value)

        refresh_resp = test_client.get("/users/me")
        assert refresh_resp.status_code == 200
        assert refresh_resp.json()["email"] == TEST_USER_EMAIL

        # Step 3: Verify a POST also works with CSRF token (simulates user action after refresh)
        csrf_token = exchange_resp.cookies.get("bond_csrf")
        logout_resp = test_client.post(
            "/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert logout_resp.status_code == 200

        # Step 4: After logout, cookie should be cleared and auth should fail
        test_client.cookies.clear()
        post_logout_resp = test_client.get("/users/me")
        assert post_logout_resp.status_code == 401

    def test_cookie_and_bearer_both_present_bearer_wins(self, test_client):
        """Bearer takes precedence when both are present."""
        bearer_token = _make_token(user_id="bearer-user", email="bearer@example.com")
        cookie_token = _make_token(user_id="cookie-user", email="cookie@example.com")

        test_client.cookies.set("bond_session", cookie_token)
        try:
            response = test_client.get(
                "/users/me",
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
            assert response.status_code == 200
            assert response.json()["email"] == "bearer@example.com"
        finally:
            test_client.cookies.clear()


# ===========================================================================
# TestTokenRevocation
# ===========================================================================
class TestTokenRevocation:
    """Token revocation tests."""

    def test_logout_revokes_token(self, test_client, bond_provider):
        """POST /auth/logout inserts jti, subsequent request fails."""
        # Clear any stale cache
        from bondable.rest.dependencies.auth import _revocation_cache
        _revocation_cache.clear()

        token = _make_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Verify token works before logout
        resp = test_client.get("/users/me", headers=headers)
        assert resp.status_code == 200

        # Logout
        logout_resp = test_client.post("/auth/logout", headers=headers)
        assert logout_resp.status_code == 200

        # Token should now be rejected
        resp2 = test_client.get("/users/me", headers=headers)
        assert resp2.status_code == 401

    def test_logout_clears_cookies(self, test_client, bond_provider):
        """Logout response clears bond_session and bond_csrf cookies when cookie auth is used."""
        from bondable.rest.dependencies.auth import _revocation_cache
        _revocation_cache.clear()

        token = _make_token()
        test_client.cookies.set("bond_session", token)
        test_client.cookies.set("bond_csrf", "some-csrf-value")
        try:
            # Need CSRF token for POST with cookie auth, OR use bearer
            # Use bearer header so CSRF middleware doesn't block us
            response = test_client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
                cookies={"bond_session": token},
            )
            assert response.status_code == 200

            # Check that cookie-clearing Set-Cookie headers are present
            set_cookies = response.headers.getlist("set-cookie") if hasattr(response.headers, 'getlist') else [
                v for k, v in response.headers.multi_items() if k.lower() == "set-cookie"
            ]
            cookie_names = " ".join(set_cookies).lower()
            assert "bond_session" in cookie_names
            assert "bond_csrf" in cookie_names
        finally:
            test_client.cookies.clear()

    def test_revoked_token_rejected(self, test_client, bond_provider):
        """Request with revoked jti returns 401."""
        import jwt as pyjwt
        from bondable.bond.providers.metadata import RevokedToken
        from bondable.rest.dependencies.auth import _revocation_cache
        _revocation_cache.clear()

        token = _make_token()
        payload = pyjwt.decode(token, options={"verify_signature": False})
        jti = payload["jti"]

        # Insert revocation directly
        with bond_provider.metadata.get_db_session() as session:
            session.add(RevokedToken(
                jti=jti,
                user_id=TEST_USER_ID,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            ))
            session.commit()

        response = test_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


# ===========================================================================
# TestCSRF
# ===========================================================================
class TestCSRF:
    """CSRF middleware tests."""

    def test_post_with_cookie_no_csrf_returns_403(self, test_client):
        """Cookie auth + no X-CSRF-Token -> 403."""
        token = _make_token()
        test_client.cookies.set("bond_session", token)
        try:
            response = test_client.post("/users/me", content="{}")
            assert response.status_code == 403
            assert "CSRF" in response.json()["detail"]
        finally:
            test_client.cookies.clear()

    def test_post_with_cookie_and_csrf_succeeds(self, test_client):
        """Cookie auth + matching X-CSRF-Token passes CSRF check."""
        token = _make_token()
        csrf_value = "test-csrf-token-value"
        test_client.cookies.set("bond_session", token)
        test_client.cookies.set("bond_csrf", csrf_value)
        try:
            # Use /auth/logout as a real POST endpoint that accepts cookie auth
            response = test_client.post(
                "/auth/logout",
                headers={"X-CSRF-Token": csrf_value},
            )
            # Should pass CSRF check (200 from logout, not 403)
            assert response.status_code == 200
        finally:
            test_client.cookies.clear()

    def test_post_with_bearer_skips_csrf(self, test_client):
        """Bearer auth + no X-CSRF-Token -> success (CSRF skipped)."""
        token = _make_token()
        response = test_client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    def test_get_request_skips_csrf(self, test_client):
        """GET with cookie auth -> success (safe method)."""
        token = _make_token()
        test_client.cookies.set("bond_session", token)
        try:
            response = test_client.get("/users/me")
            assert response.status_code == 200
        finally:
            test_client.cookies.clear()

    def test_auth_token_endpoint_skips_csrf(self, test_client, bond_provider):
        """POST /auth/token -> no CSRF check (exempt endpoint)."""
        code = _make_auth_code(bond_provider)
        # No cookies, no CSRF headers — should still work
        response = test_client.post("/auth/token", json={"code": code})
        assert response.status_code == 200


# ===========================================================================
# TestEdgeCases
# ===========================================================================
class TestEdgeCases:
    """Edge case tests."""

    def test_concurrent_code_redemption(self, test_client, bond_provider):
        """Ensure single-use under concurrent attempts."""
        code = _make_auth_code(bond_provider, platform="mobile")
        results = []

        def redeem():
            client = TestClient(app)
            resp = client.post("/auth/token", json={"code": code})
            results.append(resp.status_code)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(redeem) for _ in range(2)]
            for f in futures:
                f.result()

        # Exactly one should succeed, one should fail
        assert sorted(results) == [200, 400]

    def test_malformed_cookie_returns_401(self, test_client):
        """Garbled cookie value -> 401."""
        test_client.cookies.set("bond_session", "not-a-valid-jwt-at-all")
        try:
            response = test_client.get("/users/me")
            assert response.status_code == 401
        finally:
            test_client.cookies.clear()

    def test_expired_revocation_records_cleaned(self, bond_provider):
        """Old revocation records with past expires_at can be cleaned up."""
        from bondable.bond.providers.metadata import RevokedToken

        # Insert an expired revocation
        with bond_provider.metadata.get_db_session() as session:
            session.add(RevokedToken(
                jti="old-jti-cleanup-test",
                user_id=TEST_USER_ID,
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            ))
            session.commit()

        # Verify it exists
        with bond_provider.metadata.get_db_session() as session:
            record = session.query(RevokedToken).filter(
                RevokedToken.jti == "old-jti-cleanup-test"
            ).first()
            assert record is not None

        # Clean up expired records (can be done periodically)
        with bond_provider.metadata.get_db_session() as session:
            now = datetime.now(timezone.utc)
            deleted = session.query(RevokedToken).filter(
                RevokedToken.expires_at < now
            ).delete()
            session.commit()
            assert deleted >= 1

        # Verify it's gone
        with bond_provider.metadata.get_db_session() as session:
            record = session.query(RevokedToken).filter(
                RevokedToken.jti == "old-jti-cleanup-test"
            ).first()
            assert record is None
