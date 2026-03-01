"""Gemini LLM provider using Google's official generative AI SDK.

Uses the google-generativeai SDK with exponential backoff retry
for transient API failures (429, 503, 500).
"""

import os
import time
import random
import logging
from typing import Optional

from .base import LLMProvider

logger = logging.getLogger(__name__)

# HTTP status codes that are transient and should be retried
_TRANSIENT_STATUS_CODES = {429, 500, 503}


class GeminiAPIError(Exception):
    """Raised when the Gemini API returns a non-transient error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class GeminiProvider(LLMProvider):
    """
    LLM provider using Google's Gemini models via official SDK.

    Features:
    - Exponential backoff retry for transient errors (429, 503, 500)
    - Proper exception raising instead of returning error text
    - Configurable timeout and retry parameters
    """

    DEFAULT_MODEL = "gemini-3-flash"
    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # seconds
    MAX_DELAY = 30.0  # seconds

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_retries: int = MAX_RETRIES,
        timeout: int = 60,
    ):
        try:
            import google.generativeai as genai
            self._genai = genai
        except ImportError:
            raise ImportError(
                "google-generativeai package not installed. "
                "Install it with: pip install google-generativeai"
            )

        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key not provided. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self._genai.configure(api_key=self.api_key)

        self.model_name = model
        self.max_retries = max_retries
        self.timeout = timeout

        try:
            self.model = self._genai.GenerativeModel(model)
            logger.info(f"Initialized Gemini provider with model: {model}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model {model}: {e}")
            raise

    def _is_transient(self, error: Exception) -> bool:
        """Check if an error is transient and should be retried."""
        error_str = str(error).lower()
        # Check for HTTP status codes in the error message
        for code in _TRANSIENT_STATUS_CODES:
            if str(code) in error_str:
                return True
        # Check for common transient error messages
        if any(kw in error_str for kw in ["rate limit", "quota", "overloaded", "unavailable", "deadline"]):
            return True
        return False

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> tuple[str, int, int]:
        """
        Generate a response using Gemini with retry logic.

        Retries transient errors (429, 503, 500) with exponential backoff.
        Raises GeminiAPIError for non-transient failures.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens)
        """
        generation_config = self._genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config,
                )

                response_text = response.text if hasattr(response, 'text') else ""

                input_tokens = 0
                output_tokens = 0

                if hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata
                    input_tokens = getattr(usage, 'prompt_token_count', 0)
                    output_tokens = getattr(usage, 'candidates_token_count', 0)

                # Fallback: estimate tokens if not provided
                if input_tokens == 0:
                    input_tokens = len(prompt) // 4
                if output_tokens == 0:
                    output_tokens = len(response_text) // 4

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
                # Non-transient or exhausted retries
                break

        logger.error(f"Gemini generation failed after {self.max_retries + 1} attempts: {last_error}")
        raise GeminiAPIError(
            f"Generation failed: {last_error}",
            status_code=None,
        ) from last_error

    def __repr__(self) -> str:
        return f"GeminiProvider(model={self.model_name})"


# Alias for backward compatibility
GoogleProvider = GeminiProvider
