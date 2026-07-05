"""Unit tests for the MCP discovery client and the config overlay.

Covers parsing, TTL caching, the SSRF guard, fail-soft behaviour (outage and
empty response degrade to the last good result / static config), dynamic
add/remove between polls, and Config._overlay_discovered_mcps merge semantics.
"""

import os

import pytest

from bondable.bond import mcp_discovery
from bondable.bond.mcp_discovery import (
    DiscoveryError,
    _parse_response,
    _validate_url_ssrf,
    get_discovered_mcps,
    get_discovery_urls,
)


DISCOVERY_URL = "http://localhost:8000/connections/discovery"
DISCOVERY_URL_2 = "http://localhost:8001/connections/discovery"


class FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("boom", request=None, response=None)

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    """Reset cache + discovery env around every test."""
    mcp_discovery.reset_cache()
    mcp_discovery._CACHE._poller = None  # ensure no stale poller leaks across tests
    monkeypatch.delenv(mcp_discovery.ENV_DISCOVERY_URL, raising=False)
    monkeypatch.delenv(mcp_discovery.ENV_DISCOVERY_TTL, raising=False)
    yield
    mcp_discovery.reset_cache()
    mcp_discovery._CACHE._poller = None


def _set_response(monkeypatch, payload, calls=None):
    """Install a fake httpx.get returning ``payload``; counts calls if given."""
    def fake_get(url, timeout=None):
        if calls is not None:
            calls.append(url)
        return FakeResp(payload)
    monkeypatch.setattr(mcp_discovery.httpx, "get", fake_get)


# --- URL config -----------------------------------------------------------

def test_discovery_disabled_when_url_unset():
    assert get_discovery_urls() == []
    assert get_discovered_mcps() == []


def test_discovery_url_read_from_env(monkeypatch):
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_URL, DISCOVERY_URL)
    assert get_discovery_urls() == [DISCOVERY_URL]


def test_discovery_urls_comma_separated(monkeypatch):
    """Whitespace trimmed, empties dropped, duplicates removed preserving order."""
    monkeypatch.setenv(
        mcp_discovery.ENV_DISCOVERY_URL,
        f" {DISCOVERY_URL} , {DISCOVERY_URL_2},, {DISCOVERY_URL} ",
    )
    assert get_discovery_urls() == [DISCOVERY_URL, DISCOVERY_URL_2]


# --- Parsing --------------------------------------------------------------

def test_parse_skips_malformed_entries():
    payload = {"mcps": [
        {"name": "atlassian", "display_name": "Atlassian", "url": "http://h:1/mcp"},
        {"name": "noformat"},                 # missing url
        {"url": "http://h:2/mcp"},            # missing name
        {"name": "  ", "url": "http://h:3/mcp"},  # blank name
        "not-a-dict",
        {"name": "github", "url": "http://h:4/mcp"},  # missing display_name -> defaults
    ]}
    out = _parse_response(payload)
    assert out == [
        {"name": "atlassian", "display_name": "Atlassian", "url": "http://h:1/mcp",
         "requires_connection": True},
        {"name": "github", "display_name": "github", "url": "http://h:4/mcp",
         "requires_connection": True},
    ]


def test_parse_requires_connection_and_description():
    """Only a literal false opts out of the connect flow; description passes
    through when a non-empty string and is dropped otherwise."""
    payload = {"mcps": [
        {"name": "sbelcrm", "url": "http://h:1/mcp", "requires_connection": False,
         "description": " CRM tools "},
        {"name": "absent", "url": "http://h:2/mcp"},
        {"name": "nonbool", "url": "http://h:3/mcp", "requires_connection": "yes"},
        {"name": "blankdesc", "url": "http://h:4/mcp", "description": "  "},
        {"name": "baddesc", "url": "http://h:5/mcp", "description": 42},
    ]}
    out = {e["name"]: e for e in _parse_response(payload)}
    assert out["sbelcrm"]["requires_connection"] is False
    assert out["sbelcrm"]["description"] == "CRM tools"
    assert out["absent"]["requires_connection"] is True
    assert out["nonbool"]["requires_connection"] is True
    assert "description" not in out["blankdesc"]
    assert "description" not in out["baddesc"]


