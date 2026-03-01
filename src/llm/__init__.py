"""LLM provider implementations for Erdos."""

from .base import LLMProvider
from .mock import MockLLMProvider
from .gemini import GeminiProvider, GeminiAPIError

# Optional providers — only available when their SDK is installed
try:
    from .openai_provider import OpenAIProvider, OpenAIAPIError
except ImportError:
    OpenAIProvider = None
    OpenAIAPIError = None

try:
    from .anthropic_provider import AnthropicProvider, AnthropicAPIError
except ImportError:
    AnthropicProvider = None
    AnthropicAPIError = None

__all__ = [
    'LLMProvider',
    'MockLLMProvider',
    'GeminiProvider',
    'GeminiAPIError',
    'OpenAIProvider',
    'OpenAIAPIError',
    'AnthropicProvider',
    'AnthropicAPIError',
]
