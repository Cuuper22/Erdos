"""LLM provider implementations for Erdos."""

from .base import LLMProvider
from .mock import MockLLMProvider
from .gemini import GeminiProvider, GeminiAPIError
from .ollama_provider import OllamaProvider, OllamaAPIError
from .openrouter_provider import OpenRouterProvider, OpenRouterAPIError
from .factory import create_provider

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

from .chatgpt_provider import ChatGPTProvider, ChatGPTAPIError

__all__ = [
    "LLMProvider",
    "MockLLMProvider",
    "GeminiProvider",
    "GeminiAPIError",
    "OpenAIProvider",
    "OpenAIAPIError",
    "AnthropicProvider",
    "AnthropicAPIError",
    "OllamaProvider",
    "OllamaAPIError",
    "OpenRouterProvider",
    "OpenRouterAPIError",
    "ChatGPTProvider",
    "ChatGPTAPIError",
    "create_provider",
]