def test_parse_rejects_non_object_and_missing_list():
    with pytest.raises(DiscoveryError):
        _parse_response(["nope"])
    with pytest.raises(DiscoveryError):
        _parse_response({"no_mcps": []})


def test_parse_drops_ssrf_blocked_urls():
    """A poisoned discovery response pointing at a metadata endpoint is dropped
    so bond-ai never forwards the Bond JWT there."""
    payload = {"mcps": [
        {"name": "good", "url": "http://localhost:18003/mcp"},
        {"name": "evil", "url": "http://169.254.169.254/mcp"},
        {"name": "meta", "url": "http://metadata.google.internal/mcp"},
    ]}
    out = _parse_response(payload)
    assert [e["name"] for e in out] == ["good"]


# --- SSRF guard -----------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "http://169.254.169.254/latest",
    "http://metadata.google.internal/x",
    "ftp://localhost/x",
    "http:///nohost",
])
def test_ssrf_guard_blocks(bad):
    with pytest.raises(DiscoveryError):
        _validate_url_ssrf(bad)


@pytest.mark.parametrize("ok", [
    "http://localhost:8000/connections/discovery",
    "http://auth.bond-mcps.svc.cluster.local:8000/connections/discovery",
    "https://mcps.example.com/connections/discovery",
])
def test_ssrf_guard_allows(ok):
    _validate_url_ssrf(ok)  # no raise


def test_get_discovered_mcps_blocks_ssrf_url(monkeypatch):
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_URL, "http://169.254.169.254/discovery")
    # Should fail soft (SSRF -> DiscoveryError -> empty), never reach httpx.
    called = []
    monkeypatch.setattr(mcp_discovery.httpx, "get", lambda *a, **k: called.append(1))
    assert get_discovered_mcps() == []
    assert called == []


# --- Caching / TTL --------------------------------------------------------

def test_results_cached_within_ttl(monkeypatch):
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_URL, DISCOVERY_URL)
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_TTL, "300")
    calls = []
    _set_response(monkeypatch, {"mcps": [{"name": "a", "url": "http://h/mcp"}]}, calls)

    first = get_discovered_mcps()
    second = get_discovered_mcps()
    assert first == second
    assert len(calls) == 1  # second served from cache


def test_ttl_zero_refetches(monkeypatch):
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_URL, DISCOVERY_URL)
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_TTL, "0")
    calls = []
    _set_response(monkeypatch, {"mcps": [{"name": "a", "url": "http://h/mcp"}]}, calls)

    get_discovered_mcps()
    get_discovered_mcps()
    assert len(calls) == 2  # TTL 0 -> always refetch


def test_dynamic_add_remove_between_polls(monkeypatch):
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_URL, DISCOVERY_URL)
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_TTL, "0")
    state = {"payload": {"mcps": [{"name": "a", "url": "http://h/mcp"}]}}
    monkeypatch.setattr(mcp_discovery.httpx, "get", lambda *a, **k: FakeResp(state["payload"]))

    assert [m["name"] for m in get_discovered_mcps()] == ["a"]
    state["payload"] = {"mcps": [
        {"name": "a", "url": "http://h/mcp"}, {"name": "b", "url": "http://h2/mcp"}]}
    assert [m["name"] for m in get_discovered_mcps()] == ["a", "b"]
    state["payload"] = {"mcps": []}
    assert get_discovered_mcps() == []


# --- Poller as sole fetcher (no event-loop blocking) ----------------------

