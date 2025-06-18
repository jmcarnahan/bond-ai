"""
Simplified Bedrock Files Provider Implementation
Implements only the required abstract methods for file storage using AWS S3
"""

import io
import os
import uuid
import logging
from typing import Optional, Tuple
import boto3
from botocore.exceptions import ClientError

from bondable.bond.providers.files import FilesProvider
from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMetadata

LOGGER = logging.getLogger(__name__)


class BedrockFilesProvider(FilesProvider):
    """
    Simplified files provider for AWS Bedrock using S3 for storage.
    Implements only the required abstract methods.
    """
    
    def __init__(self, s3_client: boto3.client, metadata: BedrockMetadata):
        """
        Initialize Bedrock Files provider.
        
        Args:
            s3_client: Boto3 S3 client
            metadata: BedrockMetadata instance for storing file records
        """
        super().__init__(metadata)
        self.s3_client = s3_client
        # Use AWS account ID in bucket name for uniqueness
        aws_account_id = os.getenv('AWS_ACCOUNT_ID', '')
        default_bucket = f"bond-bedrock-files-{aws_account_id}" if aws_account_id else 'bond-bedrock-files'
        self.bucket_name = os.getenv('BEDROCK_S3_BUCKET', default_bucket)
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
        LOGGER.info(f"Initialized BedrockFilesProvider with bucket: {self.bucket_name}")
    
    def _ensure_bucket_exists(self):
        """Create S3 bucket if it doesn't exist"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            LOGGER.info(f"Using existing S3 bucket: {self.bucket_name}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                try:
                    region = self.s3_client.meta.region_name
                    if region == 'us-east-1':
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': region}
                        )
                    LOGGER.info(f"Created S3 bucket: {self.bucket_name}")
                except Exception as create_error:
                    LOGGER.error(f"Failed to create bucket: {create_error}")
                    raise
            else:
                raise
    
    def create_file_resource(self, file_path: str, file_bytes: io.BytesIO) -> str:
        """
        Creates a new file in S3.
        
        Args:
            file_path: Original file path/name
            file_bytes: File content as BytesIO
            
        Returns:
            file_id of the created file
        """
        try:
            # Generate unique file ID
            file_id = f"bedrock_file_{uuid.uuid4().hex}"
            
            # Create S3 key
            s3_key = f"files/{file_id}"
            
            # Reset BytesIO position
            file_bytes.seek(0)
            
            # Upload to S3
            self.s3_client.upload_fileobj(
                file_bytes,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'Metadata': {
                        'original_path': file_path,
                        'file_id': file_id
                    }
                }
            )
            
            LOGGER.info(f"Uploaded file to S3: bucket={self.bucket_name}, key={s3_key}, file_id={file_id}")
            return file_id
            
        except Exception as e:
            LOGGER.error(f"Failed to create file resource: {e}")
            raise
    
    def delete_file_resource(self, file_id: str) -> bool:
        """
        Deletes a file from S3.
        
        Args:
            file_id: ID of the file to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Create S3 key from file_id
            s3_key = f"files/{file_id}"
            
            # Check if object exists first
            try:
                self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    LOGGER.warning(f"File not found in S3: {file_id}")
                    return False
                else:
                    raise
            
            # Delete from S3
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            LOGGER.info(f"Deleted file from S3: bucket={self.bucket_name}, key={s3_key}")
            return True
            
        except ClientError as e:
            LOGGER.error(f"Failed to delete file resource: {e}")
            return False
        except Exception as e:
            LOGGER.error(f"Unexpected error deleting file: {e}")
            return False
    
    def get_file_bytes(self, file_tuple: Tuple[str, Optional[bytes]]) -> io.BytesIO:
        """
        Override to handle S3 file retrieval.
        
        Args:
            file_tuple: Tuple of (file_path_or_id, optional_bytes)
            
        Returns:
            BytesIO object containing file content
        """
        file_path_or_id = file_tuple[0]
        file_bytes = file_tuple[1]
        
        # If bytes are already provided, use them
        if file_bytes is not None:
            return io.BytesIO(file_bytes)
        
        # Check if this is a file_id (starts with bedrock_file_)
        if file_path_or_id.startswith('bedrock_file_'):
            try:
                # Retrieve from S3
                s3_key = f"files/{file_path_or_id}"
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=s3_key
                )
                
                content = response['Body'].read()
                LOGGER.info(f"Retrieved file from S3: {file_path_or_id} ({len(content)} bytes)")
                return io.BytesIO(content)
                
            except ClientError as e:
                LOGGER.error(f"Failed to retrieve file from S3: {e}")
                raise
        else:
            # Fall back to base implementation for local files
            return super().get_file_bytes(file_tuple)