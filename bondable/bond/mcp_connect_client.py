"""HTTP client for bond-mcps' per-MCP "connect" (OAuth delegation) endpoints.

For bond-mcps-managed MCPs, bond-ai does NOT drive the provider OAuth flow or
store provider tokens. It delegates to bond-mcps, forwarding the user's Bond JWT
(which bond-mcps validates via the shared secret). These endpoints live on the
same origin as each MCP's ``/mcp`` route (its discovered URL):

    POST   {base}/connect/{name}/ticket   body {return_url} -> {ticket, connect_url}
    GET    {base}/connect/{name}/status                      -> {connected, valid, scopes, expires_at}
    DELETE {base}/connect/{name}                             -> {disconnected}

``base`` is the origin (scheme://host[:port]) of the MCP's discovered URL — the
discovery path (e.g. ``/mcp``) is stripped. All calls forward
``Authorization: Bearer <jwt>``. A missing connect surface (HTTP 404) means the
MCP has no OAuth connection to manage; :func:`get_connect_status` returns ``None``
in that case so callers can omit it from the connectable list.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10.0

# Anything outside this set is stripped before a name is used as a URL path
# segment. MCP/provider names are short identifiers (e.g. "atlassian",
# "ms-graph"), so legitimate values pass through unchanged.
_UNSAFE_NAME_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


class ConnectError(Exception):
    """Raised when a bond-mcps connect call fails (network/HTTP/parse)."""


def _safe_name(name: str) -> str:
    """Sanitize an MCP/provider name for safe use as a URL path segment.

    The connection name originates from a request path parameter, so it must not
    be able to alter the request host/path (SSRF) — strip ``/``, ``@``, ``?`` and
    any other URL-control characters. This also breaks CodeQL's taint chain
    (``py/partial-ssrf``), mirroring the same defense in ``connections.py``'s
    ``oauth_callback``. Legitimate names are unaffected.
    """
    return _UNSAFE_NAME_CHARS.sub("_", name or "")


def connect_base_url(mcp_url: str) -> str:
    """Return the ``scheme://host[:port]`` origin of a discovered MCP URL."""
    parsed = urlparse(mcp_url)
    if not parsed.scheme or not parsed.netloc:
        raise ConnectError(f"invalid MCP URL: {mcp_url!r}")
    return f"{parsed.scheme}://{parsed.netloc}"


def _auth_headers(jwt_token: Optional[str]) -> Dict[str, str]:
    if not jwt_token:
        raise ConnectError("a Bond JWT is required to call bond-mcps connect endpoints")
    return {"Authorization": f"Bearer {jwt_token}", "Accept": "application/json"}


async def mint_connect_ticket(
    mcp_url: str,
    name: str,
    jwt_token: str,
    return_url: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Mint a connect ticket and return the browser ``connect_url``.

    bond-mcps binds the ticket to the JWT's ``sub`` and (per the contract) carries
    ``return_url`` through to the callback so the user is sent back to bond-ai.
    """
    base = connect_base_url(mcp_url)
    url = f"{base}/connect/{_safe_name(name)}/ticket"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                json={"return_url": return_url},
                headers=_auth_headers(jwt_token),
            )
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ConnectError(f"connect ticket failed for {name}: {type(exc).__name__}: {exc}") from exc

    connect_url = payload.get("connect_url") if isinstance(payload, dict) else None
    if not isinstance(connect_url, str) or not connect_url.strip():
        raise ConnectError(f"connect ticket response for {name} missing connect_url")
    return connect_url.strip()


async def get_connect_status(
    mcp_url: str,
    name: str,
    jwt_token: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[Dict[str, Any]]:
    """Return the user's connection status for an MCP, or ``None``.

    ``None`` means the MCP exposes no connect surface (HTTP 404) — i.e. it needs
    no provider connection and should not be shown as connectable. On any other
    error this raises :class:`ConnectError` (callers decide how to fail soft).
    """
    base = connect_base_url(mcp_url)
    url = f"{base}/connect/{_safe_name(name)}/status"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=_auth_headers(jwt_token))
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ConnectError(f"connect status failed for {name}: {type(exc).__name__}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ConnectError(f"connect status response for {name} is not an object")
    return payload


def _iso_expires_at(value: Any) -> Optional[str]:
    """Normalize bond-mcps' ``expires_at`` (epoch seconds) to ISO-8601 UTC.

    bond-ai's REST models (and the Flutter UI) carry ``expires_at`` as an
    ISO string — the same shape the legacy token-cache path produces. None or
    an unparseable value maps to None.
    """
    if value is None:
        return None
    try:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


async def get_connect_status_safe(
    mcp_url: str,
    name: str,
    jwt_token: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[Dict[str, Any]]:
    """:func:`get_connect_status`, but never raises — for status listings.

    Returns the status dict with ``expires_at`` normalized to ISO-8601, or
    ``None`` for "no connect surface" (HTTP 404). When bond-mcps is
    unreachable or errors, returns a disconnected-shaped dict carrying an
    ``"error"`` key, so one bad MCP never fails a whole listing.

    Callers decide what ``None`` means for their surface: the Connections
    screen omits the tile (not a connectable provider), while the tools list
    reports the server as connected (nothing to connect, still usable).
    """
    try:
        status = await get_connect_status(mcp_url, name, jwt_token, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - fail soft; listings must render
        LOGGER.warning(
            "connect status for %s failed; reporting disconnected: %s: %s",
            name, type(exc).__name__, exc,
        )
        return {
            "connected": False,
            "valid": False,
            "scopes": None,
            "expires_at": None,
            "has_refresh_token": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    if status is None:
        return None
    status = dict(status)
    status["expires_at"] = _iso_expires_at(status.get("expires_at"))
    return status


async def delete_connection(
    mcp_url: str,
    name: str,
    jwt_token: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> bool:
    """Delete the user's stored provider token for an MCP via bond-mcps."""
    base = connect_base_url(mcp_url)
    url = f"{base}/connect/{_safe_name(name)}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request("DELETE", url, headers=_auth_headers(jwt_token))
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            payload = resp.json() if resp.content else {}
    except (httpx.HTTPError, ValueError) as exc:
        raise ConnectError(f"disconnect failed for {name}: {type(exc).__name__}: {exc}") from exc

    if isinstance(payload, dict) and "disconnected" in payload:
        return bool(payload["disconnected"])
    return True