def test_request_thread_skips_fetch_when_poller_active(monkeypatch):
    """With an active background poller, request-path reads must never trigger a
    synchronous fetch (which could block an event loop). They read the cache."""
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_URL, DISCOVERY_URL)
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_TTL, "0")  # always "stale"
    calls = []
    _set_response(monkeypatch, {"mcps": [{"name": "a", "url": "http://h/mcp"}]}, calls)

    class _AlivePoller:
        def is_alive(self):
            return True

    mcp_discovery._CACHE._poller = _AlivePoller()
    # Cache empty + poller active → return [] (static fallback), NO fetch.
    assert get_discovered_mcps() == []
    assert get_discovered_mcps() == []
    assert calls == []  # request threads never fetched


def test_force_refresh_fetches_even_with_poller(monkeypatch):
    """The poller itself (force_refresh=True) must still fetch."""
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_URL, DISCOVERY_URL)
    calls = []
    _set_response(monkeypatch, {"mcps": [{"name": "a", "url": "http://h/mcp"}]}, calls)

    class _AlivePoller:
        def is_alive(self):
            return True

    mcp_discovery._CACHE._poller = _AlivePoller()
    out = get_discovered_mcps(force_refresh=True)
    assert [m["name"] for m in out] == ["a"]
    assert len(calls) == 1
    # Subsequent request-path read now sees the poller-populated cache.
    assert [m["name"] for m in get_discovered_mcps()] == ["a"]
    assert len(calls) == 1  # still no request-path fetch


def test_poll_interval_fast_until_first_success(monkeypatch):
    """Before any successful fetch the poller retries every
    STARTUP_RETRY_SECONDS (backend booted before its discovery upstream);
    after the first success it settles to the TTL cadence."""
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_URL, DISCOVERY_URL)
    cache = mcp_discovery._CACHE

    # Never fetched (also the state after a failed startup fetch) → fast.
    assert cache._next_poll_interval() == mcp_discovery.STARTUP_RETRY_SECONDS

    def boom(*a, **k):
        import httpx
        raise httpx.ConnectError("down")
    monkeypatch.setattr(mcp_discovery.httpx, "get", boom)
    get_discovered_mcps(force_refresh=True)
    assert cache._next_poll_interval() == mcp_discovery.STARTUP_RETRY_SECONDS

    # A TTL smaller than the retry interval wins (never wait longer than TTL).
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_TTL, "1")
    assert cache._next_poll_interval() == 1.0
    monkeypatch.delenv(mcp_discovery.ENV_DISCOVERY_TTL)

    # First success → normal TTL cadence (even for an empty-but-valid list).
    _set_response(monkeypatch, {"mcps": []})
    get_discovered_mcps(force_refresh=True)
    assert cache._next_poll_interval() == mcp_discovery.DEFAULT_TTL_SECONDS


def test_poller_recovers_quickly_from_failed_startup_fetch(monkeypatch):
    """End-to-end: upstream down when the poller starts → comes up moments
    later → the cache populates within the fast-retry window, not a full TTL."""
    import threading
    import time as _time

    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_URL, DISCOVERY_URL)
    monkeypatch.setattr(mcp_discovery, "STARTUP_RETRY_SECONDS", 0.05)
    upstream_up = threading.Event()

    def flaky_get(url, timeout=None):
        if not upstream_up.is_set():
            import httpx
            raise httpx.ConnectError("nginx not up yet")
        return FakeResp({"mcps": [{"name": "a", "url": "http://h/mcp"}]})
    monkeypatch.setattr(mcp_discovery.httpx, "get", flaky_get)

    mcp_discovery.start_background_poller()
    try:
        upstream_up.set()
        deadline = _time.monotonic() + 5
        while _time.monotonic() < deadline:
            if [m["name"] for m in get_discovered_mcps()] == ["a"]:
                break
            _time.sleep(0.02)
        else:
            pytest.fail("poller did not recover within the fast-retry window")
    finally:
        mcp_discovery.stop_background_poller()


# --- Fail soft ------------------------------------------------------------

