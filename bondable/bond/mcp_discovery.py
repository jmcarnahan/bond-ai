"""MCP discovery client.

bond-ai no longer hard-configures the list of MCP servers and their endpoints.
Instead it fetches the set of available MCPs from bond-mcps' discovery endpoint
(``GET <BOND_MCPS_DISCOVERY_URL>``), which returns::

    {"mcps": [{"name": "atlassian", "display_name": "Atlassian",
               "url": "http://localhost:18003/mcp"}, ...]}

Everything beyond the endpoint URL (tools, auth, capabilities) is learned via the
MCP protocol itself. Discovery only answers "which MCPs exist and where".

Results are cached in-process with a TTL and refreshed lazily on access (and
optionally by a background poller started at app startup) so MCPs can be added or
removed in bond-mcps **without restarting bond-ai**. On any fetch error or an
empty response the client *fails soft*: it returns the last good result if one is
cached, otherwise an empty list, and callers fall back to whatever static MCP
config bond-ai still carries.

Configuration (all via environment):

- ``BOND_MCPS_DISCOVERY_URL`` — full discovery URL. When unset, discovery is
  disabled and :func:`get_discovered_mcps` returns ``[]`` (pure static config).
- ``BOND_MCPS_DISCOVERY_TTL_SECONDS`` — cache TTL (default 300).
- ``BOND_MCPS_DISCOVERY_TIMEOUT_SECONDS`` — per-request HTTP timeout (default 5).
"""

from __future__ import annotations

import ipaddress
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

LOGGER = logging.getLogger(__name__)

ENV_DISCOVERY_URL = "BOND_MCPS_DISCOVERY_URL"
ENV_DISCOVERY_TTL = "BOND_MCPS_DISCOVERY_TTL_SECONDS"
ENV_DISCOVERY_TIMEOUT = "BOND_MCPS_DISCOVERY_TIMEOUT_SECONDS"

DEFAULT_TTL_SECONDS = 300
DEFAULT_TIMEOUT_SECONDS = 5.0

# Poller retry interval while the cache has never been populated. Until the
# first successful fetch, waiting a full TTL leaves managed MCPs invisible for
# minutes when bond-ai starts before its discovery upstream is reachable
# (locally `make dev-combined` starts the backend before nginx; in deployment
# a bond-ai pod can start before the bond-mcps AS). Once a fetch has
# succeeded, transient failures fall back to the last-good cache, so the
# normal TTL cadence is fine.
STARTUP_RETRY_SECONDS = 10.0

# SSRF protection: never let a (mis)configured discovery URL reach a cloud
# metadata endpoint. Mirrors the blocklist in
# ``bondable/rest/routers/user_mcp_servers.py`` (localhost is intentionally
# allowed — discovery is localhost in local dev).
_SSRF_BLOCKED_HOSTNAMES = frozenset({
    "metadata.google.internal",
    "169.254.169.254",
    "169.254.170.2",   # AWS ECS task metadata
    "fd00:ec2::254",   # AWS IMDSv2 IPv6
})


class DiscoveryError(Exception):
    """Raised internally when a discovery fetch cannot be completed."""


def get_discovery_url() -> Optional[str]:
    """Return the configured discovery URL, or ``None`` if discovery is off."""
    url = os.environ.get(ENV_DISCOVERY_URL, "").strip()
    return url or None


def _get_ttl_seconds() -> float:
    try:
        return float(os.environ.get(ENV_DISCOVERY_TTL, DEFAULT_TTL_SECONDS))
    except (TypeError, ValueError):
        return float(DEFAULT_TTL_SECONDS)


