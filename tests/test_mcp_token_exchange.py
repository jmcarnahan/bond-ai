"""Unit tests for the bond-mcps RFC 8693 token-exchange client."""

import httpx
import jwt
import pytest

from bondable.bond import mcp_token_exchange as tx


AS_BASE = "https://as.example.com"
_NO_JSON = object()


def _subject(sub="alice@example.com"):
    return jwt.encode({"sub": sub}, "x" * 32, algorithm="HS256")


class FakeResp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = {"access_token": "AS_TOKEN", "expires_in": 300} if payload is None else payload
        self.text = text

    def json(self):
        if self._payload is _NO_JSON:
            raise ValueError("not json")
        return self._payload


@pytest.fixture(autouse=True)
def _reset_cache():
    tx.reset_cache()
    yield
    tx.reset_cache()


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv(tx.ENV_AS_BASE_URL, AS_BASE)


@pytest.fixture
def fake_http(monkeypatch):
    """Patch httpx.Client/AsyncClient; set `handler`, inspect `sync_calls`/`async_calls`."""
    state = {"handler": lambda url, data: FakeResp(), "sync_calls": [], "async_calls": []}

    class FakeSyncClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, data=None):
            state["sync_calls"].append({"url": url, "data": data})
            return state["handler"](url, data)

    class FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None):
            state["async_calls"].append({"url": url, "data": data})
            return state["handler"](url, data)

    monkeypatch.setattr(tx.httpx, "Client", FakeSyncClient)
    monkeypatch.setattr(tx.httpx, "AsyncClient", FakeAsyncClient)
    return state


# --- enabled / disabled ------------------------------------------------------

def test_disabled_when_env_unset(monkeypatch):
    monkeypatch.delenv(tx.ENV_AS_BASE_URL, raising=False)
    assert tx.is_exchange_enabled() is False


def test_enabled_when_env_set(enabled):
    assert tx.is_exchange_enabled() is True


def test_exchange_disabled_raises(monkeypatch):
    monkeypatch.delenv(tx.ENV_AS_BASE_URL, raising=False)
    with pytest.raises(tx.TokenExchangeError):
        tx.exchange_token_sync(_subject(), "res")


# --- request shape -----------------------------------------------------------

def test_form_fields_and_url(enabled, fake_http):
    sub = _subject()
    out = tx.exchange_token_sync(sub, "https://mcp.example.com/mcp")
    assert out == "AS_TOKEN"
    call = fake_http["sync_calls"][0]
    assert call["url"] == f"{AS_BASE}/oauth/token"
    assert call["data"] == {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": sub,
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "resource": "https://mcp.example.com/mcp",
        "client_id": "bond-ai",
    }


def test_base_url_trailing_slash_stripped(monkeypatch, fake_http):
    monkeypatch.setenv(tx.ENV_AS_BASE_URL, AS_BASE + "/")
    tx.exchange_token_sync(_subject(), "res")
    assert fake_http["sync_calls"][0]["url"] == f"{AS_BASE}/oauth/token"


# --- cache -------------------------------------------------------------------

def test_cache_per_sub_and_resource(enabled, fake_http):
    alice = _subject("alice@x")
    bob = _subject("bob@x")

    tx.exchange_token_sync(alice, "res-a")
    tx.exchange_token_sync(alice, "res-a")  # cached — no new call
    assert len(fake_http["sync_calls"]) == 1

    tx.exchange_token_sync(alice, "res-b")  # different resource
    assert len(fake_http["sync_calls"]) == 2

    tx.exchange_token_sync(bob, "res-a")    # different subject
    assert len(fake_http["sync_calls"]) == 3


def test_cache_expiry_refresh(enabled, fake_http, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(tx.time, "monotonic", lambda: clock["t"])
    sub = _subject()
    fake_http["handler"] = lambda url, data: FakeResp(payload={"access_token": "AS_TOKEN", "expires_in": 300})

    tx.exchange_token_sync(sub, "res")             # stores expiry at 1000+300-30 = 1270
    assert len(fake_http["sync_calls"]) == 1

    clock["t"] = 1269.0                             # still valid
    tx.exchange_token_sync(sub, "res")
    assert len(fake_http["sync_calls"]) == 1

    clock["t"] = 1271.0                             # past skew-adjusted expiry
    tx.exchange_token_sync(sub, "res")
    assert len(fake_http["sync_calls"]) == 2


def test_no_expiry_is_not_cached(enabled, fake_http):
    sub = _subject()
    fake_http["handler"] = lambda url, data: FakeResp(payload={"access_token": "AS_TOKEN"})
    tx.exchange_token_sync(sub, "res")
    tx.exchange_token_sync(sub, "res")
    assert len(fake_http["sync_calls"]) == 2  # no expires_in -> not cached, refetched


# --- error mapping -----------------------------------------------------------

def test_non_200_raises(enabled, fake_http):
    fake_http["handler"] = lambda url, data: FakeResp(status_code=400, payload={}, text="invalid_grant")
    with pytest.raises(tx.TokenExchangeError) as ei:
        tx.exchange_token_sync(_subject(), "res")
    assert "400" in str(ei.value)


def test_missing_access_token_raises(enabled, fake_http):
    fake_http["handler"] = lambda url, data: FakeResp(payload={"token_type": "Bearer"})
    with pytest.raises(tx.TokenExchangeError):
        tx.exchange_token_sync(_subject(), "res")


def test_non_json_body_raises(enabled, fake_http):
    fake_http["handler"] = lambda url, data: FakeResp(payload=_NO_JSON)
    with pytest.raises(tx.TokenExchangeError):
        tx.exchange_token_sync(_subject(), "res")


def test_network_error_raises(enabled, fake_http):
    def boom(url, data):
        raise httpx.ConnectError("down")
    fake_http["handler"] = boom
    with pytest.raises(tx.TokenExchangeError):
        tx.exchange_token_sync(_subject(), "res")


def test_bad_subject_token_raises(enabled, fake_http):
    with pytest.raises(tx.TokenExchangeError):
        tx.exchange_token_sync("not-a-jwt", "res")


def test_subject_without_sub_raises(enabled, fake_http):
    token = jwt.encode({"foo": "bar"}, "x" * 32, algorithm="HS256")
    with pytest.raises(tx.TokenExchangeError):
        tx.exchange_token_sync(token, "res")


# --- sync / async parity + shared cache --------------------------------------

@pytest.mark.asyncio
async def test_async_exchange_returns_token(enabled, fake_http):
    out = await tx.exchange_token(_subject(), "res")
    assert out == "AS_TOKEN"
    assert len(fake_http["async_calls"]) == 1


@pytest.mark.asyncio
async def test_cache_shared_across_sync_and_async(enabled, fake_http):
    sub = _subject()
    await tx.exchange_token(sub, "res")          # fills cache via async
    assert len(fake_http["async_calls"]) == 1

    tx.exchange_token_sync(sub, "res")           # served from the same cache
    assert len(fake_http["sync_calls"]) == 0
