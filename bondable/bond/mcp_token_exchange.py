"""RFC 8693 token-exchange client for the bond-mcps Authorization Server.

For bond-mcps-*managed* MCPs, bond-ai must not present its HS256 Bond JWT to
the MCP pod directly. Instead it exchanges that JWT at the bond-mcps
Authorization Server (RFC 8693, ``POST {AS}/oauth/token``) for a short-lived
access token scoped to the target MCP (``resource``) and presents that token.

This module is INERT unless ``BOND_MCPS_AS_BASE_URL`` is set:
:func:`is_exchange_enabled` returns ``False`` and callers keep sending the Bond
JWT directly (the local dev-combined-jwt flow), byte-for-byte unchanged.

Exchanged tokens are cached (thread-safe, shared across the sync and async
fetchers) keyed by ``(subject "sub", resource)`` and reused until 30 s before
expiry.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Dict, Optional, Tuple

import httpx
import jwt

LOGGER = logging.getLogger(__name__)

ENV_AS_BASE_URL = "BOND_MCPS_AS_BASE_URL"
ENV_TIMEOUT = "BOND_MCPS_TOKEN_EXCHANGE_TIMEOUT_SECONDS"

DEFAULT_TIMEOUT_SECONDS = 10.0

GRANT_TYPE = "urn:ietf:params:oauth:grant-type:token-exchange"
SUBJECT_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:jwt"  # nosec B105 - RFC 8693 URN, not a secret
CLIENT_ID = "bond-ai"

# Refresh a cached token this many seconds before its reported expiry, so an
# in-flight MCP call never rides a token that lapses mid-request.
_EXPIRY_SKEW_SECONDS = 30


class TokenExchangeError(Exception):
    """Raised when the AS token exchange fails (config/network/HTTP/parse)."""


# key: (subject "sub", resource) -> value: (access_token, monotonic expiry)
_cache: Dict[Tuple[str, str], Tuple[str, float]] = {}
_cache_lock = threading.Lock()


def is_exchange_enabled() -> bool:
    """True when ``BOND_MCPS_AS_BASE_URL`` is set (and non-empty)."""
    return bool(os.getenv(ENV_AS_BASE_URL, "").strip())


def reset_cache() -> None:
    """Clear the shared token cache (tests)."""
    with _cache_lock:
        _cache.clear()


def _base_url() -> str:
    base = os.getenv(ENV_AS_BASE_URL, "").strip()
    if not base:
        raise TokenExchangeError(f"{ENV_AS_BASE_URL} is not set; token exchange is disabled")
    return base.rstrip("/")


def _timeout(timeout: Optional[float]) -> float:
    if timeout is not None:
        return timeout
    raw = os.getenv(ENV_TIMEOUT, "").strip()
    if raw:
        try:
            return float(raw)
        except ValueError:
            LOGGER.warning("invalid %s=%r; using %ss", ENV_TIMEOUT, raw, DEFAULT_TIMEOUT_SECONDS)
    return DEFAULT_TIMEOUT_SECONDS


def _subject_sub(subject_token: str) -> str:
    """Extract the ``sub`` claim without verifying the signature (cache key only)."""
    try:
        claims = jwt.decode(subject_token, options={"verify_signature": False})
    except jwt.PyJWTError as exc:
        raise TokenExchangeError(f"subject token is not a valid JWT: {exc}") from exc
    sub = claims.get("sub")
    if not sub:
        raise TokenExchangeError("subject token has no 'sub' claim")
    return str(sub)


def _cache_key(subject_token: str, resource: str) -> Tuple[str, str]:
    return (_subject_sub(subject_token), resource)


def _cached(key: Tuple[str, str]) -> Optional[str]:
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        token, expiry = entry
        if time.monotonic() >= expiry:
            _cache.pop(key, None)
            return None
        return token


def _store(key: Tuple[str, str], token: str, expires_in: object) -> None:
    # Only cache when the AS reports an expiry long enough to be worth reusing.
    if not isinstance(expires_in, (int, float)) or isinstance(expires_in, bool):
        return
    if expires_in <= _EXPIRY_SKEW_SECONDS:
        return
    with _cache_lock:
        _cache[key] = (token, time.monotonic() + float(expires_in) - _EXPIRY_SKEW_SECONDS)


def _form(subject_token: str, resource: str) -> Dict[str, str]:
    return {
        "grant_type": GRANT_TYPE,
        "subject_token": subject_token,
        "subject_token_type": SUBJECT_TOKEN_TYPE,
        "resource": resource,
        "client_id": CLIENT_ID,
    }


def _parse(status_code: int, text: str, payload_json) -> Tuple[str, object]:
    if status_code != 200:
        raise TokenExchangeError(f"AS token exchange returned HTTP {status_code}: {text[:500]}")
    if not isinstance(payload_json, dict):
        raise TokenExchangeError("AS token exchange response was not a JSON object")
    token = payload_json.get("access_token")
    if not isinstance(token, str) or not token.strip():
        raise TokenExchangeError("AS token exchange response missing access_token")
    return token.strip(), payload_json.get("expires_in")


def exchange_token_sync(subject_token: str, resource: str, timeout: Optional[float] = None) -> str:
    """Exchange ``subject_token`` for an AS access token scoped to ``resource``.

    Returns a cached token when one is still valid. Raises
    :class:`TokenExchangeError` on config/network/HTTP/parse failure.
    """
    key = _cache_key(subject_token, resource)
    cached = _cached(key)
    if cached is not None:
        return cached

    url = f"{_base_url()}/oauth/token"
    try:
        with httpx.Client(timeout=_timeout(timeout)) as client:  # nosec B113 - timeout always set
            resp = client.post(url, data=_form(subject_token, resource))
            token, expires_in = _parse(resp.status_code, resp.text, _safe_json(resp))
    except httpx.HTTPError as exc:
        raise TokenExchangeError(f"AS token exchange request failed: {type(exc).__name__}: {exc}") from exc

    _store(key, token, expires_in)
    return token


async def exchange_token(subject_token: str, resource: str, timeout: Optional[float] = None) -> str:
    """Async variant of :func:`exchange_token_sync` (shares the same cache)."""
    key = _cache_key(subject_token, resource)
    cached = _cached(key)
    if cached is not None:
        return cached

    url = f"{_base_url()}/oauth/token"
    try:
        async with httpx.AsyncClient(timeout=_timeout(timeout)) as client:  # nosec B113 - timeout always set
            resp = await client.post(url, data=_form(subject_token, resource))
            token, expires_in = _parse(resp.status_code, resp.text, _safe_json(resp))
    except httpx.HTTPError as exc:
        raise TokenExchangeError(f"AS token exchange request failed: {type(exc).__name__}: {exc}") from exc

    _store(key, token, expires_in)
    return token


def _safe_json(resp: httpx.Response):
    try:
        return resp.json()
    except ValueError:
        return None
