"""Contract test for the shared-secret JWT trust between bond-ai and bond-mcps.

bond-ai mints HS256 JWTs (sub=email, iss=bond-ai, aud includes 'mcp-server').
bond-mcps validates them with the SAME secret using fastmcp's JWTVerifier, which
is PyJWT (jwt.decode) under the hood. This test pins bond-ai's token shape to the
agreed bond-mcps verifier config so the integration can't silently drift:

    BOND_MCPS_JWT_PUBLIC_KEY = <bond-ai JWT_SECRET_KEY>   (shared secret)
    BOND_MCPS_JWT_ALGORITHM  = HS256
    BOND_MCPS_JWT_ISSUER     = bond-ai
    BOND_MCPS_JWT_AUDIENCE   = mcp-server
"""

import os
from datetime import timedelta

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-jwt-trust")

import jwt
import pytest

from bondable.rest.utils.auth import create_access_token, jwt_config

SHARED_SECRET = jwt_config.JWT_SECRET_KEY
MCPS_AUDIENCE = "mcp-server"
MCPS_ISSUER = "bond-ai"


def _verify_like_bond_mcps(token, *, secret=SHARED_SECRET, audience=MCPS_AUDIENCE, issuer=MCPS_ISSUER):
    """Mirror bond-mcps' fastmcp JWTVerifier(HS256) validation."""
    return jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience=audience,
        issuer=issuer,
    )


def _mint(**claims):
    data = {"sub": "user@example.com", "user_id": "u-1", "provider": "okta"}
    data.update(claims)
    return create_access_token(data, expires_delta=timedelta(minutes=15))


def test_bond_ai_token_has_expected_shape():
    decoded = jwt.decode(_mint(), SHARED_SECRET, algorithms=["HS256"], audience=MCPS_AUDIENCE)
    assert decoded["sub"] == "user@example.com"
    assert decoded["iss"] == MCPS_ISSUER
    assert MCPS_AUDIENCE in decoded["aud"]


def test_bond_mcps_accepts_valid_token():
    claims = _verify_like_bond_mcps(_mint())
    assert claims["sub"] == "user@example.com"  # bond-mcps user_key


def test_rejected_wrong_secret():
    with pytest.raises(jwt.InvalidSignatureError):
        _verify_like_bond_mcps(_mint(), secret="not-the-shared-secret")


def test_rejected_wrong_audience():
    with pytest.raises(jwt.InvalidAudienceError):
        _verify_like_bond_mcps(_mint(), audience="some-other-api")


def test_rejected_wrong_issuer():
    with pytest.raises(jwt.InvalidIssuerError):
        _verify_like_bond_mcps(_mint(), issuer="evil-issuer")


def test_rejected_expired_token():
    expired = create_access_token({"sub": "user@example.com"}, expires_delta=timedelta(seconds=-5))
    with pytest.raises(jwt.ExpiredSignatureError):
        _verify_like_bond_mcps(expired)
