import pytest
import os
from unittest.mock import MagicMock, patch
from bondable.bond.providers.bedrock.BedrockProvider import BedrockProvider
from bondable.bond.providers.bedrock.BedrockAgent import BedrockAgentProvider


class TestBedrockModelsIntegration:
    """Integration test for the Bedrock provider's model methods."""
    
    @pytest.fixture
    def mock_bedrock_client(self):
        """Create a mock Bedrock client with list_foundation_models response."""
        client = MagicMock()
        
        # Mock the list_foundation_models response
        client.list_foundation_models.return_value = {
            'modelSummaries': [
                # Claude models (should be included)
                {
                    'modelId': 'anthropic.claude-3-5-sonnet-20241022-v2:0',
                    'modelName': 'Claude 3.5 Sonnet v2',
                    'providerName': 'Anthropic',
                    'outputModalities': ['TEXT'],
                    'responseStreamingSupported': True,
                    'inferenceTypesSupported': ['ON_DEMAND']
                },
                {
                    'modelId': 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
                    'modelName': 'Claude 3.5 Sonnet v2 (Cross-region)',
                    'providerName': 'Anthropic',
                    'outputModalities': ['TEXT'],
                    'responseStreamingSupported': True,
                    'inferenceTypesSupported': ['CROSS_REGION_INFERENCE']
                },
                {
                    'modelId': 'anthropic.claude-3-haiku-20240307-v1:0',
                    'modelName': 'Claude 3 Haiku',
                    'providerName': 'Anthropic',
                    'outputModalities': ['TEXT'],
                    'responseStreamingSupported': True,
                    'inferenceTypesSupported': ['ON_DEMAND']
                },
                # Titan model (should be included)
                {
                    'modelId': 'amazon.titan-text-express-v1',
                    'modelName': 'Titan Text Express',
                    'providerName': 'Amazon',
                    'outputModalities': ['TEXT'],
                    'responseStreamingSupported': True,
                    'inferenceTypesSupported': ['ON_DEMAND']
                },
                # Llama model (should be included)
                {
                    'modelId': 'meta.llama3-1-8b-instruct-v1:0',
                    'modelName': 'Llama 3.1 8B Instruct',
                    'providerName': 'Meta',
                    'outputModalities': ['TEXT'],
                    'responseStreamingSupported': True,
                    'inferenceTypesSupported': ['ON_DEMAND']
                },
                # Non-streaming model (should be excluded)
                {
                    'modelId': 'ai21.j2-ultra-v1',
                    'modelName': 'Jurassic-2 Ultra',
                    'providerName': 'AI21 Labs',
                    'outputModalities': ['TEXT'],
                    'responseStreamingSupported': False,
                    'inferenceTypesSupported': ['ON_DEMAND']
                },
                # Image model (should be excluded)
                {
                    'modelId': 'stability.stable-diffusion-xl-v1',
                    'modelName': 'Stable Diffusion XL',
                    'providerName': 'Stability AI',
                    'outputModalities': ['IMAGE'],
                    'responseStreamingSupported': False,
                    'inferenceTypesSupported': ['ON_DEMAND']
                },
                # Embedding model (should be excluded)
                {
                    'modelId': 'amazon.titan-embed-text-v1',
                    'modelName': 'Titan Embeddings',
                    'providerName': 'Amazon',
                    'outputModalities': ['EMBEDDING'],
                    'responseStreamingSupported': False,
                    'inferenceTypesSupported': ['ON_DEMAND']
                }
            ]
        }
        
        return client
    
    @pytest.fixture
    def bedrock_provider(self, mock_bedrock_client):
        """Create a BedrockProvider instance with mocked client."""
        with patch('boto3.client', return_value=mock_bedrock_client):
            # Mock environment variables
            with patch.dict(os.environ, {
                'AWS_ACCESS_KEY_ID': 'test-key',
                'AWS_SECRET_ACCESS_KEY': 'test-secret',
                'AWS_REGION': 'us-east-1'
            }):
                provider = BedrockProvider()
                # Replace the client with our mock
                provider.agents.bedrock_client = mock_bedrock_client
                return provider
    
    def test_get_available_models(self, bedrock_provider):
        """Test that BedrockProvider returns the correct models."""
        models = bedrock_provider.agents.get_available_models()
        
        # Should have filtered models
        assert isinstance(models, list)
        assert len(models) == 5  # 5 text streaming models from our mock
        
        # Check model structure
        for model in models:
            assert isinstance(model, dict)
            assert 'name' in model
            assert 'description' in model
            assert 'is_default' in model
            assert isinstance(model['name'], str)
            assert isinstance(model['description'], str)
            assert isinstance(model['is_default'], bool)
        
        # Check specific models are included
        model_names = [m['name'] for m in models]
        assert 'anthropic.claude-3-5-sonnet-20241022-v2:0' in model_names
        assert 'us.anthropic.claude-3-5-sonnet-20241022-v2:0' in model_names
        assert 'anthropic.claude-3-haiku-20240307-v1:0' in model_names
        assert 'amazon.titan-text-express-v1' in model_names
        assert 'meta.llama3-1-8b-instruct-v1:0' in model_names
        
        # Check excluded models are not present
        assert 'ai21.j2-ultra-v1' not in model_names  # Non-streaming
        assert 'stability.stable-diffusion-xl-v1' not in model_names  # Image model
        assert 'amazon.titan-embed-text-v1' not in model_names  # Embedding model
        
        # Check default model
        default_models = [m for m in models if m['is_default']]
        assert len(default_models) == 1
        assert default_models[0]['name'] == 'anthropic.claude-3-5-sonnet-20241022-v2:0'
    
    def test_get_default_model(self, bedrock_provider):
        """Test that BedrockProvider returns the correct default model."""
        default_model = bedrock_provider.get_default_model()
        
        # Should return the Claude 3.5 Sonnet model
        assert default_model == 'anthropic.claude-3-5-sonnet-20241022-v2:0'
    
    def test_get_available_models_error_handling(self, bedrock_provider):
        """Test error handling when list_foundation_models fails."""
        # Make the API call fail
        bedrock_provider.agents.bedrock_client.list_foundation_models.side_effect = Exception("API Error")
        
        # Should return empty list on error
        models = bedrock_provider.agents.get_available_models()
        assert models == []
    
    def test_get_available_models_with_environment_override(self, bedrock_provider):
        """Test that environment variable can override default model."""
        with patch.dict(os.environ, {'ANTHROPIC_MODEL': 'anthropic.claude-3-haiku-20240307-v1:0'}):
            models = bedrock_provider.agents.get_available_models()
            
            # Check that the environment-specified model is marked as default
            default_models = [m for m in models if m['is_default']]
            assert len(default_models) == 1
            assert default_models[0]['name'] == 'anthropic.claude-3-haiku-20240307-v1:0'
    
    def test_models_response_format(self, bedrock_provider):
        """Test that the model response format matches the expected structure."""
        models = bedrock_provider.agents.get_available_models()
        
        # Ensure all required fields are present and of correct type
        for model in models:
            # Check exact keys - no more, no less
            assert set(model.keys()) == {'name', 'description', 'is_default'}
            
            # Check types
            assert isinstance(model['name'], str)
            assert isinstance(model['description'], str)
            assert isinstance(model['is_default'], bool)
            
            # Check that description contains provider info
            if 'claude' in model['name']:
                assert 'Anthropic' in model['description']
            elif 'titan' in model['name']:
                assert 'Amazon' in model['description']
            elif 'llama' in model['name']:
                assert 'Meta' in model['description']