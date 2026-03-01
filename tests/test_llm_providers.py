"""Tests for LLM providers."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.llm import LLMProvider, MockLLMProvider, GeminiProvider


class TestMockProvider:
    """Tests for MockLLMProvider."""
    
    def test_mock_provider_with_sorry(self):
        """Test mock provider generates proof for sorry."""
        provider = MockLLMProvider()
        response, in_tokens, out_tokens = provider.generate("Fix this sorry")
        
        assert "by simp" in response
        assert in_tokens == 100
        assert out_tokens == 20
    
    def test_mock_provider_without_sorry(self):
        """Test mock provider without sorry keyword."""
        provider = MockLLMProvider()
        response, in_tokens, out_tokens = provider.generate("Some other prompt")
        
        assert "No proof generated" in response
        assert in_tokens == 50
        assert out_tokens == 10


class TestGeminiProvider:
    """Tests for GeminiProvider (official SDK-based)."""
    
    def test_gemini_init_without_api_key(self):
        """Test Gemini provider requires API key."""
        # Clear environment variables
        old_gemini = os.environ.pop('GEMINI_API_KEY', None)
        old_google = os.environ.pop('GOOGLE_API_KEY', None)
        
        try:
            with pytest.raises(ValueError, match="Gemini API key not provided"):
                GeminiProvider()
        finally:
            # Restore environment variables if they existed
            if old_gemini:
                os.environ['GEMINI_API_KEY'] = old_gemini
            if old_google:
                os.environ['GOOGLE_API_KEY'] = old_google
    
    def test_gemini_init_with_gemini_api_key_env(self):
        """Test Gemini provider initialization with GEMINI_API_KEY."""
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}):
            with patch('google.generativeai.configure'):
                with patch('google.generativeai.GenerativeModel') as mock_model:
                    provider = GeminiProvider()
                    assert provider.api_key == 'test-key'
                    assert provider.model_name == 'gemini-2.0-flash'
    
    def test_gemini_init_with_google_api_key_env(self):
        """Test Gemini provider initialization with GOOGLE_API_KEY for backward compatibility."""
        os.environ.pop('GEMINI_API_KEY', None)  # Make sure GEMINI_API_KEY is not set
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-google-key'}):
            with patch('google.generativeai.configure'):
                with patch('google.generativeai.GenerativeModel') as mock_model:
                    provider = GeminiProvider()
                    assert provider.api_key == 'test-google-key'
    
    def test_gemini_init_with_explicit_key(self):
        """Test Gemini provider initialization with explicit API key."""
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel') as mock_model:
                provider = GeminiProvider(api_key='explicit-key', model='gemini-pro')
                assert provider.api_key == 'explicit-key'
                assert provider.model_name == 'gemini-pro'
    
    def test_gemini_generate_mock_response(self):
        """Test Gemini generate method with mocked response."""
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel') as mock_model_class:
                # Create mock response
                mock_response = Mock()
                mock_response.text = "theorem proof here"
                mock_response.usage_metadata = Mock()
                mock_response.usage_metadata.prompt_token_count = 50
                mock_response.usage_metadata.candidates_token_count = 100
                
                # Set up mock model
                mock_model = Mock()
                mock_model.generate_content.return_value = mock_response
                mock_model_class.return_value = mock_model
                
                # Test generation
                provider = GeminiProvider(api_key='test-key')
                response, in_tokens, out_tokens = provider.generate("test prompt")
                
                assert response == "theorem proof here"
                assert in_tokens == 50
                assert out_tokens == 100
    
    def test_gemini_generate_without_usage_metadata(self):
        """Test Gemini provider estimates tokens when metadata unavailable."""
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel') as mock_model_class:
                # Create mock response without usage metadata
                mock_response = Mock()
                mock_response.text = "response text"
                # No usage_metadata attribute
                
                mock_model = Mock()
                mock_model.generate_content.return_value = mock_response
                mock_model_class.return_value = mock_model
                
                provider = GeminiProvider(api_key='test-key')
                response, in_tokens, out_tokens = provider.generate("test prompt")
                
                assert response == "response text"
                # Should estimate tokens
                assert in_tokens > 0
                assert out_tokens > 0
    
    def test_gemini_generate_handles_errors(self):
        """Test Gemini provider gracefully handles generation errors."""
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel') as mock_model_class:
                mock_model = Mock()
                mock_model.generate_content.side_effect = Exception("API Error")
                mock_model_class.return_value = mock_model
                
                provider = GeminiProvider(api_key='test-key')
                response, in_tokens, out_tokens = provider.generate("test prompt")
                
                assert "Generation error" in response
                assert in_tokens == 0
                assert out_tokens == 0
    
    def test_gemini_repr(self):
        """Test string representation of Gemini provider."""
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel'):
                provider = GeminiProvider(api_key='test-key', model='gemini-pro')
                assert repr(provider) == "GeminiProvider(model=gemini-pro)"
    
    def test_google_provider_alias(self):
        """Test that GoogleProvider is an alias for GeminiProvider (backward compatibility)."""
        from src.llm.gemini import GoogleProvider
        assert GoogleProvider is GeminiProvider
