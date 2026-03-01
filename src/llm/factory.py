"""Provider factory for automatic LLM provider selection."""

import os
import logging
from typing import Optional

from .base import LLMProvider
from .mock import MockLLMProvider
from ..config import Config

logger = logging.getLogger(__name__)

# Provider registry: (config_name, env_var, provider_class_path)
_PROVIDER_PRIORITY = [
    ("google", "GOOGLE_API_KEY", "gemini"),
    ("google", "GEMINI_API_KEY", "gemini"),
    ("openai", "OPENAI_API_KEY", "openai"),
    ("anthropic", "ANTHROPIC_API_KEY", "anthropic"),
    ("ollama", "OLLAMA_URL", "ollama"),
]


def create_provider(config: Optional[Config] = None) -> LLMProvider:
    """
    Create the appropriate LLM provider based on config and environment.

    Priority:
    1. Explicit provider in config (if config.llm.provider + api_key set)
    2. Auto-detect from environment variables
    3. MockLLMProvider as fallback

    Args:
        config: Optional Config object. If None, auto-detects from env.

    Returns:
        An initialized LLMProvider instance.
    """
    if config and config.llm.api_key:
        return _create_from_config(config)

    # Auto-detect from environment
    provider = _auto_detect(config)
    if provider:
        return provider

    # Check for mock mode
    if os.environ.get("ERDOS_MOCK_MODE"):
        logger.info("Using MockLLMProvider (ERDOS_MOCK_MODE set)")
        return MockLLMProvider()

    logger.warning("No LLM provider configured, falling back to MockLLMProvider")
    return MockLLMProvider()


def _create_from_config(config: Config) -> LLMProvider:
    """Create provider from explicit config values."""
    provider_name = config.llm.provider
    api_key = config.llm.api_key
    model = config.llm.model

    if provider_name in ("google", "gemini"):
        from .gemini import GeminiProvider
        return GeminiProvider(api_key=api_key, model=model)

    elif provider_name == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=api_key, model=model)

    elif provider_name == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=api_key, model=model)

    elif provider_name == "ollama":
        from .ollama_provider import OllamaProvider
        return OllamaProvider(
            model=model,
            base_url=config.llm.ollama_url,
        )

    else:
        raise ValueError(f"Unknown provider: {provider_name}")


def _auto_detect(config: Optional[Config] = None) -> Optional[LLMProvider]:
    """Auto-detect provider from environment variables."""
    model = config.llm.model if config else None

    # Check GEMINI_API_KEY first (more specific)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        from .gemini import GeminiProvider
        logger.info("Auto-detected GEMINI_API_KEY")
        return GeminiProvider(api_key=gemini_key, model=model or GeminiProvider.DEFAULT_MODEL)

    # Then GOOGLE_API_KEY
    google_key = os.environ.get("GOOGLE_API_KEY")
    if google_key:
        from .gemini import GeminiProvider
        logger.info("Auto-detected GOOGLE_API_KEY")
        return GeminiProvider(api_key=google_key, model=model or GeminiProvider.DEFAULT_MODEL)

    # OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            from .openai_provider import OpenAIProvider
            logger.info("Auto-detected OPENAI_API_KEY")
            return OpenAIProvider(api_key=openai_key, model=model or OpenAIProvider.DEFAULT_MODEL)
        except ImportError:
            logger.warning("OPENAI_API_KEY found but openai package not installed")

    # Anthropic
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            from .anthropic_provider import AnthropicProvider
            logger.info("Auto-detected ANTHROPIC_API_KEY")
            return AnthropicProvider(api_key=anthropic_key, model=model or AnthropicProvider.DEFAULT_MODEL)
        except ImportError:
            logger.warning("ANTHROPIC_API_KEY found but anthropic package not installed")

    # Ollama (check if running)
    ollama_url = os.environ.get("OLLAMA_URL")
    if ollama_url:
        from .ollama_provider import OllamaProvider
        logger.info(f"Auto-detected OLLAMA_URL: {ollama_url}")
        return OllamaProvider(
            model=model or OllamaProvider.DEFAULT_MODEL,
            base_url=ollama_url,
        )

    return None
