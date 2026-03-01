"""Tests for LLM providers."""

import sys
import os
import json
import urllib.error
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.llm import LLMProvider, MockLLMProvider, GeminiProvider
from src.llm.gemini import GeminiAPIError

# Create mock modules for optional SDKs so tests work without them installed
_mock_openai = MagicMock()
_mock_openai.OpenAI = MagicMock
_mock_openai.RateLimitError = type('RateLimitError', (Exception,), {})
_mock_openai.APIStatusError = type('APIStatusError', (Exception,), {'status_code': 500})

_mock_anthropic = MagicMock()
_mock_anthropic.Anthropic = MagicMock
_mock_anthropic.RateLimitError = type('RateLimitError', (Exception,), {})
_mock_anthropic.OverloadedError = type('OverloadedError', (Exception,), {})
_mock_anthropic.APIStatusError = type('APIStatusError', (Exception,), {'status_code': 500})

# Inject mock modules if real ones aren't installed
if 'openai' not in sys.modules:
    sys.modules['openai'] = _mock_openai
if 'anthropic' not in sys.modules:
    sys.modules['anthropic'] = _mock_anthropic

from src.llm.openai_provider import OpenAIProvider, OpenAIAPIError
from src.llm.anthropic_provider import AnthropicProvider, AnthropicAPIError


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
        old_gemini = os.environ.pop('GEMINI_API_KEY', None)
        old_google = os.environ.pop('GOOGLE_API_KEY', None)

        try:
            with pytest.raises(ValueError, match="Gemini API key not provided"):
                GeminiProvider()
        finally:
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
                    assert provider.model_name == 'gemini-3-flash'

    def test_gemini_init_with_google_api_key_env(self):
        """Test Gemini provider initialization with GOOGLE_API_KEY."""
        os.environ.pop('GEMINI_API_KEY', None)
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
                mock_response = Mock()
                mock_response.text = "theorem proof here"
                mock_response.usage_metadata = Mock()
                mock_response.usage_metadata.prompt_token_count = 50
                mock_response.usage_metadata.candidates_token_count = 100

                mock_model = Mock()
                mock_model.generate_content.return_value = mock_response
                mock_model_class.return_value = mock_model

                provider = GeminiProvider(api_key='test-key')
                response, in_tokens, out_tokens = provider.generate("test prompt")

                assert response == "theorem proof here"
                assert in_tokens == 50
                assert out_tokens == 100

    def test_gemini_generate_without_usage_metadata(self):
        """Test Gemini provider estimates tokens when metadata unavailable."""
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel') as mock_model_class:
                mock_response = Mock(spec=['text'])
                mock_response.text = "response text"

                mock_model = Mock()
                mock_model.generate_content.return_value = mock_response
                mock_model_class.return_value = mock_model

                provider = GeminiProvider(api_key='test-key')
                response, in_tokens, out_tokens = provider.generate("test prompt")

                assert response == "response text"
                assert in_tokens > 0
                assert out_tokens > 0

    def test_gemini_generate_raises_on_non_transient_error(self):
        """Test that non-transient errors raise GeminiAPIError immediately."""
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel') as mock_model_class:
                mock_model = Mock()
                mock_model.generate_content.side_effect = Exception("Invalid API key")
                mock_model_class.return_value = mock_model

                provider = GeminiProvider(api_key='test-key', max_retries=2)

                with pytest.raises(GeminiAPIError, match="Generation failed"):
                    provider.generate("test prompt")

                # Should NOT retry — only 1 call
                assert mock_model.generate_content.call_count == 1

    def test_gemini_generate_retries_transient_errors(self):
        """Test that transient errors (429, 503) are retried."""
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel') as mock_model_class:
                mock_response = Mock()
                mock_response.text = "success"
                mock_response.usage_metadata = Mock()
                mock_response.usage_metadata.prompt_token_count = 10
                mock_response.usage_metadata.candidates_token_count = 5

                mock_model = Mock()
                # Fail twice with rate limit, then succeed
                mock_model.generate_content.side_effect = [
                    Exception("429 rate limit exceeded"),
                    Exception("503 service unavailable"),
                    mock_response,
                ]
                mock_model_class.return_value = mock_model

                provider = GeminiProvider(api_key='test-key', max_retries=3)
                # Patch sleep to avoid actual delays in tests
                with patch('src.llm.gemini.time.sleep'):
                    response, in_tokens, out_tokens = provider.generate("test")

                assert response == "success"
                assert mock_model.generate_content.call_count == 3

    def test_gemini_generate_exhausts_retries(self):
        """Test that exhausting retries raises GeminiAPIError."""
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel') as mock_model_class:
                mock_model = Mock()
                mock_model.generate_content.side_effect = Exception("429 rate limit exceeded")
                mock_model_class.return_value = mock_model

                provider = GeminiProvider(api_key='test-key', max_retries=2)

                with patch('src.llm.gemini.time.sleep'):
                    with pytest.raises(GeminiAPIError):
                        provider.generate("test")

                # 1 initial + 2 retries = 3 total
                assert mock_model.generate_content.call_count == 3

    def test_gemini_repr(self):
        """Test string representation of Gemini provider."""
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel'):
                provider = GeminiProvider(api_key='test-key', model='gemini-pro')
                assert repr(provider) == "GeminiProvider(model=gemini-pro)"

    def test_google_provider_alias(self):
        """Test that GoogleProvider is an alias for GeminiProvider."""
        from src.llm.gemini import GoogleProvider
        assert GoogleProvider is GeminiProvider


