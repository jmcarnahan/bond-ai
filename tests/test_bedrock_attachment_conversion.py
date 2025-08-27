"""
Unit test for BedrockFiles attachment conversion functionality.
"""

import pytest
import io
from bondable.bond.providers.bedrock.BedrockFiles import BedrockFilesProvider
from unittest.mock import Mock, MagicMock


class TestAttachmentConversion:
    """Test the convert_attachments_to_files method"""
    
    def test_convert_attachments_with_code_interpreter(self):
        """Test converting attachments with code_interpreter tool type"""
        # Mock S3 client
        s3_client = Mock()
        
        # Mock metadata with file details
        metadata = Mock()
        mock_file_details = Mock()
        mock_file_details.file_id = "s3://bond-bedrock-files-119684128788/files/bond_file_test123"
        mock_file_details.file_path = "/tmp/bond_file_test123"
        mock_file_details.file_size = 100  # Small file
        mock_file_details.mime_type = "text/plain"
        
        mock_file_details2 = Mock()
        mock_file_details2.file_id = "s3://bond-bedrock-files-119684128788/files/bond_file_test456"
        mock_file_details2.file_path = "/tmp/bond_file_test456"
        mock_file_details2.file_size = 200  # Small file
        mock_file_details2.mime_type = "text/plain"
        
        # Create BedrockFilesProvider instance
        files_provider = BedrockFilesProvider(s3_client, metadata)
        
        # Mock get_file_details
        files_provider.get_file_details = Mock(side_effect=[[mock_file_details], [mock_file_details2]])
        
        # Mock get_file_bytes to return test data
        test_bytes = io.BytesIO(b"test content")
        files_provider.get_file_bytes = Mock(return_value=test_bytes)
        
        # Test attachments
        attachments = [
            {
                "file_id": "s3://bond-bedrock-files-119684128788/files/bond_file_test123",
                "tools": [{"type": "code_interpreter"}]
            },
            {
                "file_id": "s3://bond-bedrock-files-119684128788/files/bond_file_test456",
                "tools": [{"type": "code_interpreter"}]
            }
        ]
        
        # Convert attachments
        result = files_provider.convert_attachments_to_files(attachments)
        
        # Verify result
        assert len(result) == 2
        
        # Check first file - should be BYTE_CONTENT for small file
        assert result[0]['name'] == 'bond_file_test123'
        assert result[0]['source']['sourceType'] == 'BYTE_CONTENT'
        assert 'byteContent' in result[0]['source']
        assert result[0]['source']['byteContent']['mediaType'] == 'text/plain'
        assert result[0]['useCase'] == 'CODE_INTERPRETER'
        
        # Check second file - should also be BYTE_CONTENT
        assert result[1]['name'] == 'bond_file_test456'
        assert result[1]['source']['sourceType'] == 'BYTE_CONTENT'
        assert result[1]['useCase'] == 'CODE_INTERPRETER'
    
    def test_convert_attachments_with_file_search(self):
        """Test converting attachments with file_search tool type"""
        # Mock S3 client
        s3_client = Mock()
        
        # Mock metadata
        metadata = Mock()
        mock_file_details = Mock()
        mock_file_details.file_id = "s3://bond-bedrock-files-119684128788/files/bond_file_test789"
        mock_file_details.file_path = "/tmp/bond_file_test789"
        mock_file_details.file_size = 500  # Small file
        mock_file_details.mime_type = "text/plain"
        
        # Create BedrockFilesProvider instance
        files_provider = BedrockFilesProvider(s3_client, metadata)
        
        # Mock get_file_details
        files_provider.get_file_details = Mock(return_value=[mock_file_details])
        
        # Mock get_file_bytes
        test_bytes = io.BytesIO(b"test content")
        files_provider.get_file_bytes = Mock(return_value=test_bytes)
        
        # Test attachments with file_search
        attachments = [
            {
                "file_id": "s3://bond-bedrock-files-119684128788/files/bond_file_test789",
                "tools": [{"type": "file_search"}]
            }
        ]
        
        # Convert attachments
        result = files_provider.convert_attachments_to_files(attachments)
        
        # Verify result
        assert len(result) == 1
        assert result[0]['name'] == 'bond_file_test789'
        assert result[0]['source']['sourceType'] == 'BYTE_CONTENT'
        assert result[0]['useCase'] == 'CHAT'  # file_search maps to CHAT
    
    def test_convert_attachments_with_invalid_file_id(self):
        """Test handling invalid file IDs"""
        # Mock S3 client
        s3_client = Mock()
        
        # Mock metadata
        metadata = Mock()
        mock_file_details = Mock()
        mock_file_details.file_id = "s3://bond-bedrock-files-119684128788/files/bond_file_valid"
        mock_file_details.file_path = "/tmp/bond_file_valid"
        mock_file_details.file_size = 100
        mock_file_details.mime_type = "text/plain"
        
        # Create BedrockFilesProvider instance
        files_provider = BedrockFilesProvider(s3_client, metadata)
        
        # Mock get_file_details - only called for valid file
        files_provider.get_file_details = Mock(return_value=[mock_file_details])
        
        # Mock get_file_bytes
        test_bytes = io.BytesIO(b"valid content")
        files_provider.get_file_bytes = Mock(return_value=test_bytes)
        
        # Test attachments with invalid file_id
        attachments = [
            {
                "file_id": "invalid_file_id",  # Not an S3 URI
                "tools": [{"type": "code_interpreter"}]
            },
            {
                "file_id": "s3://bond-bedrock-files-119684128788/files/bond_file_valid",
                "tools": [{"type": "code_interpreter"}]
            }
        ]
        
        # Convert attachments
        result = files_provider.convert_attachments_to_files(attachments)
        
        # Should only include valid file
        assert len(result) == 1
        assert result[0]['name'] == 'bond_file_valid'
        assert result[0]['source']['sourceType'] == 'BYTE_CONTENT'
    
    def test_convert_attachments_large_file(self):
        """Test converting attachments with large files (>10MB)"""
        # Mock S3 client
        s3_client = Mock()
        
        # Mock metadata with large file
        metadata = Mock()
        mock_file_details = Mock()
        mock_file_details.file_id = "s3://bond-bedrock-files-119684128788/files/bond_file_large"
        mock_file_details.file_path = "/tmp/bond_file_large"
        mock_file_details.file_size = 15 * 1024 * 1024  # 15MB - large file
        mock_file_details.mime_type = "application/octet-stream"
        
        # Create BedrockFilesProvider instance
        files_provider = BedrockFilesProvider(s3_client, metadata)
        
        # Mock get_file_details
        files_provider.get_file_details = Mock(return_value=[mock_file_details])
        
        # Test attachment with large file
        attachments = [
            {
                "file_id": "s3://bond-bedrock-files-119684128788/files/bond_file_large",
                "tools": [{"type": "code_interpreter"}]
            }
        ]
        
        # Convert attachments
        result = files_provider.convert_attachments_to_files(attachments)
        
        # Verify result - large file should use S3 location
        assert len(result) == 1
        assert result[0]['name'] == 'bond_file_large'
        assert result[0]['source']['sourceType'] == 'S3'
        assert result[0]['source']['s3Location']['uri'] == attachments[0]['file_id']
        assert result[0]['useCase'] == 'CODE_INTERPRETER'
    
    def test_convert_empty_attachments(self):
        """Test converting empty attachments list"""
        # Mock S3 client
        s3_client = Mock()
        
        # Mock metadata
        metadata = Mock()
        
        # Create BedrockFilesProvider instance
        files_provider = BedrockFilesProvider(s3_client, metadata)
        
        # Empty attachments
        attachments = []
        
        # Convert attachments
        result = files_provider.convert_attachments_to_files(attachments)
        
        # Should return empty list
        assert result == []


# Run with: poetry run pytest tests/test_bedrock_attachment_conversion.py -v