def _get_timeout_seconds() -> float:
    try:
        return float(os.environ.get(ENV_DISCOVERY_TIMEOUT, DEFAULT_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        return float(DEFAULT_TIMEOUT_SECONDS)


def _validate_url_ssrf(url: str) -> None:
    """Raise :class:`DiscoveryError` if ``url`` targets a blocked host/scheme."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise DiscoveryError(f"discovery URL scheme not allowed: {parsed.scheme!r}")
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise DiscoveryError("discovery URL has no hostname")
    if hostname in _SSRF_BLOCKED_HOSTNAMES:
        raise DiscoveryError(f"discovery URL hostname is blocked: {hostname}")
    try:
        if ipaddress.ip_address(hostname).is_link_local:
            raise DiscoveryError(f"discovery URL hostname is blocked (link-local): {hostname}")
    except ValueError:
        pass  # not an IP literal — exact-match check above is sufficient


def _parse_response(payload: Any) -> List[Dict[str, str]]:
    """Coerce a discovery response into a clean list of MCP entries.

    Malformed entries (missing ``name``/``url`` or wrong types) are skipped so a
    single bad entry never breaks discovery for the others.
    """
    if not isinstance(payload, dict):
        raise DiscoveryError("discovery response is not a JSON object")
    raw = payload.get("mcps")
    if not isinstance(raw, list):
        raise DiscoveryError("discovery response missing 'mcps' list")

    entries: List[Dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        url = item.get("url")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(url, str) or not url.strip():
            continue
        url = url.strip()
        # SSRF defense-in-depth: bond-ai dials these URLs server-side with the
        # user's Bond JWT attached (connect flow + tool calls), so a poisoned or
        # MITM'd discovery response must never point us at a metadata/link-local
        # endpoint. Drop offenders rather than trust the discovery source blindly.
        try:
            _validate_url_ssrf(url)
        except DiscoveryError as exc:
            LOGGER.warning("Skipping discovered MCP %r: %s", name.strip(), exc)
            continue
        display_name = item.get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            display_name = name
        entries.append({
            "name": name.strip(),
            "display_name": display_name.strip(),
            "url": url,
        })
    return entries


class _DiscoveryCache:
    """Thread-safe TTL cache for discovered MCP entries with fail-soft refresh."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: Optional[List[Dict[str, str]]] = None
        self._fetched_at: float = 0.0
        self._poller: Optional[threading.Thread] = None
        self._poller_stop: Optional[threading.Event] = None

    def reset(self) -> None:
        """Clear cached state (primarily for tests)."""
        with self._lock:
            self._entries = None
            self._fetched_at = 0.0

    def _is_fresh(self) -> bool:
        return (
            self._entries is not None
            and (time.monotonic() - self._fetched_at) < _get_ttl_seconds()
        )

    def get(self, force_refresh: bool = False) -> List[Dict[str, str]]:
        url = get_discovery_url()
        if not url:
            return []

        with self._lock:
            if not force_refresh:
                # When a background poller owns refreshing (the server runs one via
                # the app lifespan), request threads must NEVER do a synchronous
                # fetch — they may be on an event loop, and a blocking HTTP call
                # would stall the whole worker. Read whatever the poller cached
                # (possibly empty on the brief startup window → the caller falls
                # back to static config until the poller's first refresh lands).
                # Without a poller (scripts/CLI, off the event loop) lazy fetch is
                # the right behaviour, so we only short-circuit when one is alive.
                poller_active = self._poller is not None and self._poller.is_alive()
                if poller_active or self._is_fresh():
                    return list(self._entries or [])

        # Fetch outside the lock so a slow endpoint doesn't block other readers.
        try:
            entries = self._fetch(url)
        except DiscoveryError as exc:
            LOGGER.warning("MCP discovery fetch failed (%s); failing soft", exc)
            with self._lock:
                # Serve the last good result if we have one, else empty.
                return list(self._entries or [])

        with self._lock:
            self._entries = entries
            self._fetched_at = time.monotonic()
            return list(entries)

    def _fetch(self, url: str) -> List[Dict[str, str]]:
        _validate_url_ssrf(url)
        try:
            resp = httpx.get(url, timeout=_get_timeout_seconds())  # nosec B113 - timeout always set (defaults to 5s)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DiscoveryError(f"{type(exc).__name__}: {exc}") from exc
        entries = _parse_response(payload)
        LOGGER.debug("MCP discovery returned %d server(s) from %s", len(entries), url)
        return entries

    def _next_poll_interval(self) -> float:
        """Poll cadence: fast retry until the first successful fetch lands."""
        with self._lock:
            never_fetched = self._entries is None
        ttl = _get_ttl_seconds()
        return min(STARTUP_RETRY_SECONDS, ttl) if never_fetched else ttl

    def start_background_poller(self) -> None:
        """Start a daemon thread that refreshes the cache every TTL seconds.

        Idempotent and a no-op when discovery is disabled. Lazy TTL refresh on
        access already keeps data fresh for active traffic; the poller guarantees
        regular refresh even when nothing is reading (so a newly added MCP shows
        up without waiting for the next request). Until the first fetch
        succeeds it polls every ``STARTUP_RETRY_SECONDS`` instead, so a backend
        that boots before its discovery upstream recovers in seconds, not a
        full TTL.
        """
        if not get_discovery_url():
            return
        with self._lock:
            if self._poller is not None and self._poller.is_alive():
                return
            stop = threading.Event()
            self._poller_stop = stop

            def _loop() -> None:
                while not stop.is_set():
                    try:
                        self.get(force_refresh=True)
                    except Exception:  # noqa: BLE001 - poller must never die
                        LOGGER.debug("MCP discovery poll iteration failed", exc_info=True)
                    stop.wait(self._next_poll_interval())

            poller = threading.Thread(
                target=_loop, name="mcp-discovery-poller", daemon=True
            )
            self._poller = poller
            poller.start()

    def stop_background_poller(self) -> None:
        with self._lock:
            if self._poller_stop is not None:
                self._poller_stop.set()
            self._poller = None
            self._poller_stop = None


_CACHE = _DiscoveryCache()


def get_discovered_mcps(force_refresh: bool = False) -> List[Dict[str, str]]:
    """Return the available MCPs from bond-mcps discovery.

    Returns a list of ``{"name", "display_name", "url"}`` dicts (possibly empty).
    Never raises: a discovery outage degrades to the last good result or ``[]``.
    """
    return _CACHE.get(force_refresh=force_refresh)


def start_background_poller() -> None:
    """Start the periodic discovery refresh thread (call once at app startup)."""
    _CACHE.start_background_poller()


def stop_background_poller() -> None:
    """Stop the periodic discovery refresh thread (for shutdown / tests)."""
    _CACHE.stop_background_poller()


def reset_cache() -> None:
    """Clear the in-process discovery cache (primarily for tests)."""
    _CACHE.reset()
