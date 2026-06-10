"""Tests for the OpenRouter provider."""

import io
import os
import json
import urllib.error
import pytest
from unittest.mock import Mock, patch

from src.llm import OpenRouterProvider, OpenRouterAPIError


def _mock_response(payload: dict) -> Mock:
    """Build a context-manager mock mimicking urllib's HTTP response."""
    mock_resp = Mock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = Mock(return_value=False)
    return mock_resp


def _http_error(code: int, body: bytes = b'{"error": {"message": "boom"}}') -> urllib.error.HTTPError:
    """Build an HTTPError with a readable body, as urllib raises them."""
    return urllib.error.HTTPError(
        url=OpenRouterProvider.API_URL,
        code=code,
        msg="error",
        hdrs=None,
        fp=io.BytesIO(body),
    )


_SUCCESS_PAYLOAD = {
    "choices": [{"message": {"role": "assistant", "content": "proof by simp"}}],
    "usage": {"prompt_tokens": 25, "completion_tokens": 40},
}


class TestOpenRouterInit:
    """Tests for OpenRouterProvider initialization."""

    def test_init_without_api_key(self):
        """Test OpenRouter provider requires API key."""
        old = os.environ.pop('OPENROUTER_API_KEY', None)
        try:
            with pytest.raises(ValueError, match="OpenRouter API key not provided"):
                OpenRouterProvider()
        finally:
            if old:
                os.environ['OPENROUTER_API_KEY'] = old

    def test_init_with_env_key(self):
        """Test OpenRouter provider initialization with OPENROUTER_API_KEY."""
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'sk-or-env'}):
            provider = OpenRouterProvider()
            assert provider.api_key == 'sk-or-env'
            assert provider.model_name == 'google/gemini-2.5-flash'

    def test_init_with_explicit_key(self):
        """Test OpenRouter provider initialization with explicit key."""
        provider = OpenRouterProvider(api_key='sk-or-test', model='openai/gpt-4o')
        assert provider.api_key == 'sk-or-test'
        assert provider.model_name == 'openai/gpt-4o'


