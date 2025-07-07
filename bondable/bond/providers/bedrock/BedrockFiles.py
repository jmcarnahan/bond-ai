"""
Simplified Bedrock Files Provider Implementation
Implements only the required abstract methods for file storage using AWS S3
"""

import io
import os
import uuid
import logging
import base64
import boto3
from typing import Optional, Tuple, Dict, Any, List
from botocore.exceptions import ClientError
from bondable.bond.config import Config
from bondable.bond.providers.provider import Provider
from bondable.bond.providers.files import FilesProvider, FileDetails
from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMetadata

LOGGER = logging.getLogger(__name__)
CODE_INTERPRETER_MIME_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/x-excel",
    "application/x-msexcel",
    "text/tab-separated-values",
}

class BedrockFilesProvider(FilesProvider):
    """
    Simplified files provider for AWS Bedrock using S3 for storage.
    Implements only the required abstract methods.
    """
    
    def __init__(self, s3_client: boto3.client, provider: Provider, metadata: BedrockMetadata):
        """
        Initialize Bedrock Files provider.
        
        Args:
            s3_client: S3 client
            metadata: BedrockMetadata instance for storing file records
        """
        super().__init__(metadata)

        self.s3_client = s3_client
        default_bucket_id = os.getenv('AWS_ACCOUNT_ID', uuid.uuid4().hex)
        default_bucket = f"bond-bedrock-files-{default_bucket_id}"
        self.bucket_name = os.getenv('BEDROCK_S3_BUCKET', default_bucket)
        self.bond_provider: Provider = provider
        
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


    def _get_key_from_file_id(self, file_id: str) -> Tuple[str, str]:
        """
        Extracts bucket name and S3 key from the file_id.
        
        Args:
            file_id: S3 URI of the file (e.g., s3://bucket/key)
        Returns:
            Tuple of (bucket_name, s3_key)
        """
        if not file_id.startswith('s3://'):
            raise ValueError(f"Invalid file_id format: {file_id}. Expected S3 URI format.")
        
        parts = file_id[5:].split('/', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {file_id}. Expected format s3://bucket/key.")
        bucket_name = parts[0]
        s3_key = parts[1]
        
        # Log warning if bucket doesn't match but still allow access
        if bucket_name != self.bucket_name:
            LOGGER.warning(f"File ID bucket '{bucket_name}' does not match configured bucket '{self.bucket_name}'")
            
        return bucket_name, s3_key
    
    
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
            file_id = f"bond_file_{uuid.uuid4().hex}"

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

            # the file_id to return is the uri of the file in S3
            s3_url = f"s3://{self.bucket_name}/{s3_key}"
            return s3_url
            
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
  
            bucket_name, s3_key = self._get_key_from_file_id(file_id)         
            
            # Use head_object to check if the object exists before deleting
            # Check if object exists first
            try:
                self.s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    LOGGER.warning(f"File not found in S3: {file_id}")
                    return False
                else:
                    raise
            
            # Delete from S3
            self.s3_client.delete_object(
                Bucket=bucket_name,
                Key=s3_key
            )
            
            LOGGER.info(f"Deleted file from S3: bucket={bucket_name}, key={s3_key}")
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
            file_tuple: Tuple of (file_id, optional_bytes)
            
        Returns:
            BytesIO object containing file content
        """
        file_id = file_tuple[0]
        file_bytes = file_tuple[1]
        
        # If bytes are already provided, use them
        if file_bytes is not None:
            return io.BytesIO(file_bytes)
        
        # Check if this is a file_id (starts with s3://)
        if file_id.startswith('s3://'):
            bucket_name, s3_key = self._get_key_from_file_id(file_id)  
            try:
                response = self.s3_client.get_object(
                    Bucket=bucket_name,
                    Key=s3_key
                )
                content = response['Body'].read()
                LOGGER.info(f"Retrieved file from S3: {file_id} ({len(content)} bytes)")
                return io.BytesIO(content)
                
            except ClientError as e:
                LOGGER.error(f"Failed to retrieve file from S3: {e}")
                raise
        else:
            # Fall back to base implementation for local files
            return super().get_file_bytes(file_tuple)
        

    def get_files_invocation(self, tool_resources: Dict) -> Dict[str, Any]:
        """
        Map the tool resources to the Bedrock file structure. Use the mime_type and file_size
        to detemine how to map things. Use the get_file_details() of the parent class
        to get the file details and return the files in the format expected by Bedrock.
        If the file is greater than 10MB, it should be returned as a S3 location.
        If the file is less than 10MB, it should be returned as byte content.

        The tool resources should look like this:
        {
            "code_interpreter": {
                "file_ids": [
                    "bedrock_file_d0efbb1d54634ed591ac29960774e42a"
                ]
            },
            "file_search": {
                "vector_store_ids": [
                    "bedrock_vs_55c6e310-221d-44e7-a6a0-feb461209d01"
                ]
            }
        }
        and the schema for the output is:
        'files': [
            {
                'name': 'string',
                'source': {
                    'byteContent': {
                        'data': b'bytes',
                        'mediaType': 'string'
                    },
                    's3Location': {
                        'uri': 'string'
                    },
                    'sourceType': 'S3'|'BYTE_CONTENT'
                },
                'useCase': 'CODE_INTERPRETER'|'CHAT'
            },
        ],
        """
        
        file_details_list = []

        # Handle code_interpreter files
        if 'code_interpreter' in tool_resources and 'file_ids' in tool_resources['code_interpreter']:
            # Get all file details at once
            file_details_list = self.get_file_details(tool_resources['code_interpreter']['file_ids'])
            
        # Handle file_search vector stores - for now just include them in chat
        if 'file_search' in tool_resources and 'vector_store_ids' in tool_resources['file_search']:
            for vector_store_id in tool_resources['file_search']['vector_store_ids']:
                # Assuming vector store IDs are mapped to file IDs
                vector_store_files: Dict[str, List[FileDetails]] = self.bond_provider.vectorstores.get_vector_store_file_details([vector_store_id])
                for file_id, details_list in vector_store_files.items():
                    if details_list:
                        file_details_list.extend(details_list)

        # in the code below map the mime_type to useCase using CODE_INTERPRETER_MIME_TYPES, if the mime_type is in CODE_INTERPRETER_MIME_TYPES, use 'CODE_INTERPRETER', otherwise use 'CHAT'
        files = []
        for file_details in file_details_list:
            file_id = file_details.file_id
            mime_type = file_details.mime_type or 'application/octet-stream'
            
            # Determine useCase based on mime_type
            files.append({
                'name': os.path.basename(file_details.file_path),
                'source': {
                    's3Location': {
                        'uri': file_details.file_id
                    },
                    'sourceType': 'S3'
                },
                'useCase': 'CODE_INTERPRETER' if mime_type in CODE_INTERPRETER_MIME_TYPES else 'CHAT'
            })
        
        # # Handle file_search vector stores
        # if 'file_search' in tool_resources and 'vector_store_ids' in tool_resources['file_search']:
        #     for vector_store_id in tool_resources['file_search']['vector_store_ids']:
        #         # Assuming vector store IDs are mapped to file IDs
        #         vector_store_files = self.bond_provider.vectorstores.get_vector_store_file_details([vector_store_id])
        #         for file_id, details in vector_store_files.items():
        #             if details:
        #                 files.append({
        #                     'name': os.path.basename(details[0]['s3_key']),
        #                     'source': {
        #                         'byteContent': {
        #                             'data': None,  # Not used for S3 files
        #                             'mediaType': details[0].get('mime_type', 'application/octet-stream')
        #                         },
        #                         's3Location': {
        #                             'uri': f"s3://{self.bucket_name}/{details[0]['s3_key']}"
        #                         },
        #                         'sourceType': 'S3'
        #                     },
        #                     'useCase': 'CHAT'
        #                 })
        
        return files if files else None
    
    def convert_attachments_to_files(self, attachments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert attachments from the stream_response format to Bedrock file format.
        Small files (<10MB) are sent as BYTE_CONTENT, larger files use S3 location.
        
        Args:
            attachments: List of attachment dictionaries with file_id and tools
            
        Returns:
            List of files in Bedrock format
        """
        files = []
        
        for attachment in attachments:
            file_id = attachment.get('file_id')
            if not file_id or not file_id.startswith('s3://'):
                LOGGER.warning(f"Skipping invalid attachment file_id: {file_id}")
                continue
                
            # Get file details to check size and get metadata
            try:
                file_details_list = self.get_file_details([file_id])
                if not file_details_list:
                    LOGGER.warning(f"No file details found for attachment: {file_id}")
                    continue
                
                file_details = file_details_list[0]
                file_size = file_details.file_size or 0
                
                # Determine use case based on tool type
                use_case = 'CHAT'  # Default
                tools = attachment.get('tools', [])
                for tool in tools:
                    if tool.get('type') == 'code_interpreter':
                        use_case = 'CODE_INTERPRETER'
                        break
                
                # Check file size to determine how to send it
                if file_size > 0:  # Always use S3 location for attachments
                    files.append({
                        'name': os.path.basename(file_details.file_path),
                        'source': {
                            's3Location': {
                                'uri': file_id
                            },
                            'sourceType': 'S3'
                        },
                        'useCase': use_case
                    })
                else:  # Less than or equal to 10MB - send as byte content
                    LOGGER.info(f"Retrieving file from S3: {file_id} ({file_size} bytes)")
                    file_bytes = self.get_file_bytes((file_id, None))
                    file_data = base64.b64encode(file_bytes.getvalue()).decode('utf-8')
                    files.append({
                        'name': os.path.basename(file_details.file_path),
                        'source': {
                            'byteContent': {
                                'data': file_data,
                                'mediaType': file_details.mime_type
                            },
                            'sourceType': 'BYTE_CONTENT'
                        },
                        'useCase': use_case
                    })
                    
            except Exception as e:
                LOGGER.error(f"Error processing attachment {file_id}: {e}")
                continue
            
        return files


