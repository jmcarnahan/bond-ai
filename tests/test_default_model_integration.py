import pytest
from bondable.bond.providers.openai.OAIAProvider import OAIAProvider
from bondable.bond.providers.openai.OAIAAgent import OAIAAgentProvider
from bondable.bond.providers.openai.OAIAMetadata import OAIAMetadata
from unittest.mock import MagicMock, patch
import logging

class TestDefaultModelIntegration:
    """Test that get_default_model properly uses get_available_models."""

    def test_get_default_model_uses_available_models(self):
        """Test that get_default_model calls get_available_models and returns the default."""
        with patch('bondable.bond.providers.openai.OAIAProvider.OpenAI') as mock_openai:
            with patch('bondable.bond.providers.openai.OAIAProvider.Config') as mock_config:
                # Mock dependencies
                mock_config.config.return_value.get_metadata_db_url.return_value = "sqlite:///:memory:"

                # Create provider
                provider = OAIAProvider()

                # Get default model
                default_model = provider.get_default_model()

                # Should return gpt-4o as it's marked as default
                assert default_model == "gpt-4o"

    def test_get_default_model_no_models_available(self):
        """Test get_default_model when no models are available."""
        with patch('bondable.bond.providers.openai.OAIAProvider.OpenAI') as mock_openai:
            with patch('bondable.bond.providers.openai.OAIAProvider.Config') as mock_config:
                # Mock dependencies
                mock_config.config.return_value.get_metadata_db_url.return_value = "sqlite:///:memory:"

                # Create provider
                provider = OAIAProvider()

                # Mock get_available_models to return empty list
                provider.agents.get_available_models = MagicMock(return_value=[])

                # Get default model
                default_model = provider.get_default_model()

                # Should return fallback
                assert default_model == "gpt-4o"

    def test_get_default_model_no_default_specified(self):
        """Test get_default_model when no model is marked as default."""
        with patch('bondable.bond.providers.openai.OAIAProvider.OpenAI') as mock_openai:
            with patch('bondable.bond.providers.openai.OAIAProvider.Config') as mock_config:
                # Mock dependencies
                mock_config.config.return_value.get_metadata_db_url.return_value = "sqlite:///:memory:"

                # Create provider
                provider = OAIAProvider()

                # Mock get_available_models to return models without default
                provider.agents.get_available_models = MagicMock(return_value=[
                    {'name': 'gpt-3.5-turbo', 'description': 'Fast model', 'is_default': False},
                    {'name': 'gpt-4', 'description': 'Smart model', 'is_default': False}
                ])

                # Get default model
                default_model = provider.get_default_model()

                # Should return first model
                assert default_model == "gpt-3.5-turbo"

    def test_get_default_model_multiple_defaults(self):
        """Test get_default_model when multiple models are marked as default (edge case)."""
        with patch('bondable.bond.providers.openai.OAIAProvider.OpenAI') as mock_openai:
            with patch('bondable.bond.providers.openai.OAIAProvider.Config') as mock_config:
                # Mock dependencies
                mock_config.config.return_value.get_metadata_db_url.return_value = "sqlite:///:memory:"

                # Create provider
                provider = OAIAProvider()

                # Mock get_available_models to return multiple defaults
                provider.agents.get_available_models = MagicMock(return_value=[
                    {'name': 'gpt-3.5-turbo', 'description': 'Fast model', 'is_default': True},
                    {'name': 'gpt-4o', 'description': 'Best model', 'is_default': True}
                ])

                # Get default model
                default_model = provider.get_default_model()

                # Should return first default found
                assert default_model == "gpt-3.5-turbo"
