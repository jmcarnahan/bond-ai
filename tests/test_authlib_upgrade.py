"""
Tests for Authlib 1.6.6 → 1.6.9 upgrade and FastMCP v3 migration.

Verifies:
- Authlib version and basic functionality (Group A)
- alg:none CVE fix is effective (Group B)
- FastMCP JWTVerifier works with authlib (Group C)
- End-to-end MCP server with JWT auth (Group D)
- FastMCP v3 get_http_headers() behavior: lowercase keys, authorization exclusion (Group E)
"""

import base64
import json
import time

import pytest
from authlib.jose import JsonWebKey, JsonWebToken
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.common.security import generate_token
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier, RSAKeyPair
from fastmcp.utilities.tests import run_server_async
from fastmcp import Client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rsa_keypair():
    """Generate a fresh RSA keypair for tests."""
    return RSAKeyPair.generate()


@pytest.fixture
def rsa_keypair_alt():
    """Generate a second RSA keypair (for wrong-key tests)."""
    return RSAKeyPair.generate()


# ===========================================================================
# Group A: Authlib Basics
# ===========================================================================


def test_authlib_version():
    """Confirm installed authlib version >= 1.6.9."""
    import authlib
    parts = tuple(int(p) for p in authlib.__version__.split("."))
    assert parts >= (1, 6, 9), f"Expected >= 1.6.9, got {authlib.__version__}"


def test_jwt_rsa_roundtrip():
    """Encode/decode a JWT with RS256 via authlib's JsonWebToken + JsonWebKey."""
    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    private_pem = key.as_pem(is_private=True)
    public_pem = key.as_pem(is_private=False)

    jwt_instance = JsonWebToken(["RS256"])
    payload = {"sub": "user@example.com", "iss": "test", "iat": int(time.time())}
    token = jwt_instance.encode({"alg": "RS256"}, payload, private_pem)

    claims = jwt_instance.decode(token, public_pem)
    claims.validate()
    assert claims["sub"] == "user@example.com"
    assert claims["iss"] == "test"


def test_oauth2_client_and_token_gen():
    """AsyncOAuth2Client instantiates and generate_token produces output."""
    client = AsyncOAuth2Client(client_id="test-client", client_secret="test-secret")
    assert client.client_id == "test-client"

    token = generate_token()
    assert isinstance(token, str)
    assert len(token) > 0


# ===========================================================================
# Group B: Security — alg:none CVE Fix
# ===========================================================================


def _craft_alg_none_token(alg_value: str, payload: dict) -> bytes:
    """Craft a JWT with the given alg header and no signature."""
    header = json.dumps({"alg": alg_value, "typ": "JWT"}).encode()
    body = json.dumps(payload).encode()
    h = base64.urlsafe_b64encode(header).rstrip(b"=")
    b = base64.urlsafe_b64encode(body).rstrip(b"=")
    return h + b"." + b + b"."


def test_alg_none_rejected_by_authlib():
    """JWT with alg:none must be rejected by authlib's JsonWebToken."""
    payload = {"sub": "attacker", "iss": "test", "iat": int(time.time())}
    token = _craft_alg_none_token("none", payload)

    jwt_instance = JsonWebToken(["RS256"])
    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    public_pem = key.as_pem(is_private=False)

    with pytest.raises(Exception):
        claims = jwt_instance.decode(token, public_pem)
        claims.validate()


def test_alg_none_case_variations():
    """None, NONE, nOnE all rejected by authlib."""
    payload = {"sub": "attacker", "iss": "test", "iat": int(time.time())}
    jwt_instance = JsonWebToken(["RS256"])
    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    public_pem = key.as_pem(is_private=False)

    for alg in ("None", "NONE", "nOnE"):
        token = _craft_alg_none_token(alg, payload)
        with pytest.raises(Exception):
            claims = jwt_instance.decode(token, public_pem)
            claims.validate()


@pytest.mark.asyncio
async def test_alg_none_rejected_by_jwt_verifier(rsa_keypair):
    """Crafted alg:none token rejected by FastMCP's JWTVerifier."""
    verifier = JWTVerifier(public_key=rsa_keypair.public_key)
    payload = {"sub": "attacker", "iss": "test", "iat": int(time.time())}
    token = _craft_alg_none_token("none", payload)

    result = await verifier.verify_token(token.decode())
    assert result is None