def test_failsoft_returns_last_good_on_error(monkeypatch):
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_URL, DISCOVERY_URL)
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_TTL, "0")
    good = {"mcps": [{"name": "a", "url": "http://h/mcp"}]}
    monkeypatch.setattr(mcp_discovery.httpx, "get", lambda *a, **k: FakeResp(good))
    assert [m["name"] for m in get_discovered_mcps()] == ["a"]

    def boom(*a, **k):
        import httpx
        raise httpx.ConnectError("down")
    monkeypatch.setattr(mcp_discovery.httpx, "get", boom)
    # Outage -> serve last good (not empty).
    assert [m["name"] for m in get_discovered_mcps()] == ["a"]


def test_failsoft_empty_when_no_prior_success(monkeypatch):
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_URL, DISCOVERY_URL)

    def boom(*a, **k):
        import httpx
        raise httpx.ConnectError("down")
    monkeypatch.setattr(mcp_discovery.httpx, "get", boom)
    assert get_discovered_mcps() == []


# --- Multiple sources -------------------------------------------------------

def _set_multi_response(monkeypatch, payloads):
    """Install a fake httpx.get dispatching per-URL from ``payloads``.

    A payload value of an Exception instance is raised instead of returned.
    """
    def fake_get(url, timeout=None):
        payload = payloads[url]
        if isinstance(payload, Exception):
            raise payload
        return FakeResp(payload)
    monkeypatch.setattr(mcp_discovery.httpx, "get", fake_get)


def test_multi_source_merge_in_configured_order(monkeypatch):
    monkeypatch.setenv(
        mcp_discovery.ENV_DISCOVERY_URL, f"{DISCOVERY_URL},{DISCOVERY_URL_2}")
    _set_multi_response(monkeypatch, {
        DISCOVERY_URL: {"mcps": [{"name": "atlassian", "url": "http://h:1/mcp"}]},
        DISCOVERY_URL_2: {"mcps": [
            {"name": "sbelcrm", "url": "http://h:2/mcp", "requires_connection": False}]},
    })
    out = get_discovered_mcps()
    assert [m["name"] for m in out] == ["atlassian", "sbelcrm"]
    assert out[0]["requires_connection"] is True
    assert out[1]["requires_connection"] is False


def test_multi_source_per_source_failsoft(monkeypatch):
    """One source down keeps its last good entries without affecting the other;
    a source that never succeeded contributes nothing."""
    import httpx

    monkeypatch.setenv(
        mcp_discovery.ENV_DISCOVERY_URL, f"{DISCOVERY_URL},{DISCOVERY_URL_2}")
    monkeypatch.setenv(mcp_discovery.ENV_DISCOVERY_TTL, "0")

    # B down from the start → A only.
    _set_multi_response(monkeypatch, {
        DISCOVERY_URL: {"mcps": [{"name": "a", "url": "http://h:1/mcp"}]},
        DISCOVERY_URL_2: httpx.ConnectError("down"),
    })
    assert [m["name"] for m in get_discovered_mcps()] == ["a"]

    # B comes up → merged.
    _set_multi_response(monkeypatch, {
        DISCOVERY_URL: {"mcps": [{"name": "a", "url": "http://h:1/mcp"}]},
        DISCOVERY_URL_2: {"mcps": [{"name": "b", "url": "http://h:2/mcp"}]},
    })
    assert [m["name"] for m in get_discovered_mcps()] == ["a", "b"]

    # B goes down again → A fresh + B last-good.
    _set_multi_response(monkeypatch, {
        DISCOVERY_URL: {"mcps": [{"name": "a2", "url": "http://h:3/mcp"}]},
        DISCOVERY_URL_2: httpx.ConnectError("down"),
    })
    assert [m["name"] for m in get_discovered_mcps()] == ["a2", "b"]