class TestOpenAIProvider:
    """Tests for OpenAIProvider."""

    def _make_provider(self, **kwargs):
        """Helper to create an OpenAIProvider with mocked openai client."""
        mock_client = Mock()
        with patch.object(sys.modules['openai'], 'OpenAI', return_value=mock_client):
            provider = OpenAIProvider(api_key='sk-test', **kwargs)
        return provider, mock_client

    def test_openai_init_without_api_key(self):
        """Test OpenAI provider requires API key."""
        old = os.environ.pop('OPENAI_API_KEY', None)
        try:
            with pytest.raises(ValueError, match="OpenAI API key not provided"):
                OpenAIProvider()
        finally:
            if old:
                os.environ['OPENAI_API_KEY'] = old

    def test_openai_init_with_explicit_key(self):
        """Test OpenAI provider initialization with explicit key."""
        provider, _ = self._make_provider(model='gpt-4')
        assert provider.api_key == 'sk-test'
        assert provider.model_name == 'gpt-4'

    def test_openai_generate_mock_response(self):
        """Test OpenAI generate with mocked response."""
        provider, mock_client = self._make_provider()

        mock_choice = Mock()
        mock_choice.message.content = "proof by simp"
        mock_usage = Mock()
        mock_usage.prompt_tokens = 40
        mock_usage.completion_tokens = 80
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client.chat.completions.create.return_value = mock_response

        response, in_tokens, out_tokens = provider.generate("test prompt")
        assert response == "proof by simp"
        assert in_tokens == 40
        assert out_tokens == 80

    def test_openai_generate_raises_on_non_transient_error(self):
        """Test non-transient errors raise OpenAIAPIError."""
        provider, mock_client = self._make_provider(max_retries=1)
        mock_client.chat.completions.create.side_effect = Exception("Invalid auth")

        with pytest.raises(OpenAIAPIError, match="Generation failed"):
            provider.generate("test")

        assert mock_client.chat.completions.create.call_count == 1

    def test_openai_generate_retries_transient_errors(self):
        """Test transient errors are retried."""
        provider, mock_client = self._make_provider(max_retries=2)

        mock_choice = Mock()
        mock_choice.message.content = "ok"
        mock_usage = Mock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client.chat.completions.create.side_effect = [
            Exception("429 rate limit"),
            mock_response,
        ]

        with patch('src.llm.openai_provider.time.sleep'):
            response, _, _ = provider.generate("test")

        assert response == "ok"
        assert mock_client.chat.completions.create.call_count == 2

    def test_openai_repr(self):
        """Test string representation."""
        provider, _ = self._make_provider(model='gpt-4o')
        assert repr(provider) == "OpenAIProvider(model=gpt-4o)"


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    def _make_provider(self, **kwargs):
        """Helper to create an AnthropicProvider with mocked client."""
        mock_client = Mock()
        with patch.object(sys.modules['anthropic'], 'Anthropic', return_value=mock_client):
            provider = AnthropicProvider(api_key='sk-ant-test', **kwargs)
        return provider, mock_client

    def test_anthropic_init_without_api_key(self):
        """Test Anthropic provider requires API key."""
        old = os.environ.pop('ANTHROPIC_API_KEY', None)
        try:
            with pytest.raises(ValueError, match="Anthropic API key not provided"):
                AnthropicProvider()
        finally:
            if old:
                os.environ['ANTHROPIC_API_KEY'] = old

    def test_anthropic_init_with_explicit_key(self):
        """Test Anthropic provider initialization."""
        provider, _ = self._make_provider(model='claude-haiku-4-5-20251001')
        assert provider.api_key == 'sk-ant-test'
        assert provider.model_name == 'claude-haiku-4-5-20251001'

    def test_anthropic_generate_mock_response(self):
        """Test Anthropic generate with mocked response."""
        provider, mock_client = self._make_provider()

        mock_block = Mock()
        mock_block.type = "text"
        mock_block.text = "proof complete"
        mock_usage = Mock()
        mock_usage.input_tokens = 30
        mock_usage.output_tokens = 60
        mock_response = Mock()
        mock_response.content = [mock_block]
        mock_response.usage = mock_usage

        mock_client.messages.create.return_value = mock_response

        response, in_tokens, out_tokens = provider.generate("test prompt")
        assert response == "proof complete"
        assert in_tokens == 30
        assert out_tokens == 60

    def test_anthropic_generate_raises_on_non_transient_error(self):
        """Test non-transient errors raise AnthropicAPIError."""
        provider, mock_client = self._make_provider(max_retries=1)
        mock_client.messages.create.side_effect = Exception("Invalid key")

        with pytest.raises(AnthropicAPIError, match="Generation failed"):
            provider.generate("test")

        assert mock_client.messages.create.call_count == 1

    def test_anthropic_generate_retries_transient_errors(self):
        """Test transient errors are retried."""
        provider, mock_client = self._make_provider(max_retries=2)

        mock_block = Mock()
        mock_block.type = "text"
        mock_block.text = "ok"
        mock_usage = Mock()
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 5
        mock_response = Mock()
        mock_response.content = [mock_block]
        mock_response.usage = mock_usage

        mock_client.messages.create.side_effect = [
            Exception("529 overloaded"),
            mock_response,
        ]

        with patch('src.llm.anthropic_provider.time.sleep'):
            response, _, _ = provider.generate("test")

        assert response == "ok"
        assert mock_client.messages.create.call_count == 2

    def test_anthropic_repr(self):
        """Test string representation."""
        provider, _ = self._make_provider()
        assert repr(provider) == f"AnthropicProvider(model={AnthropicProvider.DEFAULT_MODEL})"


