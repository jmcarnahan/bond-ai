import pytest
from bondable.bond.providers.openai.OAIAAgent import OAIAAgentProvider
from bondable.bond.providers.openai.OAIAMetadata import OAIAMetadata
from unittest.mock import MagicMock

class TestModelsIntegration:
    """Integration test for the get_available_models method."""

    def test_oaia_provider_get_available_models(self):
        """Test that OAIAAgentProvider returns the expected models."""
        # Create mock dependencies
        mock_openai_client = MagicMock()
        mock_metadata = MagicMock(spec=OAIAMetadata)

        # Create the provider
        provider = OAIAAgentProvider(mock_openai_client, mock_metadata)

        # Get available models
        models = provider.get_available_models()

        # Assertions
        assert isinstance(models, list)
        assert len(models) == 1

        # Check the model structure
        model = models[0]
        assert isinstance(model, dict)
        assert 'name' in model
        assert 'description' in model
        assert 'is_default' in model

        # Check the specific model
        assert model['name'] == 'gpt-4o'
        assert model['description'] == 'Most capable GPT-4 Omni model for complex tasks'
        assert model['is_default'] is True

    def test_models_response_format(self):
        """Test that the model response format is correct."""
        mock_openai_client = MagicMock()
        mock_metadata = MagicMock(spec=OAIAMetadata)

        provider = OAIAAgentProvider(mock_openai_client, mock_metadata)
        models = provider.get_available_models()

        # Ensure all required fields are present and of correct type
        for model in models:
            assert isinstance(model['name'], str)
            assert isinstance(model['description'], str)
            assert isinstance(model['is_default'], bool)

            # Ensure no extra fields
            assert set(model.keys()) == {'name', 'description', 'is_default'}
