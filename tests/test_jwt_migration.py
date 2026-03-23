"""
Tests for PyJWT migration from python-jose.

Validates that PyJWT behaves correctly for all JWT usage patterns
in the Bond AI codebase, ensuring the migration from python-jose
introduces no regressions.
"""
import pytest
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import jwt
from jwt.exceptions import (
    InvalidTokenError,
    ExpiredSignatureError,
    InvalidSignatureError,
    DecodeError,
    InvalidAlgorithmError,
)

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='_jwt_migration.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ.setdefault('METADATA_DB_URL', TEST_METADATA_DB_URL)
os.environ.setdefault('JWT_SECRET_KEY', 'test-jwt-migration-secret-key')

from bondable.bond.config import Config

jwt_config = Config.config().get_jwt_config()
SECRET = jwt_config.JWT_SECRET_KEY
ALGORITHM = jwt_config.JWT_ALGORITHM


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


def _make_token(claims: dict, secret: str = SECRET, algorithm: str = ALGORITHM) -> str:
    """Helper to create a JWT token with default expiry."""
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        **claims,
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


class TestJwtRoundTrip:
    """Test basic encode/decode round-trip."""

    def test_encode_decode_round_trip(self):
        """Token encoding and decoding preserves all claims."""
        claims = {
            "sub": "user@example.com",
            "user_id": "user_123",
            "provider": "okta",
            "name": "Test User",
        }
        token = _make_token(claims)

        decoded = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        assert decoded["sub"] == "user@example.com"
        assert decoded["user_id"] == "user_123"
        assert decoded["provider"] == "okta"
        assert decoded["name"] == "Test User"
        assert "exp" in decoded

    def test_encode_returns_str(self):
        """jwt.encode() returns a str (not bytes) in PyJWT 2.x."""
        token = _make_token({"sub": "test@example.com"})
        assert isinstance(token, str)


class TestExpiredToken:
    """Test expired token handling."""

    def test_expired_token_raises_error(self):
        """Expired tokens raise ExpiredSignatureError."""
        payload = {
            "sub": "user@example.com",
            "user_id": "user_123",
            "provider": "okta",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)

        with pytest.raises(ExpiredSignatureError):
            jwt.decode(token, SECRET, algorithms=[ALGORITHM])

    def test_expired_signature_is_invalid_token_error(self):
        """ExpiredSignatureError is a subclass of InvalidTokenError."""
        assert issubclass(ExpiredSignatureError, InvalidTokenError)


class TestInvalidSignature:
    """Test invalid signature handling."""

    def test_wrong_secret_raises_error(self):
        """Decoding with wrong secret raises InvalidSignatureError."""
        token = _make_token({"sub": "user@example.com"})

        with pytest.raises(InvalidSignatureError):
            jwt.decode(token, "wrong-secret-key", algorithms=[ALGORITHM])

    def test_invalid_signature_is_invalid_token_error(self):
        """InvalidSignatureError is a subclass of InvalidTokenError."""
        assert issubclass(InvalidSignatureError, InvalidTokenError)


class TestMissingClaims:
    """Test handling of tokens with missing required claims."""

    def test_missing_sub_claim(self):
        """Token without 'sub' decodes but get_current_user should reject it."""
        token = _make_token({"user_id": "user_123", "provider": "okta"})
        decoded = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        assert decoded.get("sub") is None

    def test_missing_user_id_claim(self):
        """Token without 'user_id' decodes but get_current_user should reject it."""
        token = _make_token({"sub": "user@example.com", "provider": "okta"})
        decoded = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        assert decoded.get("user_id") is None

    def test_missing_provider_claim(self):
        """Token without 'provider' decodes but get_current_user should reject it."""
        token = _make_token({"sub": "user@example.com", "user_id": "user_123"})
        decoded = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        assert decoded.get("provider") is None


class TestTamperedToken:
    """Test tampered token handling."""

    def test_tampered_payload_fails(self):
        """Modifying a token's payload after encoding causes decode to fail."""
        token = _make_token({"sub": "user@example.com", "user_id": "user_123"})

        # Tamper with the payload portion (middle segment)
        parts = token.split(".")
        # Flip a character in the payload
        payload_chars = list(parts[1])
        payload_chars[0] = "A" if payload_chars[0] != "A" else "B"
        parts[1] = "".join(payload_chars)
        tampered_token = ".".join(parts)

        with pytest.raises(InvalidTokenError):
            jwt.decode(tampered_token, SECRET, algorithms=[ALGORITHM])


class TestAlgorithmMismatch:
    """Test algorithm mismatch handling."""

    def test_algorithm_mismatch_raises_error(self):
        """Encoding with HS256 but decoding requiring RS256 fails."""
        token = _make_token({"sub": "user@example.com"}, algorithm="HS256")

        with pytest.raises(InvalidTokenError):
            jwt.decode(token, SECRET, algorithms=["RS256"])