# ===========================================================================
# Group C: FastMCP JWTVerifier
# ===========================================================================


@pytest.mark.asyncio
async def test_jwt_verifier_valid_token(rsa_keypair):
    """Sign with RSA key, verify via JWTVerifier -> success."""
    issuer = "https://fastmcp.example.com"
    audience = "test-audience"

    token = rsa_keypair.create_token(
        subject="user@example.com",
        issuer=issuer,
        audience=audience,
    )
    verifier = JWTVerifier(
        public_key=rsa_keypair.public_key,
        issuer=issuer,
        audience=audience,
    )

    result = await verifier.verify_token(token)
    assert result is not None
    assert result.client_id == "user@example.com"


@pytest.mark.asyncio
async def test_jwt_verifier_wrong_key(rsa_keypair, rsa_keypair_alt):
    """Sign with one key, verify with a different key -> rejected."""
    token = rsa_keypair.create_token(subject="user@example.com")
    verifier = JWTVerifier(public_key=rsa_keypair_alt.public_key)

    result = await verifier.verify_token(token)
    assert result is None


@pytest.mark.asyncio
async def test_jwt_verifier_expired_token(rsa_keypair):
    """Expired token -> returns None."""
    token = rsa_keypair.create_token(
        subject="user@example.com",
        expires_in_seconds=-10,
    )
    verifier = JWTVerifier(public_key=rsa_keypair.public_key)

    result = await verifier.verify_token(token)
    assert result is None


@pytest.mark.asyncio
async def test_jwt_verifier_claims_mismatch(rsa_keypair):
    """Wrong issuer or audience -> rejected."""
    token = rsa_keypair.create_token(
        subject="user@example.com",
        issuer="https://real-issuer.com",
        audience="real-audience",
    )

    # Wrong issuer
    verifier_bad_iss = JWTVerifier(
        public_key=rsa_keypair.public_key,
        issuer="https://wrong-issuer.com",
        audience="real-audience",
    )
    result = await verifier_bad_iss.verify_token(token)
    assert result is None

    # Wrong audience
    verifier_bad_aud = JWTVerifier(
        public_key=rsa_keypair.public_key,
        issuer="https://real-issuer.com",
        audience="wrong-audience",
    )
    result = await verifier_bad_aud.verify_token(token)
    assert result is None


# ===========================================================================
# Group D: End-to-End MCP Server
# ===========================================================================


def _make_auth_server(rsa_keypair, issuer="https://test.example.com", audience="test-aud"):
    """Create a FastMCP server with JWT auth and a simple tool."""
    verifier = JWTVerifier(
        public_key=rsa_keypair.public_key,
        issuer=issuer,
        audience=audience,
    )
    mcp = FastMCP("Test Auth Server", auth=verifier)

    @mcp.tool()
    def protected_echo(message: str) -> str:
        """Echo back the message (protected)."""
        return f"echo: {message}"

    return mcp


def _make_public_server():
    """Create a FastMCP server with no auth."""
    mcp = FastMCP("Test Public Server")

    @mcp.tool()
    def public_ping() -> str:
        """Return pong (no auth)."""
        return "pong"

    return mcp


@pytest.mark.asyncio
async def test_mcp_protected_tool_no_auth(rsa_keypair):
    """Call protected tool without token -> rejected."""
    server = _make_auth_server(rsa_keypair)

    async with run_server_async(server) as url:
        with pytest.raises(Exception):
            async with Client(url) as client:
                await client.call_tool("protected_echo", {"message": "hello"})


@pytest.mark.asyncio
async def test_mcp_protected_tool_valid_auth(rsa_keypair):
    """Call protected tool with valid JWT -> succeeds."""
    issuer = "https://test.example.com"
    audience = "test-aud"
    server = _make_auth_server(rsa_keypair, issuer=issuer, audience=audience)

    token = rsa_keypair.create_token(
        subject="user@test.com",
        issuer=issuer,
        audience=audience,
    )

    async with run_server_async(server) as url:
        async with Client(url, auth=token) as client:
            result = await client.call_tool("protected_echo", {"message": "hello"})
            texts = [c.text for c in result.content if hasattr(c, "text")]
            assert any("echo: hello" in t for t in texts)


