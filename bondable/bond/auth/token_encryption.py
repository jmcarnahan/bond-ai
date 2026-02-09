"""
Token encryption utilities for secure storage of OAuth tokens.

Uses AES-256-GCM authenticated encryption with a key derived from the
JWT secret via HKDF. This provides 256-bit key strength with authenticated
encryption (no separate HMAC needed).

Security Note:
- Tokens are encrypted at rest in the database
- Decryption only happens when tokens are needed for API calls
- Key is derived from JWT_SECRET_KEY using HKDF with a domain separator
"""

import base64
import logging
import os
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

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
    Derive a 256-bit AES key from the JWT secret using HKDF.

    Uses HKDF with SHA-256 and a domain-specific info parameter to derive
    a key that is distinct from any other use of JWT_SECRET_KEY.

    Args:
        secret: The JWT secret key string

    Returns:
        32-byte (256-bit) raw key suitable for AES-256-GCM
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bits
        salt=None,
        info=b"bond-ai-token-encryption",
    )
    return hkdf.derive(secret.encode('utf-8'))


def get_encryption_key() -> bytes:
    """
    Get the AES-256-GCM encryption key derived from JWT secret.

    Returns:
        32-byte raw encryption key

    Raises:
        TokenEncryptionError: If JWT_SECRET_KEY is not set
    """
    jwt_secret = _get_jwt_secret()
    return _derive_encryption_key(jwt_secret)


def encrypt_token(token: str) -> str:
    """
    Encrypt a token for secure database storage using AES-256-GCM.

    Args:
        token: The plaintext token to encrypt

    Returns:
        Base64-encoded string containing nonce (12 bytes) + ciphertext + GCM tag

    Raises:
        TokenEncryptionError: If encryption fails
    """
    if not token:
        raise TokenEncryptionError("Cannot encrypt empty token")

    try:
        key = get_encryption_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit nonce, recommended for GCM
        ciphertext = aesgcm.encrypt(nonce, token.encode('utf-8'), None)
        # Store as base64: nonce (12 bytes) || ciphertext + GCM tag
        return base64.urlsafe_b64encode(nonce + ciphertext).decode('utf-8')
    except TokenEncryptionError:
        raise
    except Exception as e:
        LOGGER.error(f"Failed to encrypt token: {e}")
        raise TokenEncryptionError(f"Token encryption failed: {e}")


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt a token from database storage using AES-256-GCM.

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
        raw = base64.urlsafe_b64decode(encrypted_token.encode('utf-8'))
        nonce = raw[:12]
        ciphertext = raw[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
    except InvalidTag:
        LOGGER.error("Invalid token: decryption failed - possibly wrong key or corrupted data")
        raise TokenEncryptionError("Token decryption failed: invalid or corrupted token")
    except TokenEncryptionError:
        raise
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