def test_multi_source_name_collision_first_wins(monkeypatch):
    monkeypatch.setenv(
        mcp_discovery.ENV_DISCOVERY_URL, f"{DISCOVERY_URL},{DISCOVERY_URL_2}")
    _set_multi_response(monkeypatch, {
        DISCOVERY_URL: {"mcps": [{"name": "github", "url": "http://first/mcp"}]},
        DISCOVERY_URL_2: {"mcps": [
            {"name": "github", "url": "http://second/mcp"},
            {"name": "sbelcrm", "url": "http://second/crm/mcp"},
        ]},
    })
    out = {m["name"]: m for m in get_discovered_mcps()}
    assert set(out) == {"github", "sbelcrm"}
    assert out["github"]["url"] == "http://first/mcp"


# --- Config overlay -------------------------------------------------------

def _overlay(monkeypatch, static, discovered):
    monkeypatch.setattr(
        "bondable.bond.mcp_discovery.get_discovered_mcps",
        lambda force_refresh=False: discovered,
    )
    from bondable.bond.config import Config
    cfg = Config.__new__(Config)
    return cfg._overlay_discovered_mcps(static)


def test_overlay_merges_and_strips_oauth(monkeypatch):
    static = {"mcpServers": {
        "atlassian_v2": {"url": "http://old", "auth_type": "oauth2",
                          "oauth_config": {"scopes": "stale"}, "icon_url": "x.png"},
        "hello": {"command": "python", "args": ["h.py"]},
    }}
    discovered = [
        {"name": "atlassian_v2", "display_name": "Atlassian", "url": "http://localhost:18003/mcp"},
        {"name": "github", "display_name": "GitHub", "url": "http://localhost:18002/mcp"},
    ]
    out = _overlay(monkeypatch, static, discovered)["mcpServers"]

    atl = out["atlassian_v2"]
    assert atl["url"] == "http://localhost:18003/mcp"
    assert atl["auth_type"] == "bond_jwt"
    assert atl["transport"] == "streamable-http"
    assert "oauth_config" not in atl          # stale OAuth dropped
    assert atl["icon_url"] == "x.png"          # annotation preserved
    assert out["hello"] == {"command": "python", "args": ["h.py"]}  # untouched
    assert out["github"]["auth_type"] == "bond_jwt"

    # Discovered servers are marked managed: bond_jwt like internal servers,
    # but their per-user connection status is delegated to bond-mcps (the
    # "non-oauth = always connected" shortcut must not apply to them).
    assert atl["is_managed"] is True
    assert out["github"]["is_managed"] is True
    assert "is_managed" not in out["hello"]


def test_overlay_noop_when_no_discovery(monkeypatch):
    static = {"mcpServers": {"hello": {"command": "python"}}}
    out = _overlay(monkeypatch, static, [])
    assert out == static


def test_overlay_internal_entry_not_managed(monkeypatch):
    """requires_connection=false entries are internal bond_jwt servers: never
    marked is_managed (the "always connected" path in /mcp/tools applies), and
    a stale is_managed from an earlier overlay is removed."""
    static = {"mcpServers": {
        "sbelcrm": {"url": "http://old", "auth_type": "bond_jwt",
                    "description": "Static description", "is_managed": True},
    }}
    discovered = [
        {"name": "sbelcrm", "display_name": "SBEL CRM",
         "url": "http://localhost:8001/mcp", "requires_connection": False,
         "description": "Discovered description"},
        {"name": "fresh", "url": "http://localhost:9999/mcp",
         "requires_connection": False, "description": "From discovery"},
    ]
    out = _overlay(monkeypatch, static, discovered)["mcpServers"]

    crm = out["sbelcrm"]
    assert crm["url"] == "http://localhost:8001/mcp"
    assert crm["auth_type"] == "bond_jwt"
    assert "is_managed" not in crm
    assert crm["description"] == "Static description"   # static annotation wins

    fresh = out["fresh"]
    assert "is_managed" not in fresh
    assert fresh["description"] == "From discovery"     # discovery fills the gap
