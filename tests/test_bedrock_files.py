"""
Test file functionality for Bedrock provider.
Tests file creation, retrieval, and deletion using S3 storage.
"""

import os
import io
import pytest
import tempfile
from unittest.mock import patch
from bondable.bond.config import Config
from bondable.bond.providers.files import FileDetails


@pytest.fixture(scope="module")
def bedrock_provider():
    """Get the Bedrock provider instance"""
    with patch.dict(os.environ, {'BOND_PROVIDER_CLASS': 'bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider'}):
        config = Config.config()
        provider = config.get_provider()
        assert type(provider).__name__ == "BedrockProvider"
        yield provider


@pytest.fixture
def test_file_content():
    """Create test file content"""
    return b"This is a test file for Bedrock Files provider.\nIt contains some sample text."


@pytest.fixture
def test_file_path():
    """Create a temporary test file"""
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
        content = b"Test file content for Bedrock Files provider"
        f.write(content)
        f.flush()
        yield f.name
    # Cleanup
    if os.path.exists(f.name):
        os.unlink(f.name)


class TestBedrockFiles:
    """Test Bedrock files functionality"""

    def test_create_file_resource(self, bedrock_provider, test_file_content):
        """Test creating a file resource in S3"""
        # Create file from bytes
        file_bytes = io.BytesIO(test_file_content)
        file_path = "test_document.txt"

        # Create file resource
        file_id = bedrock_provider.files.create_file_resource(file_path, file_bytes)

        # Verify file_id format
        assert file_id is not None
        assert file_id.startswith("bedrock_file_")
        assert len(file_id) > len("bedrock_file_")

        # Cleanup
        bedrock_provider.files.delete_file_resource(file_id)

    def test_get_file_bytes_from_s3(self, bedrock_provider, test_file_content):
        """Test retrieving file bytes from S3"""
        # First create a file
        file_bytes = io.BytesIO(test_file_content)
        file_path = "test_retrieve.txt"
        file_id = bedrock_provider.files.create_file_resource(file_path, file_bytes)

        try:
            # Test retrieving by file_id
            retrieved_bytes = bedrock_provider.files.get_file_bytes((file_id, None))

            # Verify content
            retrieved_bytes.seek(0)
            retrieved_content = retrieved_bytes.read()
            assert retrieved_content == test_file_content

        finally:
            # Cleanup
            bedrock_provider.files.delete_file_resource(file_id)

    def test_delete_file_resource(self, bedrock_provider, test_file_content):
        """Test deleting a file from S3"""
        # Create a file
        file_bytes = io.BytesIO(test_file_content)
        file_path = "test_delete.txt"
        file_id = bedrock_provider.files.create_file_resource(file_path, file_bytes)

        # Delete the file
        result = bedrock_provider.files.delete_file_resource(file_id)
        assert result is True

        # Verify deletion - trying to get should fail
        with pytest.raises(Exception):
            bedrock_provider.files.get_file_bytes((file_id, None))

    def test_delete_nonexistent_file(self, bedrock_provider):
        """Test deleting a file that doesn't exist"""
        fake_file_id = "bedrock_file_nonexistent"

        # Should return False, not raise exception
        result = bedrock_provider.files.delete_file_resource(fake_file_id)
        assert result is False

    def test_file_workflow_with_metadata(self, bedrock_provider, test_file_path):
        """Test complete file workflow using FilesProvider methods"""
        test_user_id = "test_user_files"

        # Get or create file ID (this uses the base FilesProvider method)
        file_tuple = (test_file_path, None)
        file_details = bedrock_provider.files.get_or_create_file_id(test_user_id, file_tuple)

        try:
            # Verify file details
            assert isinstance(file_details, FileDetails)
            assert file_details.file_id.startswith("bedrock_file_")
            assert file_details.file_path == test_file_path
            assert file_details.file_hash is not None
            assert file_details.mime_type is not None
            assert file_details.owner_user_id == test_user_id

            # Get file details by ID
            file_details_list = bedrock_provider.files.get_file_details([file_details.file_id])
            assert len(file_details_list) == 1
            assert file_details_list[0].file_id == file_details.file_id

            # Test that creating the same file again reuses the ID
            file_details2 = bedrock_provider.files.get_or_create_file_id(test_user_id, file_tuple)
            assert file_details2.file_id == file_details.file_id

        finally:
            # Cleanup
            bedrock_provider.files.delete_file(file_details.file_id)

    def test_multiple_files_same_content(self, bedrock_provider, test_file_content):
        """Test handling multiple files with same content"""
        test_user_id = "test_user_duplicate"

        # Create first file
        file_tuple1 = ("document1.txt", test_file_content)
        file_details1 = bedrock_provider.files.get_or_create_file_id(test_user_id, file_tuple1)

        # For Bedrock, each file gets a unique file_id even if content is the same
        # This is different from OpenAI which reuses file IDs
        # So let's test that we can handle the same file path with same content
        file_tuple1_again = ("document1.txt", test_file_content)
        file_details1_again = bedrock_provider.files.get_or_create_file_id(test_user_id, file_tuple1_again)

        try:
            # Should reuse the same file_id for exact same path and content
            assert file_details1.file_id == file_details1_again.file_id
            assert file_details1.file_hash == file_details1_again.file_hash
            assert file_details1.file_path == file_details1_again.file_path

        finally:
            # Cleanup
            bedrock_provider.files.delete_file(file_details1.file_id)

    def test_get_file_bytes_local_fallback(self, bedrock_provider, test_file_path):
        """Test that get_file_bytes can still handle local files"""
        # Test with local file path
        file_bytes = bedrock_provider.files.get_file_bytes((test_file_path, None))

        # Verify we got content
        file_bytes.seek(0)
        content = file_bytes.read()
        assert len(content) > 0
        assert b"Test file content" in content


# Run with: pytest tests/test_bedrock_files.py -v
