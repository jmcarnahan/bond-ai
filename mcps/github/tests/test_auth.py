"""Tests for auth.py -- Bearer token extraction."""

import base64

import pytest
from unittest.mock import patch

FAKE_BASIC_AUTH = base64.b64encode(b"user:pass").decode()


class TestGetGitHubToken:
    """Test get_github_token() header parsing."""

    def test_extracts_bearer_token(self):
        from github.auth import get_github_token

        with patch("github.auth.get_http_headers", return_value={"authorization": "Bearer ghp_abc123"}):
            token = get_github_token()
        assert token == "ghp_abc123"

    def test_calls_get_http_headers_with_authorization_include(self):
        """Verify get_http_headers is called with include={'authorization'}.

        FastMCP v3 strips the authorization header by default.
        Without include={'authorization'}, auth will silently fail.
        """
        from github.auth import get_github_token

        with patch("github.auth.get_http_headers", return_value={"authorization": "Bearer tok"}) as mock_headers:
            get_github_token()
        mock_headers.assert_called_once_with(include={"authorization"})

    def test_raises_on_missing_header(self):
        from github.auth import get_github_token

        with patch("github.auth.get_http_headers", return_value={}):
            with pytest.raises(PermissionError, match="Authorization required"):
                get_github_token()

    def test_raises_on_empty_authorization(self):
        from github.auth import get_github_token

        with patch("github.auth.get_http_headers", return_value={"authorization": ""}):
            with pytest.raises(PermissionError, match="Authorization required"):
                get_github_token()

    def test_raises_on_non_bearer_scheme(self):
        from github.auth import get_github_token

        with patch("github.auth.get_http_headers", return_value={"authorization": f"Basic {FAKE_BASIC_AUTH}"}):
            with pytest.raises(PermissionError, match="Authorization required"):
                get_github_token()

    def test_preserves_full_token_value(self):
        """Token may contain dots, underscores, etc. -- ensure nothing is stripped."""
        from github.auth import get_github_token

        long_token = "test_token_with.dots_and-dashes.1234"
        with patch("github.auth.get_http_headers", return_value={"authorization": f"Bearer {long_token}"}):
            token = get_github_token()
        assert token == long_token
