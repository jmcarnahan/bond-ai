"""Tests for opaque file ID mapping (MAS-133).

Verifies that AWS account IDs are not exposed in API responses.
"""
import pytest
from unittest.mock import MagicMock
from bondable.rest.routers.files import _to_opaque_id, _resolve_file_id


class TestToOpaqueId:
    """Tests for _to_opaque_id()."""

    def test_extracts_bond_file_id(self):
        assert _to_opaque_id("s3://bond-bedrock-files-019593708315/files/bond_file_abc123def456") == "bond_file_abc123def456"

    def test_different_account_ids(self):
        assert _to_opaque_id("s3://bond-bedrock-files-123456789012/files/bond_file_aabbccdd") == "bond_file_aabbccdd"
        assert _to_opaque_id("s3://bond-bedrock-files-000000000000/files/bond_file_11223344") == "bond_file_11223344"

    def test_custom_bucket_name(self):
        assert _to_opaque_id("s3://my-custom-bucket/files/bond_file_deadbeef") == "bond_file_deadbeef"

    def test_fallback_for_non_bond_file(self):
        """Non-bond_file URIs return last path component."""
        assert _to_opaque_id("s3://bucket/files/some_other_file") == "some_other_file"

    def test_no_slash_passthrough(self):
        assert _to_opaque_id("bond_file_abc123") == "bond_file_abc123"


class TestResolveFileId:
    """Tests for _resolve_file_id()."""

    @pytest.fixture
    def mock_provider(self):
        provider = MagicMock()
        provider.files.bucket_name = "bond-bedrock-files-019593708315"
        return provider

    def test_resolves_opaque_id(self, mock_provider):
        result = _resolve_file_id("bond_file_abc123def456", mock_provider)
        assert result == "s3://bond-bedrock-files-019593708315/files/bond_file_abc123def456"

    def test_passthrough_s3_uri(self, mock_provider):
        uri = "s3://bond-bedrock-files-019593708315/files/bond_file_abc123def456"
        assert _resolve_file_id(uri, mock_provider) == uri

    def test_rejects_malformed_id(self, mock_provider):
        with pytest.raises(ValueError, match="Invalid file ID format"):
            _resolve_file_id("../../../etc/passwd", mock_provider)

    def test_rejects_random_string(self, mock_provider):
        with pytest.raises(ValueError, match="Invalid file ID format"):
            _resolve_file_id("not_a_valid_id", mock_provider)

    def test_rejects_empty_string(self, mock_provider):
        with pytest.raises(ValueError, match="Invalid file ID format"):
            _resolve_file_id("", mock_provider)

    def test_rejects_cross_bucket_s3_uri(self, mock_provider):
        """S3 URIs pointing to a different bucket must be rejected."""
        with pytest.raises(ValueError, match="unauthorized bucket"):
            _resolve_file_id("s3://attacker-bucket/files/bond_file_abc123", mock_provider)

    def test_rejects_different_account_bucket(self, mock_provider):
        with pytest.raises(ValueError, match="unauthorized bucket"):
            _resolve_file_id("s3://bond-bedrock-files-999999999999/files/bond_file_abc123", mock_provider)

    def test_allows_matching_bucket_s3_uri(self, mock_provider):
        uri = "s3://bond-bedrock-files-019593708315/files/bond_file_abc123"
        assert _resolve_file_id(uri, mock_provider) == uri


class TestRoundTrip:
    """Verify opaque ID round-trips correctly."""

    def test_round_trip(self):
        provider = MagicMock()
        provider.files.bucket_name = "bond-bedrock-files-123456789012"
        original_uri = "s3://bond-bedrock-files-123456789012/files/bond_file_aabbccdd11223344"

        opaque = _to_opaque_id(original_uri)
        assert opaque == "bond_file_aabbccdd11223344"
        assert "s3://" not in opaque
        assert "123456789012" not in opaque

        resolved = _resolve_file_id(opaque, provider)
        assert resolved == original_uri