class TestVerifyOptions:
    """Test decode options that match production usage."""

    def test_verify_aud_false(self):
        """verify_aud=False allows tokens without matching audience (production usage)."""
        claims = {
            "sub": "user@example.com",
            "user_id": "user_123",
            "provider": "okta",
            "aud": "mcp-server",
        }
        token = _make_token(claims)

        # Should succeed even though we don't pass audience parameter
        decoded = jwt.decode(
            token, SECRET, algorithms=[ALGORITHM],
            options={"verify_aud": False}
        )
        assert decoded["sub"] == "user@example.com"
        assert decoded["aud"] == "mcp-server"

    def test_verify_signature_false(self):
        """verify_signature=False allows decoding without secret (used in sample_mcp_server.py)."""
        token = _make_token({"sub": "user@example.com", "iss": "bond-ai"})

        decoded = jwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=[ALGORITHM]
        )
        assert decoded["sub"] == "user@example.com"
        assert decoded["iss"] == "bond-ai"


class TestExtraClaims:
    """Test that additional claims survive round-trip."""

    def test_okta_metadata_round_trip(self):
        """Extra claims like okta_sub, given_name etc. survive encode/decode."""
        claims = {
            "sub": "user@example.com",
            "user_id": "user_123",
            "provider": "okta",
            "name": "Test User",
            "okta_sub": "00u1234567890",
            "given_name": "Test",
            "family_name": "User",
            "locale": "en-US",
            "iss": "bond-ai",
            "aud": "mcp-server",
        }
        token = _make_token(claims)

        decoded = jwt.decode(
            token, SECRET, algorithms=[ALGORITHM],
            options={"verify_aud": False}
        )
        assert decoded["okta_sub"] == "00u1234567890"
        assert decoded["given_name"] == "Test"
        assert decoded["family_name"] == "User"
        assert decoded["locale"] == "en-US"
        assert decoded["iss"] == "bond-ai"
        assert decoded["aud"] == "mcp-server"


class TestInvalidTokenErrorCatchAll:
    """Test that InvalidTokenError catches all JWT error subtypes."""

    def test_catches_expired_signature_error(self):
        """InvalidTokenError catches ExpiredSignatureError."""
        payload = {
            "sub": "user@example.com",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)

        with pytest.raises(InvalidTokenError):
            jwt.decode(token, SECRET, algorithms=[ALGORITHM])

    def test_catches_invalid_signature_error(self):
        """InvalidTokenError catches InvalidSignatureError."""
        token = _make_token({"sub": "user@example.com"})

        with pytest.raises(InvalidTokenError):
            jwt.decode(token, "wrong-secret", algorithms=[ALGORITHM])

    def test_catches_decode_error(self):
        """InvalidTokenError catches DecodeError for malformed tokens."""
        with pytest.raises(InvalidTokenError):
            jwt.decode("not.a.valid.jwt", SECRET, algorithms=[ALGORITHM])

    def test_decode_error_is_invalid_token_error(self):
        """DecodeError is a subclass of InvalidTokenError."""
        assert issubclass(DecodeError, InvalidTokenError)


class TestGetCurrentUserIntegration:
    """Test that get_current_user works correctly with PyJWT."""

    @staticmethod
    def _make_mock_request(token: str):
        """Create a mock Request object with a Bearer token."""
        from unittest.mock import MagicMock
        request = MagicMock()
        request.headers = {"authorization": f"Bearer {token}"}
        request.cookies = {}
        return request

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        """A valid token with all required claims returns a User."""
        from bondable.rest.dependencies.auth import get_current_user

        claims = {
            "sub": "testuser@example.com",
            "user_id": "user_test_123",
            "provider": "okta",
            "name": "Test User",
            "okta_sub": "00utest",
            "given_name": "Test",
            "family_name": "User",
            "iss": "bond-ai",
            "aud": "bond-ai-api",
        }
        token = _make_token(claims)

        user = await get_current_user(self._make_mock_request(token))
        assert user.email == "testuser@example.com"
        assert user.user_id == "user_test_123"
        assert user.provider == "okta"
        assert user.name == "Test User"
        assert user.okta_sub == "00utest"
        assert user.given_name == "Test"
        assert user.family_name == "User"

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        """An expired token causes get_current_user to raise 401."""
        from bondable.rest.dependencies.auth import get_current_user
        from fastapi import HTTPException

        payload = {
            "sub": "user@example.com",
            "user_id": "user_123",
            "provider": "okta",
            "iss": "bond-ai",
            "aud": "bond-ai-api",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(self._make_mock_request(token))
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_sub_raises_401(self):
        """A token without 'sub' causes get_current_user to raise 401."""
        from bondable.rest.dependencies.auth import get_current_user
        from fastapi import HTTPException

        token = _make_token({"user_id": "user_123", "provider": "okta", "iss": "bond-ai", "aud": "bond-ai-api"})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(self._make_mock_request(token))
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_user_id_raises_401(self):
        """A token without 'user_id' causes get_current_user to raise 401."""
        from bondable.rest.dependencies.auth import get_current_user
        from fastapi import HTTPException

        token = _make_token({"sub": "user@example.com", "provider": "okta", "iss": "bond-ai", "aud": "bond-ai-api"})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(self._make_mock_request(token))
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_provider_raises_401(self):
        """A token without 'provider' causes get_current_user to raise 401."""
        from bondable.rest.dependencies.auth import get_current_user
        from fastapi import HTTPException

        token = _make_token({"sub": "user@example.com", "user_id": "user_123", "iss": "bond-ai", "aud": "bond-ai-api"})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(self._make_mock_request(token))
        assert exc_info.value.status_code == 401