class TestOpenRouterGenerate:
    """Tests for OpenRouterProvider.generate."""

    def _make_provider(self, **kwargs):
        return OpenRouterProvider(api_key='sk-or-test', **kwargs)

    def test_generate_request_payload_shape(self):
        """Test the request URL, headers, and OpenAI-schema body."""
        provider = self._make_provider()
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured['req'] = req
            captured['timeout'] = timeout
            return _mock_response(_SUCCESS_PAYLOAD)

        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            provider.generate("prove this", temperature=0.3, max_tokens=512)

        req = captured['req']
        assert req.full_url == "https://openrouter.ai/api/v1/chat/completions"
        assert req.get_method() == "POST"
        # urllib normalizes header names via str.capitalize()
        assert req.get_header('Authorization') == 'Bearer sk-or-test'
        assert req.get_header('Content-type') == 'application/json'
        assert req.get_header('Http-referer') == 'https://github.com/Cuuper22/Erdos'
        assert req.get_header('X-title') == 'Erdos'

        body = json.loads(req.data.decode("utf-8"))
        assert body["model"] == "google/gemini-2.5-flash"
        assert body["messages"] == [{"role": "user", "content": "prove this"}]
        assert body["temperature"] == 0.3
        assert body["max_tokens"] == 512

    def test_generate_mock_response(self):
        """Test generate with mocked HTTP success."""
        provider = self._make_provider()

        with patch('urllib.request.urlopen', return_value=_mock_response(_SUCCESS_PAYLOAD)):
            response, in_tokens, out_tokens = provider.generate("test")

        assert response == "proof by simp"
        assert in_tokens == 25
        assert out_tokens == 40

    def test_generate_estimates_tokens_without_usage(self):
        """Test token estimation when the usage field is missing."""
        provider = self._make_provider()
        payload = {"choices": [{"message": {"content": "a proof, twenty chars"}}]}

        with patch('urllib.request.urlopen', return_value=_mock_response(payload)):
            response, in_tokens, out_tokens = provider.generate("a prompt of some length")

        assert response == "a proof, twenty chars"
        assert in_tokens > 0
        assert out_tokens > 0

    def test_generate_handles_empty_choices(self):
        """Test generate returns empty text when choices are missing."""
        provider = self._make_provider()

        with patch('urllib.request.urlopen', return_value=_mock_response({"choices": []})):
            response, _, _ = provider.generate("test")

        assert response == ""

    def test_generate_retries_transient_errors(self):
        """Test transient HTTP errors (429, 503) are retried."""
        provider = self._make_provider(max_retries=3)

        with patch('urllib.request.urlopen', side_effect=[
            _http_error(429),
            _http_error(503),
            _mock_response(_SUCCESS_PAYLOAD),
        ]) as mock_urlopen:
            with patch('src.llm.openrouter_provider.time.sleep'):
                response, _, _ = provider.generate("test")

        assert response == "proof by simp"
        assert mock_urlopen.call_count == 3

    def test_generate_exhausts_retries(self):
        """Test exhausting retries raises OpenRouterAPIError."""
        provider = self._make_provider(max_retries=2)

        with patch('urllib.request.urlopen', side_effect=_http_error(503)) as mock_urlopen:
            with patch('src.llm.openrouter_provider.time.sleep'):
                with pytest.raises(OpenRouterAPIError, match="Generation failed") as exc_info:
                    provider.generate("test")

        # 1 initial + 2 retries = 3 total
        assert mock_urlopen.call_count == 3
        assert exc_info.value.status_code == 503

    def test_generate_raises_on_non_transient_error(self):
        """Test non-transient errors (400) raise immediately without retry."""
        provider = self._make_provider(max_retries=2)

        with patch('urllib.request.urlopen', side_effect=_http_error(400)) as mock_urlopen:
            with pytest.raises(OpenRouterAPIError, match="Generation failed") as exc_info:
                provider.generate("test")

        # Should NOT retry — only 1 call
        assert mock_urlopen.call_count == 1
        assert exc_info.value.status_code == 400

    def test_generate_raises_on_connection_error(self):
        """Test connection failures raise OpenRouterAPIError."""
        provider = self._make_provider(max_retries=1)

        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Connection refused")):
            with pytest.raises(OpenRouterAPIError, match="Generation failed"):
                provider.generate("test")


class TestOpenRouterFactory:
    """Tests for OpenRouter creation via the provider factory."""

    _SYSTEM_KEYS = {"HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}

    def _clean_env(self):
        """Clear env but preserve system-critical keys."""
        saved = {k: os.environ[k] for k in self._SYSTEM_KEYS if k in os.environ}
        os.environ.clear()
        os.environ.update(saved)

    def test_factory_from_config(self):
        """Test factory creates OpenRouterProvider from explicit config."""
        from src.llm.factory import create_provider
        from src.config import Config
        config = Config()
        config.llm.provider = "openrouter"
        config.llm.api_key = "sk-or-test"
        config.llm.model = "google/gemini-2.5-flash"
        provider = create_provider(config)
        assert isinstance(provider, OpenRouterProvider)
        assert provider.model_name == "google/gemini-2.5-flash"

    def test_factory_auto_detects_openrouter(self):
        """Test factory auto-detects OPENROUTER_API_KEY."""
        from src.llm.factory import create_provider
        original_env = os.environ.copy()
        self._clean_env()
        try:
            os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
            provider = create_provider()
            assert isinstance(provider, OpenRouterProvider)
            assert provider.model_name == OpenRouterProvider.DEFAULT_MODEL
        finally:
            os.environ.clear()
            os.environ.update(original_env)


class TestOpenRouterRepr:
    """Tests for OpenRouterProvider string representation."""

    def test_repr(self):
        """Test string representation."""
        provider = OpenRouterProvider(api_key='sk-or-test', model='google/gemini-2.5-flash')
        assert repr(provider) == "OpenRouterProvider(model=google/gemini-2.5-flash)"
