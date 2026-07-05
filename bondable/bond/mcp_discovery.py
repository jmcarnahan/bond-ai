"""MCP discovery client.

bond-ai no longer hard-configures the list of MCP servers and their endpoints.
Instead it fetches the set of available MCPs from one or more discovery
endpoints (``GET <url>`` for each URL in ``BOND_MCPS_DISCOVERY_URL``), each of
which returns::

    {"mcps": [{"name": "atlassian", "display_name": "Atlassian",
               "url": "http://localhost:18003/mcp"}, ...]}

Entries may carry two optional fields (see docs/PLATFORM-CONTRACT.md):

- ``requires_connection`` (bool, default ``true``) — ``true`` means the user
  must run a per-provider connect flow, delegated to the advertising service
  (bond-mcps' /connect routes); ``false`` means the MCP is authorized by the
  Bond JWT for any signed-in user (e.g. sbel-crm) and needs no connect flow.
- ``description`` — human-readable blurb, passed through to the UI.

Everything beyond that (tools, auth, capabilities) is learned via the MCP
protocol itself. Discovery only answers "which MCPs exist and where".

Results are cached in-process per source with a TTL and refreshed lazily on
access (and optionally by a background poller started at app startup) so MCPs
can be added or removed upstream **without restarting bond-ai**. Each source
*fails soft* independently: on a fetch error it keeps that source's last good
result (or contributes nothing if it never succeeded) without affecting the
other sources, and callers fall back to whatever static MCP config bond-ai
still carries. When two sources advertise the same ``name``, the earlier URL
in the configured list wins and a warning is logged.

Configuration (all via environment):

- ``BOND_MCPS_DISCOVERY_URL`` — comma-separated list of discovery URLs. When
  unset, discovery is disabled and :func:`get_discovered_mcps` returns ``[]``
  (pure static config).
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


def get_discovery_urls() -> List[str]:
    """Return the configured discovery URLs (possibly empty when discovery is off).

    ``BOND_MCPS_DISCOVERY_URL`` is a comma-separated list; whitespace around
    entries is ignored, empties are dropped, and duplicates are removed while
    preserving order (order matters: earlier sources win name collisions).
    """
    raw = os.environ.get(ENV_DISCOVERY_URL, "")
    urls: List[str] = []
    for part in raw.split(","):
        url = part.strip()
        if url and url not in urls:
            urls.append(url)
    return urls


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


def _parse_response(payload: Any) -> List[Dict[str, Any]]:
    """Coerce a discovery response into a clean list of MCP entries.

    Malformed entries (missing ``name``/``url`` or wrong types) are skipped so a
    single bad entry never breaks discovery for the others.
    """
    if not isinstance(payload, dict):
        raise DiscoveryError("discovery response is not a JSON object")
    raw = payload.get("mcps")
    if not isinstance(raw, list):
        raise DiscoveryError("discovery response missing 'mcps' list")

    entries: List[Dict[str, Any]] = []
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
        entry: Dict[str, Any] = {
            "name": name.strip(),
            "display_name": display_name.strip(),
            "url": url,
            # Only a literal JSON `false` opts an MCP out of the per-user
            # connect flow; anything else (absent, non-bool) keeps the safe
            # default of a managed connection.
            "requires_connection": item.get("requires_connection") is not False,
        }
        description = item.get("description")
        if isinstance(description, str) and description.strip():
            entry["description"] = description.strip()
        entries.append(entry)
    return entries


class _SourceState:
    """Last-good entries and fetch time for a single discovery URL."""

    __slots__ = ("entries", "fetched_at")

    def __init__(self) -> None:
        self.entries: Optional[List[Dict[str, Any]]] = None
        self.fetched_at: float = 0.0

    def is_fresh(self) -> bool:
        return (
            self.entries is not None
            and (time.monotonic() - self.fetched_at) < _get_ttl_seconds()
        )


class _DiscoveryCache:
    """Thread-safe per-source TTL cache for discovered MCP entries.

    Each configured discovery URL fails soft independently: a fetch error keeps
    that source's last good entries without affecting the others.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sources: Dict[str, _SourceState] = {}
        self._poller: Optional[threading.Thread] = None
        self._poller_stop: Optional[threading.Event] = None

    def reset(self) -> None:
        """Clear cached state (primarily for tests)."""
        with self._lock:
            self._sources = {}

    def _merge_locked(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Merge cached entries across sources in configured order.

        Earlier sources win name collisions (callers must hold ``self._lock``).
        """
        merged: List[Dict[str, Any]] = []
        claimed: Dict[str, str] = {}
        for url in urls:
            state = self._sources.get(url)
            for entry in (state.entries if state else None) or []:
                name = entry["name"]
                if name in claimed:
                    LOGGER.warning(
                        "Discovered MCP %r from %s shadowed by earlier source %s",
                        name, url, claimed[name],
                    )
                    continue
                claimed[name] = url
                merged.append(dict(entry))
        return merged

    def get(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        urls = get_discovery_urls()
        if not urls:
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
                if poller_active or all(
                    self._sources.get(u) is not None and self._sources[u].is_fresh()
                    for u in urls
                ):
                    return self._merge_locked(urls)
            stale = [
                u for u in urls
                if not (self._sources.get(u) is not None and self._sources[u].is_fresh())
            ] if not force_refresh else list(urls)

        # Fetch outside the lock so a slow endpoint doesn't block other readers.
        for url in stale:
            try:
                entries = self._fetch(url)
            except DiscoveryError as exc:
                # Keep this source's last good entries (or nothing if it never
                # succeeded); other sources are unaffected.
                LOGGER.warning(
                    "MCP discovery fetch from %s failed (%s); failing soft", url, exc
                )
                continue
            with self._lock:
                state = self._sources.setdefault(url, _SourceState())
                state.entries = entries
                state.fetched_at = time.monotonic()

        with self._lock:
            return self._merge_locked(urls)

    def _fetch(self, url: str) -> List[Dict[str, Any]]:
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
        """Poll cadence: fast retry until every source's first fetch lands."""
        urls = get_discovery_urls()
        with self._lock:
            never_fetched = any(
                self._sources.get(u) is None or self._sources[u].entries is None
                for u in urls
            )
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
        if not get_discovery_urls():
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


def get_discovered_mcps(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Return the available MCPs merged across all configured discovery sources.

    Returns a list of ``{"name", "display_name", "url", "requires_connection"
    [, "description"]}`` dicts (possibly empty). Never raises: a source outage
    degrades to that source's last good result without affecting the others.
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
