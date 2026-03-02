"""Tests for auth module — token and cloud_id extraction."""

import base64

import pytest
from unittest.mock import patch

FAKE_BASIC_AUTH = base64.b64encode(b"user:pass").decode()


class TestGetAtlassianToken:
    """Test Bearer token extraction."""

    def test_extracts_token_from_lowercase_header(self):
        mock_headers = {"authorization": "Bearer test-token-123"}
        with patch("atlassian.auth.get_http_headers", return_value=mock_headers):
            from atlassian.auth import get_atlassian_token
            assert get_atlassian_token() == "test-token-123"

    def test_extracts_token_from_titlecase_header(self):
        mock_headers = {"Authorization": "Bearer my-oauth-token"}
        with patch("atlassian.auth.get_http_headers", return_value=mock_headers):
            from atlassian.auth import get_atlassian_token
            assert get_atlassian_token() == "my-oauth-token"

    def test_raises_if_no_auth_header(self):
        with patch("atlassian.auth.get_http_headers", return_value={}):
            from atlassian.auth import get_atlassian_token
            with pytest.raises(PermissionError, match="Authorization required"):
                get_atlassian_token()

    def test_raises_if_not_bearer(self):
        mock_headers = {"authorization": f"Basic {FAKE_BASIC_AUTH}"}
        with patch("atlassian.auth.get_http_headers", return_value=mock_headers):
            from atlassian.auth import get_atlassian_token
            with pytest.raises(PermissionError, match="Authorization required"):
                get_atlassian_token()


class TestGetCloudId:
    """Test cloud_id extraction from X-Atlassian-Cloud-Id header."""

    def test_extracts_cloud_id_lowercase(self):
        mock_headers = {"x-atlassian-cloud-id": "abc-123-cloud"}
        with patch("atlassian.auth.get_http_headers", return_value=mock_headers):
            from atlassian.auth import get_cloud_id
            assert get_cloud_id() == "abc-123-cloud"

    def test_extracts_cloud_id_titlecase(self):
        mock_headers = {"X-Atlassian-Cloud-Id": "def-456-cloud"}
        with patch("atlassian.auth.get_http_headers", return_value=mock_headers):
            from atlassian.auth import get_cloud_id
            assert get_cloud_id() == "def-456-cloud"

    def test_raises_if_no_cloud_id_header(self):
        with patch("atlassian.auth.get_http_headers", return_value={}):
            from atlassian.auth import get_cloud_id
            with pytest.raises(PermissionError, match="Cloud ID required"):
                get_cloud_id()

    def test_raises_if_empty_cloud_id(self):
        mock_headers = {"x-atlassian-cloud-id": ""}
        with patch("atlassian.auth.get_http_headers", return_value=mock_headers):
            from atlassian.auth import get_cloud_id
            with pytest.raises(PermissionError, match="Cloud ID required"):
                get_cloud_id()
