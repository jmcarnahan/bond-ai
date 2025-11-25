"""
Token encryption utilities for secure storage of OAuth tokens.

Uses Fernet symmetric encryption with a key derived from the JWT secret.
This allows reusing the existing JWT_SECRET_KEY for token encryption
without needing additional secret management.

Security Note:
- Tokens are encrypted at rest in the database
- Decryption only happens when tokens are needed for API calls
- Key is derived from JWT_SECRET_KEY using SHA-256 hashing
"""

import base64
import hashlib
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

LOGGER = logging.getLogger(__name__)


class TokenEncryptionError(Exception):
    """Raised when token encryption or decryption fails."""
    pass


def _get_jwt_secret() -> str:
    """Get JWT secret from environment variable."""
    jwt_secret = os.environ.get("JWT_SECRET_KEY")
    if not jwt_secret:
        raise TokenEncryptionError("JWT_SECRET_KEY environment variable not set")
    return jwt_secret


def _derive_encryption_key(secret: str) -> bytes:
    """
    Derive a Fernet-compatible encryption key from the JWT secret.

    Fernet requires a 32-byte key that is URL-safe base64 encoded.
    We use SHA-256 to hash the JWT secret to get exactly 32 bytes.

    Args:
        secret: The JWT secret key string

    Returns:
        URL-safe base64 encoded 32-byte key suitable for Fernet
    """
    # Hash the secret to get exactly 32 bytes
    key_bytes = hashlib.sha256(secret.encode('utf-8')).digest()
    # Fernet expects URL-safe base64 encoded key
    return base64.urlsafe_b64encode(key_bytes)


def get_encryption_key() -> bytes:
    """
    Get the Fernet encryption key derived from JWT secret.

    Returns:
        URL-safe base64 encoded encryption key

    Raises:
        TokenEncryptionError: If JWT_SECRET_KEY is not set
    """
    jwt_secret = _get_jwt_secret()
    return _derive_encryption_key(jwt_secret)


def encrypt_token(token: str) -> str:
    """
    Encrypt a token for secure database storage.

    Args:
        token: The plaintext token to encrypt

    Returns:
        Base64-encoded encrypted token string

    Raises:
        TokenEncryptionError: If encryption fails
    """
    if not token:
        raise TokenEncryptionError("Cannot encrypt empty token")

    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        encrypted_bytes = fernet.encrypt(token.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        LOGGER.error(f"Failed to encrypt token: {e}")
        raise TokenEncryptionError(f"Token encryption failed: {e}")


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt a token from database storage.

    Args:
        encrypted_token: The base64-encoded encrypted token

    Returns:
        The decrypted plaintext token

    Raises:
        TokenEncryptionError: If decryption fails (invalid key, corrupted data, etc.)
    """
    if not encrypted_token:
        raise TokenEncryptionError("Cannot decrypt empty token")

    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        decrypted_bytes = fernet.decrypt(encrypted_token.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except InvalidToken:
        LOGGER.error("Invalid token: decryption failed - possibly wrong key or corrupted data")
        raise TokenEncryptionError("Token decryption failed: invalid or corrupted token")
    except Exception as e:
        LOGGER.error(f"Failed to decrypt token: {e}")
        raise TokenEncryptionError(f"Token decryption failed: {e}")


def encrypt_token_safe(token: Optional[str]) -> Optional[str]:
    """
    Safely encrypt a token, returning None if input is None.

    Args:
        token: The plaintext token to encrypt, or None

    Returns:
        Encrypted token string, or None if input was None
    """
    if token is None:
        return None
    return encrypt_token(token)


def decrypt_token_safe(encrypted_token: Optional[str]) -> Optional[str]:
    """
    Safely decrypt a token, returning None if input is None.

    Args:
        encrypted_token: The encrypted token string, or None

    Returns:
        Decrypted token string, or None if input was None
    """
    if encrypted_token is None:
        return None
    return decrypt_token(encrypted_token)


def verify_encryption_setup() -> bool:
    """
    Verify that token encryption is properly configured.

    Tests that encryption and decryption work correctly with the current
    JWT_SECRET_KEY configuration.

    Returns:
        True if encryption setup is valid

    Raises:
        TokenEncryptionError: If encryption is not properly configured
    """
    test_token = "test_token_for_verification_12345"
    try:
        encrypted = encrypt_token(test_token)
        decrypted = decrypt_token(encrypted)
        if decrypted != test_token:
            raise TokenEncryptionError("Encryption verification failed: decrypted token doesn't match")
        LOGGER.info("Token encryption setup verified successfully")
        return True
    except TokenEncryptionError:
        raise
    except Exception as e:
        raise TokenEncryptionError(f"Encryption verification failed: {e}")
