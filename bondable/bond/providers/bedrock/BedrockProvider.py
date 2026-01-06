"""
BedrockProvider - AWS Bedrock implementation of Bond Provider interface

This provider uses AWS Bedrock's Converse API for agent interactions,
S3 for file storage, and Bedrock Knowledge Bases for vector stores.
"""

import os
import boto3
from botocore.exceptions import ClientError
from sqlalchemy import text
from bondable.bond.providers.provider import Provider
from bondable.bond.config import Config
from bondable.bond.cache import bond_cache
from .BedrockMetadata import BedrockMetadata
from .BedrockThreads import BedrockThreadsProvider
import logging
from typing import Optional, List, Dict, Any

LOGGER = logging.getLogger(__name__)

# Default model mapping for common model names
BEDROCK_MODEL_MAPPING = {
    # Standard model IDs (for us-east-1 and other regions)
    "claude-3-opus": "anthropic.claude-3-opus-20240229-v1:0",
    "claude-3-sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
    "claude-3-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
    "claude-3.5-sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "claude-3.5-sonnet-v2": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "claude-3.5-haiku": "anthropic.claude-3-5-haiku-20241022-v1:0",
    "claude-4-sonnet": "anthropic.claude-sonnet-4-20250514-v1:0",
    "claude-4-opus": "anthropic.claude-opus-4-20250514-v1:0",
    # Cross-region inference profiles (us-east-2 and other regions)
    "us-claude-3-haiku": "us.anthropic.claude-3-haiku-20240307-v1:0",
    "us-claude-3.5-sonnet": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "us-claude-3.5-haiku": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "us-claude-4-sonnet": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    # Other models
    "llama3-8b": "meta.llama3-8b-instruct-v1:0",
    "llama3-70b": "meta.llama3-70b-instruct-v1:0",
    "mistral-7b": "mistral.mistral-7b-instruct-v0:2",
    "mistral-large": "mistral.mistral-large-2407-v1:0",
}


