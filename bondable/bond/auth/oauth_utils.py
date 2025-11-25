"""
Shared OAuth utilities for MCP authentication.

This module provides common OAuth functionality used across MCP routers,
including PKCE generation and OAuth state management.
"""

import secrets
import hashlib
import base64
import logging
from datetime import datetime
from typing import Optional, Union

LOGGER = logging.getLogger(__name__)


def safe_isoformat(value: Union[str, datetime, None]) -> Optional[str]:
    """
    Safely convert a datetime or string to ISO format string.

    SQLite returns datetime columns as strings, so we need to handle both cases.

    Args:
        value: A datetime object, ISO format string, or None

    Returns:
        ISO format string or None
    """
    if value is None:
        return None
    if isinstance(value, str):
        # Already a string, return as-is (assuming it's valid ISO format)
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    # Unknown type, try to convert to string
    LOGGER.warning(f"Unexpected type for isoformat: {type(value)}")
    return str(value)


def generate_pkce_pair() -> tuple[str, str]:
    """
    Generate a PKCE (Proof Key for Code Exchange) code verifier and challenge.

    PKCE is used to prevent authorization code interception attacks in
    public OAuth clients (like mobile apps or SPAs).

    Returns:
        Tuple of (code_verifier, code_challenge)
        - code_verifier: A cryptographically random string (43-128 characters)
        - code_challenge: SHA-256 hash of the verifier, base64url encoded
    """
    # Generate code verifier (43-128 characters per RFC 7636)
    code_verifier = secrets.token_urlsafe(64)

    # Generate code challenge (SHA256 hash of verifier, base64url encoded)
    code_challenge_bytes = hashlib.sha256(code_verifier.encode('ascii')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge_bytes).decode('ascii').rstrip('=')

    return code_verifier, code_challenge


def generate_oauth_state(prefix: Optional[str] = None) -> str:
    """
    Generate a cryptographically secure OAuth state parameter.

    The state parameter is used for CSRF protection in OAuth flows.

    Args:
        prefix: Optional prefix to add to the state for identification

    Returns:
        A secure random string suitable for use as an OAuth state parameter
    """
    state = secrets.token_urlsafe(32)
    if prefix:
        return f"{prefix}_{state}"
    return state


def validate_oauth_state(state: str, stored_state: str) -> bool:
    """
    Validate an OAuth state parameter against the stored value.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        state: The state parameter received in the callback
        stored_state: The state parameter that was stored during authorization

    Returns:
        True if states match, False otherwise
    """
    return secrets.compare_digest(state, stored_state)


# User-Agent header for MCP client requests
# Some MCP servers (like Atlassian) require a User-Agent header
MCP_USER_AGENT = 'Bond-AI-MCP-Client/1.0'


def get_mcp_default_headers() -> dict:
    """
    Get default headers for MCP client requests.

    Returns:
        Dictionary of default headers including User-Agent
    """
    return {
        'User-Agent': MCP_USER_AGENT
    }
