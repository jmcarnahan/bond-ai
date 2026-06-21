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
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10.0


class ConnectError(Exception):
    """Raised when a bond-mcps connect call fails (network/HTTP/parse)."""


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
    url = f"{base}/connect/{name}/ticket"
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
    url = f"{base}/connect/{name}/status"
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


async def delete_connection(
    mcp_url: str,
    name: str,
    jwt_token: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> bool:
    """Delete the user's stored provider token for an MCP via bond-mcps."""
    base = connect_base_url(mcp_url)
    url = f"{base}/connect/{name}"
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