class TestOllamaProvider:
    """Tests for OllamaProvider."""

    def test_ollama_init(self):
        """Test Ollama provider initialization."""
        from src.llm.ollama_provider import OllamaProvider
        provider = OllamaProvider(model="codellama", base_url="http://localhost:11434")
        assert provider.model_name == "codellama"
        assert provider.base_url == "http://localhost:11434"

    def test_ollama_generate_mock_response(self):
        """Test Ollama generate with mocked HTTP."""
        from src.llm.ollama_provider import OllamaProvider
        provider = OllamaProvider()

        mock_data = json.dumps({
            "response": "proof by induction",
            "prompt_eval_count": 25,
            "eval_count": 40,
        }).encode("utf-8")

        mock_resp = Mock()
        mock_resp.read.return_value = mock_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_resp):
            response, in_tokens, out_tokens = provider.generate("test")

        assert response == "proof by induction"
        assert in_tokens == 25
        assert out_tokens == 40

    def test_ollama_connection_error(self):
        """Test Ollama raises on connection failure."""
        from src.llm.ollama_provider import OllamaProvider, OllamaAPIError
        provider = OllamaProvider(base_url="http://localhost:99999")

        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Connection refused")):
            with pytest.raises(OllamaAPIError, match="Cannot connect"):
                provider.generate("test")

    def test_ollama_repr(self):
        """Test string representation."""
        from src.llm.ollama_provider import OllamaProvider
        provider = OllamaProvider(model="llama3.2", base_url="http://localhost:11434")
        assert "OllamaProvider" in repr(provider)
        assert "llama3.2" in repr(provider)


class TestProviderFactory:
    """Tests for create_provider factory."""

    _SYSTEM_KEYS = {"HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}

    def _clean_env(self):
        """Clear env but preserve system-critical keys."""
        saved = {k: os.environ[k] for k in self._SYSTEM_KEYS if k in os.environ}
        os.environ.clear()
        os.environ.update(saved)

    def test_factory_returns_mock_in_mock_mode(self):
        """Test factory returns MockLLMProvider when ERDOS_MOCK_MODE is set."""
        from src.llm.factory import create_provider
        self._clean_env()
        os.environ["ERDOS_MOCK_MODE"] = "1"
        provider = create_provider()
        assert isinstance(provider, MockLLMProvider)

    def test_factory_auto_detects_gemini(self):
        """Test factory auto-detects GEMINI_API_KEY."""
        from src.llm.factory import create_provider
        self._clean_env()
        os.environ["GEMINI_API_KEY"] = "test-key"
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel'):
                provider = create_provider()
        assert isinstance(provider, GeminiProvider)

    def test_factory_from_config(self):
        """Test factory creates provider from explicit config."""
        from src.llm.factory import create_provider
        from src.config import Config
        config = Config()
        config.llm.provider = "google"
        config.llm.api_key = "test-key"
        config.llm.model = "gemini-3-flash"
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel'):
                provider = create_provider(config)
        assert isinstance(provider, GeminiProvider)

    def test_factory_fallback_to_mock(self):
        """Test factory falls back to MockLLMProvider when no provider available."""
        from src.llm.factory import create_provider
        self._clean_env()
        provider = create_provider()
        assert isinstance(provider, MockLLMProvider)
