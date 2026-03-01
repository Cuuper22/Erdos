"""Anthropic LLM provider for the Erdos Proof Mining System."""

import os
import time
import random
import logging
from typing import Optional

from .base import LLMProvider

logger = logging.getLogger(__name__)


class AnthropicAPIError(Exception):
    """Raised when the Anthropic API returns a non-transient error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class AnthropicProvider(LLMProvider):
    """
    LLM provider using Anthropic's messages API.

    Supports Claude models (claude-sonnet-4-20250514, claude-haiku, etc).
    Includes exponential backoff retry for transient errors.
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    MAX_RETRIES = 3
    BASE_DELAY = 1.0
    MAX_DELAY = 30.0
    _TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 529}

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_retries: int = MAX_RETRIES,
        timeout: int = 60,
    ):
        try:
            import anthropic
            self._anthropic = anthropic
        except ImportError:
            raise ImportError(
                "anthropic package not installed. "
                "Install it with: pip install erdos-prover[anthropic]"
            )

        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model_name = model
        self.max_retries = max_retries
        self.timeout = timeout
        self.client = self._anthropic.Anthropic(api_key=self.api_key, timeout=timeout)
        logger.info(f"Initialized Anthropic provider with model: {model}")

    def _is_transient(self, error: Exception) -> bool:
        """Check if an error is transient and should be retried."""
        if hasattr(self._anthropic, 'RateLimitError') and isinstance(error, self._anthropic.RateLimitError):
            return True
        if hasattr(self._anthropic, 'OverloadedError') and isinstance(error, self._anthropic.OverloadedError):
            return True
        if hasattr(self._anthropic, 'APIStatusError') and isinstance(error, self._anthropic.APIStatusError):
            return getattr(error, 'status_code', 0) in self._TRANSIENT_STATUS_CODES

        error_str = str(error).lower()
        if any(kw in error_str for kw in ["rate limit", "overloaded", "unavailable"]):
            return True
        return False

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> tuple[str, int, int]:
        """Generate a response using Anthropic with retry logic."""
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                )

                response_text = ""
                for block in response.content:
                    if block.type == "text":
                        response_text += block.text

                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens

                logger.debug(
                    f"Generated {output_tokens} tokens "
                    f"(input: {input_tokens}, temp: {temperature})"
                )

                return response_text, input_tokens, output_tokens

            except Exception as e:
                last_error = e
                if attempt < self.max_retries and self._is_transient(e):
                    delay = min(
                        self.BASE_DELAY * (2 ** attempt) + random.uniform(0, 1),
                        self.MAX_DELAY,
                    )
                    logger.warning(
                        f"Transient error on attempt {attempt + 1}/{self.max_retries + 1}, "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)
                    continue
                break

        logger.error(f"Anthropic generation failed after {self.max_retries + 1} attempts: {last_error}")
        raise AnthropicAPIError(
            f"Generation failed: {last_error}",
            status_code=getattr(last_error, 'status_code', None),
        ) from last_error

    def __repr__(self) -> str:
        return f"AnthropicProvider(model={self.model_name})"
