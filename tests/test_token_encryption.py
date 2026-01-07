"""
Integration tests for token encryption functionality.
Tests the encryption/decryption of OAuth tokens using JWT secret.
"""

import os
import pytest
import tempfile

# Set up test environment before imports
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key-for-encryption-testing-12345')

from bondable.bond.auth.token_encryption import (
    encrypt_token,
    decrypt_token,
    encrypt_token_safe,
    decrypt_token_safe,
    verify_encryption_setup,
    TokenEncryptionError,
    _derive_encryption_key,
    get_encryption_key
)


class TestTokenEncryption:
    """Test token encryption and decryption"""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption work correctly"""
        original_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-token-payload"

        encrypted = encrypt_token(original_token)
        decrypted = decrypt_token(encrypted)

        assert decrypted == original_token
        assert encrypted != original_token  # Should be different

    def test_encryption_produces_different_output(self):
        """Test that same token encrypted twice produces different ciphertext (Fernet uses random IV)"""
        token = "same-token-value"

        encrypted1 = encrypt_token(token)
        encrypted2 = encrypt_token(token)

        # Both should decrypt to same value
        assert decrypt_token(encrypted1) == token
        assert decrypt_token(encrypted2) == token

        # But ciphertext should be different due to random IV
        assert encrypted1 != encrypted2

    def test_encrypt_empty_token_raises_error(self):
        """Test that encrypting empty token raises error"""
        with pytest.raises(TokenEncryptionError) as exc_info:
            encrypt_token("")

        assert "empty token" in str(exc_info.value).lower()

    def test_decrypt_empty_token_raises_error(self):
        """Test that decrypting empty token raises error"""
        with pytest.raises(TokenEncryptionError) as exc_info:
            decrypt_token("")

        assert "empty token" in str(exc_info.value).lower()

    def test_decrypt_invalid_token_raises_error(self):
        """Test that decrypting invalid ciphertext raises error"""
        with pytest.raises(TokenEncryptionError) as exc_info:
            decrypt_token("not-valid-encrypted-data")

        assert "decryption failed" in str(exc_info.value).lower()

    def test_safe_encrypt_none_returns_none(self):
        """Test that encrypt_token_safe with None returns None"""
        result = encrypt_token_safe(None)
        assert result is None

    def test_safe_decrypt_none_returns_none(self):
        """Test that decrypt_token_safe with None returns None"""
        result = decrypt_token_safe(None)
        assert result is None

    def test_safe_functions_work_with_values(self):
        """Test that safe functions work correctly with actual values"""
        original = "test-access-token-12345"

        encrypted = encrypt_token_safe(original)
        assert encrypted is not None

        decrypted = decrypt_token_safe(encrypted)
        assert decrypted == original

    def test_verify_encryption_setup_succeeds(self):
        """Test that verify_encryption_setup works with valid config"""
        result = verify_encryption_setup()
        assert result is True

    def test_encryption_key_derivation_is_deterministic(self):
        """Test that same secret produces same key"""
        key1 = _derive_encryption_key("same-secret")
        key2 = _derive_encryption_key("same-secret")

        assert key1 == key2

    def test_different_secrets_produce_different_keys(self):
        """Test that different secrets produce different keys"""
        key1 = _derive_encryption_key("secret-one")
        key2 = _derive_encryption_key("secret-two")

        assert key1 != key2

    def test_get_encryption_key_uses_env_variable(self):
        """Test that get_encryption_key uses JWT_SECRET_KEY from environment"""
        key = get_encryption_key()
        assert key is not None
        assert len(key) == 44  # Base64 encoded 32-byte key

    def test_long_token_encryption(self):
        """Test encryption of long tokens"""
        # Create a long token (simulating a real OAuth token)
        long_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9." + "a" * 2000

        encrypted = encrypt_token(long_token)
        decrypted = decrypt_token(encrypted)

        assert decrypted == long_token

    def test_special_characters_in_token(self):
        """Test encryption of tokens with special characters"""
        special_token = "token+with/special=chars&more?query#fragment"

        encrypted = encrypt_token(special_token)
        decrypted = decrypt_token(encrypted)

        assert decrypted == special_token

    def test_unicode_in_token(self):
        """Test encryption of tokens with unicode characters"""
        unicode_token = "token-with-unicode-\u00e9\u00e8\u00ea-chars"

        encrypted = encrypt_token(unicode_token)
        decrypted = decrypt_token(encrypted)

        assert decrypted == unicode_token


class TestEncryptionWithMissingSecret:
    """Test encryption behavior when JWT_SECRET_KEY is missing"""

    def test_encrypt_without_secret_raises_error(self):
        """Test that encryption fails without JWT_SECRET_KEY"""
        # Save original value
        original_secret = os.environ.get('JWT_SECRET_KEY')

        try:
            # Remove the secret
            if 'JWT_SECRET_KEY' in os.environ:
                del os.environ['JWT_SECRET_KEY']

            with pytest.raises(TokenEncryptionError) as exc_info:
                encrypt_token("test-token")

            assert "JWT_SECRET_KEY" in str(exc_info.value)

        finally:
            # Restore original value
            if original_secret:
                os.environ['JWT_SECRET_KEY'] = original_secret


class TestEncryptionIntegration:
    """Integration tests simulating real-world scenarios"""

    def test_oauth_token_lifecycle(self):
        """Test complete OAuth token storage lifecycle"""
        # Simulate receiving OAuth tokens - use randomized values to avoid credential patterns
        import secrets
        access_token = f"test_oauth_token_{secrets.token_urlsafe(48)}"
        refresh_token = f"test_refresh_{secrets.token_urlsafe(32)}"

        # Encrypt for storage
        encrypted_access = encrypt_token(access_token)
        encrypted_refresh = encrypt_token_safe(refresh_token)

        # Verify encrypted values are different from original
        assert encrypted_access != access_token
        assert encrypted_refresh != refresh_token

        # Simulate retrieval and decryption
        decrypted_access = decrypt_token(encrypted_access)
        decrypted_refresh = decrypt_token_safe(encrypted_refresh)

        assert decrypted_access == access_token
        assert decrypted_refresh == refresh_token

    def test_multiple_connections_encryption(self):
        """Test encrypting tokens for multiple connections"""
        connections = {
            "atlassian": "atlassian-token-xyz123",
            "google_drive": "google-drive-token-abc456",
            "slack": "slack-token-def789"
        }

        encrypted = {}
        for name, token in connections.items():
            encrypted[name] = encrypt_token(token)

        # Decrypt all and verify
        for name, enc_token in encrypted.items():
            decrypted = decrypt_token(enc_token)
            assert decrypted == connections[name]


# Run with: poetry run pytest tests/test_token_encryption.py -v
