from math import ceil
from unittest.mock import MagicMock, patch

import pytest

from pr_agent.algo.token_handler import ModelTypeValidator, TokenHandler


class TestTokenHandler:
    @patch('pr_agent.algo.token_handler.get_settings')
    def test_gemini_token_counting(self, mock_get_settings):
        # Setup mock settings
        mock_settings = MagicMock()
        mock_settings.config.model = "gemini/gemini-1.5-pro"
        # Mock get with default
        def get_side_effect(key, default=None):
            if key == 'openai.key': return None
            if key == 'anthropic.key': return None
            return default
        mock_settings.get.side_effect = get_side_effect
        mock_get_settings.return_value = mock_settings

        # Mock litellm
        with patch('pr_agent.algo.token_handler.litellm') as mock_litellm:
            mock_litellm.token_counter.return_value = 123

            # We need to ensure TokenHandler uses this model
            with patch('pr_agent.algo.token_handler.TokenEncoder') as MockTokenEncoder:
                 mock_encoder = MagicMock()
                 mock_encoder.encode.return_value = [1]*10 # 10 tokens estimate
                 MockTokenEncoder.get_token_encoder.return_value = mock_encoder

                 handler = TokenHandler()
                 handler.encoder = mock_encoder # Force set encoder

                 # force_accurate=True is needed to trigger _get_token_count_by_model_type
                 count = handler.count_tokens("some text", force_accurate=True)

                 assert count == 123
                 mock_litellm.token_counter.assert_called_with(model="gemini/gemini-1.5-pro", text="some text")

    @patch('pr_agent.algo.token_handler.get_settings')
    def test_gemini_fallback(self, mock_get_settings):
        # Setup mock settings
        mock_settings = MagicMock()
        mock_settings.config.model = "gemini/gemini-1.5-pro"

        # We need to handle the .get chained calls properly or use separate mocks
        # _apply_estimation_factor calls get_settings().get('config.model_token_count_estimate_factor', 0)

        def get_side_effect(key, default=None):
            if key == 'config.model_token_count_estimate_factor': return 0.5
            if key == 'openai.key': return None
            if key == 'anthropic.key': return None
            return default
        mock_settings.get.side_effect = get_side_effect

        mock_get_settings.return_value = mock_settings

        # Mock litellm to raise exception
        with patch('pr_agent.algo.token_handler.litellm') as mock_litellm:
            mock_litellm.token_counter.side_effect = Exception("API Error")

            with patch('pr_agent.algo.token_handler.TokenEncoder') as MockTokenEncoder:
                 mock_encoder = MagicMock()
                 mock_encoder.encode.return_value = [1]*10 # 10 tokens estimate
                 MockTokenEncoder.get_token_encoder.return_value = mock_encoder

                 handler = TokenHandler()
                 handler.encoder = mock_encoder

                 count = handler.count_tokens("some text", force_accurate=True)

                 # Should fallback to estimation: ceil(10 * (1 + 0.5)) = 15
                 assert count == 15

    def test_model_type_validator(self):
        assert ModelTypeValidator.is_gemini_model("gemini/pro")
        assert ModelTypeValidator.is_gemini_model("models/gemini-1.5")
        assert not ModelTypeValidator.is_gemini_model("gpt-4")
