"""Tests for auth.py -- Bearer token extraction."""

import base64

import pytest
from unittest.mock import patch

FAKE_BASIC_AUTH = base64.b64encode(b"user:pass").decode()


class TestGetGraphToken:
    """Test get_graph_token() header parsing."""

    def test_extracts_bearer_token(self):
        from ms_graph.auth import get_graph_token

        with patch("ms_graph.auth.get_http_headers", return_value={"authorization": "Bearer my-token-123"}):
            token = get_graph_token()
        assert token == "my-token-123"

    def test_extracts_token_case_insensitive_header(self):
        from ms_graph.auth import get_graph_token

        with patch("ms_graph.auth.get_http_headers", return_value={"Authorization": "Bearer upper-case-tok"}):
            token = get_graph_token()
        assert token == "upper-case-tok"

    def test_raises_on_missing_header(self):
        from ms_graph.auth import get_graph_token

        with patch("ms_graph.auth.get_http_headers", return_value={}):
            with pytest.raises(PermissionError, match="Authorization required"):
                get_graph_token()

    def test_raises_on_empty_authorization(self):
        from ms_graph.auth import get_graph_token

        with patch("ms_graph.auth.get_http_headers", return_value={"authorization": ""}):
            with pytest.raises(PermissionError, match="Authorization required"):
                get_graph_token()

    def test_raises_on_non_bearer_scheme(self):
        from ms_graph.auth import get_graph_token

        with patch("ms_graph.auth.get_http_headers", return_value={"authorization": f"Basic {FAKE_BASIC_AUTH}"}):
            with pytest.raises(PermissionError, match="Authorization required"):
                get_graph_token()

    def test_preserves_full_token_value(self):
        """Token may contain dots, slashes, etc. -- ensure nothing is stripped."""
        from ms_graph.auth import get_graph_token

        long_token = "eyJ0eXAi.eyJhdWQi.signature_here"
        with patch("ms_graph.auth.get_http_headers", return_value={"authorization": f"Bearer {long_token}"}):
            token = get_graph_token()
        assert token == long_token
