import pytest
import os
from unittest.mock import patch, MagicMock
from bondable.bond.providers.openai.OAIAAgent import OAIAAgentProvider
from bondable.bond.providers.openai.OAIAMetadata import OAIAMetadata

class TestEnvironmentModelsConfiguration:
    """Test that models configuration from environment variables works correctly."""

    def test_default_models_when_no_env_vars(self):
        """Test default model configuration when no environment variables are set."""
        # Clear any existing env vars
        with patch.dict(os.environ, {}, clear=True):
            mock_openai_client = MagicMock()
            mock_metadata = MagicMock(spec=OAIAMetadata)

            provider = OAIAAgentProvider(mock_openai_client, mock_metadata)
            models = provider.get_available_models()

            # Should have default model
            assert len(models) == 1
            assert models[0]['name'] == 'gpt-4o'
            assert models[0]['description'] == 'Most capable GPT-4 Omni model for complex tasks'
            assert models[0]['is_default'] is True

    def test_single_model_from_env(self):
        """Test loading a single model from environment variables."""
        with patch.dict(os.environ, {
            'OPENAI_MODELS': 'gpt-4o:Most capable GPT-4 Omni model for complex tasks',
            'OPENAI_DEFAULT_MODEL': 'gpt-4o'
        }):
            mock_openai_client = MagicMock()
            mock_metadata = MagicMock(spec=OAIAMetadata)

            provider = OAIAAgentProvider(mock_openai_client, mock_metadata)
            models = provider.get_available_models()

            assert len(models) == 1
            assert models[0]['name'] == 'gpt-4o'
            assert models[0]['description'] == 'Most capable GPT-4 Omni model for complex tasks'
            assert models[0]['is_default'] is True

    def test_multiple_models_from_env(self):
        """Test loading multiple models from environment variables."""
        with patch.dict(os.environ, {
            'OPENAI_MODELS': 'gpt-4o:GPT-4 Omni model,gpt-4o-mini:Smaller GPT-4 model,gpt-3.5-turbo:Fast model',
            'OPENAI_DEFAULT_MODEL': 'gpt-4o-mini'
        }):
            mock_openai_client = MagicMock()
            mock_metadata = MagicMock(spec=OAIAMetadata)

            provider = OAIAAgentProvider(mock_openai_client, mock_metadata)
            models = provider.get_available_models()

            assert len(models) == 3

            # Check each model
            assert models[0]['name'] == 'gpt-4o'
            assert models[0]['description'] == 'GPT-4 Omni model'
            assert models[0]['is_default'] is False

            assert models[1]['name'] == 'gpt-4o-mini'
            assert models[1]['description'] == 'Smaller GPT-4 model'
            assert models[1]['is_default'] is True

            assert models[2]['name'] == 'gpt-3.5-turbo'
            assert models[2]['description'] == 'Fast model'
            assert models[2]['is_default'] is False

    def test_models_without_descriptions(self):
        """Test loading models without descriptions (just names)."""
        with patch.dict(os.environ, {
            'OPENAI_MODELS': 'gpt-4o,gpt-3.5-turbo',
            'OPENAI_DEFAULT_MODEL': 'gpt-4o'
        }):
            mock_openai_client = MagicMock()
            mock_metadata = MagicMock(spec=OAIAMetadata)

            provider = OAIAAgentProvider(mock_openai_client, mock_metadata)
            models = provider.get_available_models()

            assert len(models) == 2
            assert models[0]['name'] == 'gpt-4o'
            assert models[0]['description'] == 'gpt-4o model'
            assert models[0]['is_default'] is True

            assert models[1]['name'] == 'gpt-3.5-turbo'
            assert models[1]['description'] == 'gpt-3.5-turbo model'
            assert models[1]['is_default'] is False

    def test_default_model_not_in_list(self):
        """Test when default model is not in the available models list."""
        with patch.dict(os.environ, {
            'OPENAI_MODELS': 'gpt-4o:GPT-4 model,gpt-3.5-turbo:GPT-3.5 model',
            'OPENAI_DEFAULT_MODEL': 'gpt-4o-mini'  # Not in the list
        }):
            mock_openai_client = MagicMock()
            mock_metadata = MagicMock(spec=OAIAMetadata)

            provider = OAIAAgentProvider(mock_openai_client, mock_metadata)
            models = provider.get_available_models()

            assert len(models) == 2
            # First model should be marked as default
            assert models[0]['is_default'] is True
            assert models[1]['is_default'] is False

    def test_whitespace_handling(self):
        """Test that whitespace is properly handled in configuration."""
        with patch.dict(os.environ, {
            'OPENAI_MODELS': '  gpt-4o : GPT-4 Omni model  ,  gpt-3.5-turbo:GPT-3.5 Turbo  ',
            'OPENAI_DEFAULT_MODEL': ' gpt-4o '
        }):
            mock_openai_client = MagicMock()
            mock_metadata = MagicMock(spec=OAIAMetadata)

            provider = OAIAAgentProvider(mock_openai_client, mock_metadata)
            models = provider.get_available_models()

            assert len(models) == 2
            assert models[0]['name'] == 'gpt-4o'
            assert models[0]['description'] == 'GPT-4 Omni model'
            assert models[0]['is_default'] is True

            assert models[1]['name'] == 'gpt-3.5-turbo'
            assert models[1]['description'] == 'GPT-3.5 Turbo'
            assert models[1]['is_default'] is False

    def test_get_default_model_integration(self):
        """Test that get_default_model works with environment configuration."""
        with patch.dict(os.environ, {
            'OPENAI_MODELS': 'gpt-3.5-turbo:Fast model,gpt-4o:Smart model',
            'OPENAI_DEFAULT_MODEL': 'gpt-4o'
        }):
            with patch('bondable.bond.providers.openai.OAIAProvider.OpenAI') as mock_openai:
                with patch('bondable.bond.providers.openai.OAIAProvider.Config') as mock_config:
                    mock_config.config.return_value.get_metadata_db_url.return_value = "sqlite:///:memory:"

                    from bondable.bond.providers.openai.OAIAProvider import OAIAProvider
                    provider = OAIAProvider()

                    default_model = provider.get_default_model()
                    assert default_model == 'gpt-4o'