@pytest.mark.asyncio
async def test_mcp_protected_tool_expired_auth(rsa_keypair):
    """Call protected tool with expired JWT -> rejected."""
    issuer = "https://test.example.com"
    audience = "test-aud"
    server = _make_auth_server(rsa_keypair, issuer=issuer, audience=audience)

    token = rsa_keypair.create_token(
        subject="user@test.com",
        issuer=issuer,
        audience=audience,
        expires_in_seconds=-10,
    )

    async with run_server_async(server) as url:
        with pytest.raises(Exception):
            async with Client(url, auth=token) as client:
                await client.call_tool("protected_echo", {"message": "hello"})


@pytest.mark.asyncio
async def test_mcp_public_tool_no_auth():
    """Public tool works without auth."""
    server = _make_public_server()

    # Use in-process Client directly (no HTTP server) to avoid uvicorn shutdown hang
    async with Client(server) as client:
        result = await client.call_tool("public_ping", {})
        texts = [c.text for c in result.content if hasattr(c, "text")]
        assert any("pong" in t for t in texts)


# ===========================================================================
# Group E: FastMCP v3 Header Behavior Regression
# ===========================================================================


def test_get_http_headers_lowercases_keys_and_excludes_auth_by_default():
    """Verify two critical FastMCP v3 get_http_headers() behaviors:

    1. All returned header keys are lowercase — our auth modules use
       headers.get("authorization") and would silently fail otherwise.
    2. The 'authorization' header is excluded by default but included when
       include={"authorization"} is passed — this is the v3 behavior change
       that required updating all auth modules.

    If either behavior changes in a future fastmcp release, this test will
    catch it before production auth silently breaks.
    """
    from starlette.requests import Request
    from fastmcp.server.dependencies import get_http_headers, _current_http_request

    # Simulate an HTTP request with mixed-case headers (as a real HTTP server would receive)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [
            (b"Authorization", b"Bearer test-token-abc123"),
            (b"Content-Type", b"application/json"),
            (b"X-Atlassian-Cloud-Id", b"cloud-xyz"),
            (b"X-Custom-Header", b"custom-value"),
            (b"Host", b"localhost:8000"),
        ],
    }
    mock_request = Request(scope)

    # Set the context variable so get_http_headers() can find our request
    token = _current_http_request.set(mock_request)
    try:
        headers_default = get_http_headers()
        headers_with_auth = get_http_headers(include={"authorization"})
        headers_with_cloud_id = get_http_headers(include={"x-atlassian-cloud-id"})
    finally:
        _current_http_request.reset(token)

    # 1. All returned keys must be lowercase
    for key in headers_with_auth:
        assert key == key.lower(), (
            f"get_http_headers() returned non-lowercase key '{key}'. "
            f"Auth modules depend on lowercase keys — this will break auth."
        )

    # 2. Default call must exclude authorization (v3 behavior change)
    assert "authorization" not in headers_default, (
        "get_http_headers() without include= returned 'authorization'. "
        "If this v3 behavior reverted, the include= parameter is harmless, "
        "but verify auth modules still work."
    )

    # 3. include={"authorization"} must include it
    assert "authorization" in headers_with_auth, (
        "get_http_headers(include={'authorization'}) did not return 'authorization'. "
        "This will break all MCP server authentication."
    )
    assert headers_with_auth["authorization"] == "Bearer test-token-abc123"

    # 4. Custom headers not in exclude list pass through by default
    assert "x-atlassian-cloud-id" in headers_default, (
        "x-atlassian-cloud-id should pass through by default (not in exclude list)."
    )
    assert headers_default["x-atlassian-cloud-id"] == "cloud-xyz"

    # 5. include= also works for custom headers (defensive coding in atlassian auth)
    assert "x-atlassian-cloud-id" in headers_with_cloud_id

    # 6. Standard excluded headers are stripped
    assert "host" not in headers_default
    assert "content-type" not in headers_default