class BedrockProvider(Provider):
    """AWS Bedrock implementation of the Bond Provider interface"""

    def __init__(self):
        super().__init__()
        self.config = Config.config()

        # Initialize AWS clients
        self._init_aws_clients()

        # Initialize metadata with database URL
        metadata_db_url = self.config.get_metadata_db_url()
        self.metadata = BedrockMetadata(metadata_db_url)

        # Initialize sub-providers
        self.threads = BedrockThreadsProvider(bedrock_agent_runtime_client=self.bedrock_agent_runtime_client, provider=self, metadata=self.metadata)

        # Initialize agent provider
        from .BedrockAgent import BedrockAgentProvider
        self.agents = BedrockAgentProvider(bedrock_client=self.bedrock_client, bedrock_agent_client=self.bedrock_agent_client, metadata=self.metadata)

        # Initialize files provider
        from .BedrockFiles import BedrockFilesProvider
        self.files = BedrockFilesProvider(s3_client=self.s3_client, provider=self, metadata=self.metadata)

        # Initialize vector stores with KB support
        from .BedrockVectorStores import BedrockVectorStoresProvider
        self.vectorstores = BedrockVectorStoresProvider(
            metadata_provider=self.metadata,
            s3_client=self.s3_client,
            bedrock_agent_client=self.bedrock_agent_client,
            bedrock_agent_runtime_client=self.bedrock_agent_runtime_client
        )
        self.vectorstores.files_provider = self.files  # Set files provider reference

        # Groups and users are handled by base metadata
        from bondable.bond.groups import Groups
        from bondable.bond.users import Users
        self.groups = Groups(self.metadata)
        self.users = Users(self.metadata)

        LOGGER.info("Initialized BedrockProvider")

    def _init_aws_clients(self):
        """Initialize AWS service clients"""
        # Get AWS configuration from environment - REQUIRED
        self.aws_region = os.getenv('AWS_REGION')
        if not self.aws_region:
            raise ValueError("AWS_REGION environment variable must be set. Please set AWS_REGION to your desired AWS region (e.g., us-east-2)")
        aws_session = None
        try:
            aws_profile = os.getenv('AWS_PROFILE', None)
            if aws_profile:
                aws_session: boto3.Session = boto3.Session(
                    profile_name=aws_profile,
                    region_name=self.aws_region
                )
            else:
                aws_session: boto3.Session = boto3.Session(
                    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', None),
                    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', None),
                    region_name=self.aws_region
                )
        except Exception as e:
            LOGGER.error(f"Error creating AWS session: {e}")
            raise ValueError("Failed to create AWS session. Check your AWS credentials and configuration.")

        # Initialize Bedrock clients
        try:
            self.bedrock_client = aws_session.client(
                service_name='bedrock',
                region_name=self.aws_region
            )
            self.bedrock_runtime_client = aws_session.client(
                service_name='bedrock-runtime',
                region_name=self.aws_region
            )
            self.bedrock_agent_client = aws_session.client(
                service_name='bedrock-agent',
                region_name=self.aws_region
            )
            self.bedrock_agent_runtime_client = aws_session.client(
                service_name='bedrock-agent-runtime',
                region_name=self.aws_region
            )

            # S3 client for file storage
            self.s3_client = aws_session.client(
                service_name='s3',
                region_name=self.aws_region
            )

            LOGGER.info(f"Initialized AWS clients in region {self.aws_region}")

        except Exception as e:
            LOGGER.error(f"Error initializing AWS clients: {e}")
            raise

    def get_default_model(self) -> str:
        """
        Get the default model ID for this provider.

        Returns:
            The default Bedrock model ID
        """
        # Check environment variable first
        default_model = os.getenv('BEDROCK_DEFAULT_MODEL')
        if default_model:
            return default_model

        # Check config
        if hasattr(self.config, 'bedrock_default_model'):
            return self.config.bedrock_default_model

        # Always use cross-region inference models with us. prefix
        return "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available models from Bedrock.

        Returns:
            List of model information dictionaries
        """
        try:
            # List foundation models
            response = self.bedrock_client.list_foundation_models(
                byOutputModality='TEXT'
            )

            models = []
            for model in response.get('modelSummaries', []):
                # Include models that support text output and streaming
                # The Converse API is supported by models that have streaming support
                streaming_support = model.get('responseStreamingSupported', False)
                output_modalities = model.get('outputModalities', [])

                # Include models that support text output and streaming
                if 'TEXT' in output_modalities and streaming_support:
                    # Check if this is a model we support
                    model_id = model['modelId']

                    # Filter for Claude models and other supported models
                    # You can expand this list as needed
                    supported_prefixes = ['anthropic.claude', 'us.anthropic.claude', 'amazon.titan', 'meta.llama']
                    is_supported = any(model_id.startswith(prefix) for prefix in supported_prefixes)

                    if is_supported:
                        model_info = {
                            'id': model_id,
                            'name': model_id,  # Use model ID as name for consistency
                            'description': f"{model['providerName']} - {model['modelName']}",
                            'is_default': False,  # Will be set later
                            'provider': model['providerName'],
                            'input_modalities': model.get('inputModalities', []),
                            'output_modalities': output_modalities,
                            'supports_streaming': bool(streaming_support),
                            'supports_tools': model.get('supportsToolUse', False),
                            'max_tokens': model.get('maxTokens', 4096)
                        }
                        models.append(model_info)

            # Get the default model from environment
            default_model = self.get_default_model()

            # Mark the default model and check if it's in the list
            default_found = False
            for model in models:
                if model['id'] == default_model:
                    model['is_default'] = True
                    default_found = True
                    break

            # If the default model is not in the list (e.g., cross-region models), add it
            if not default_found and default_model:
                # Add the default model to the list
                models.append({
                    'id': default_model,
                    'name': default_model,
                    'description': 'Anthropic - Claude (Default from BEDROCK_DEFAULT_MODEL)',
                    'is_default': True,
                    'provider': 'Anthropic',
                    'input_modalities': ['TEXT'],
                    'output_modalities': ['TEXT'],
                    'supports_streaming': True,
                    'supports_tools': True,
                    'max_tokens': 4096
                })
                LOGGER.info(f"Added default model from environment: {default_model}")

            # Sort by provider and name
            models.sort(key=lambda x: (x['provider'], x['name']))

            LOGGER.info(f"Found {len(models)} available models supporting Converse API")
            return models

        except ClientError as e:
            LOGGER.error(f"Error listing Bedrock models: {e}")
            return []

    def map_model_name(self, model_name: str) -> str:
        """
        Map a friendly model name to a Bedrock model ID.

        Args:
            model_name: Friendly name or actual Bedrock model ID

        Returns:
            Bedrock model ID
        """
        # If it's already a full model ID (contains dots), return as-is
        if '.' in model_name and ':' in model_name:
            return model_name

        # Check mapping
        mapped = BEDROCK_MODEL_MAPPING.get(model_name)
        if mapped:
            return mapped

        # Check if it's a partial match (e.g., "claude-3-haiku" without version)
        for key, value in BEDROCK_MODEL_MAPPING.items():
            if model_name in key or key in model_name:
                return value

        # Return as-is and let Bedrock handle validation
        return model_name

    @classmethod
    @bond_cache
    def provider(cls) -> Provider:
        """
        Get or create a singleton instance of BedrockProvider.

        Returns:
            BedrockProvider instance
        """
        return BedrockProvider()

    def validate_configuration(self) -> Dict[str, any]:
        """
        Validate that the provider is properly configured.

        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'info': {}
        }

        # Check AWS credentials
        try:
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            results['info']['aws_account'] = identity['Account']
            results['info']['aws_arn'] = identity['Arn']
        except Exception as e:
            results['valid'] = False
            results['errors'].append(f"AWS credentials not configured: {e}")

        # Check default model
        default_model = self.get_default_model()
        results['info']['default_model'] = default_model

        # Verify model exists
        try:
            models = self.get_available_models()
            model_ids = [m['id'] for m in models]
            if default_model not in model_ids:
                results['warnings'].append(
                    f"Default model '{default_model}' not found in available models. "
                    "This might be due to region restrictions."
                )
        except Exception as e:
            results['warnings'].append(f"Could not verify available models: {e}")

        # Check S3 bucket for file storage
        s3_bucket = os.getenv('BEDROCK_S3_BUCKET')
        if not s3_bucket:
            results['warnings'].append(
                "BEDROCK_S3_BUCKET not configured. File uploads will not work."
            )
        else:
            results['info']['s3_bucket'] = s3_bucket
            # Verify bucket exists and is accessible
            try:
                self.s3_client.head_bucket(Bucket=s3_bucket)
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    results['errors'].append(f"S3 bucket '{s3_bucket}' does not exist")
                else:
                    results['errors'].append(f"Cannot access S3 bucket '{s3_bucket}': {e}")
                results['valid'] = False

        # Check database connection
        try:
            session = self.metadata.get_db_session()
            session.execute(text('SELECT 1'))
            session.close()
            results['info']['database'] = 'connected'
        except Exception as e:
            results['valid'] = False
            results['errors'].append(f"Database connection failed: {e}")

        return results

    def __repr__(self):
        return f"BedrockProvider(region={self.aws_region}, default_model={self.get_default_model()})"
