"""OpenRouter LLM provider for the Erdos Proof Mining System.

OpenRouter (openrouter.ai) is an OpenAI-compatible gateway: one API key
gives access to models from every major lab (Google, OpenAI, Anthropic,
Meta, ...). Uses only the Python standard library — no SDK required.
"""

import os
import json
import time
import random
import logging
import urllib.request
import urllib.error
from typing import Optional

from .base import LLMProvider

logger = logging.getLogger(__name__)


class OpenRouterAPIError(Exception):
    """Raised when the OpenRouter API returns a non-transient error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class OpenRouterProvider(LLMProvider):
    """
    LLM provider using OpenRouter's chat completions API.

    Speaks the OpenAI chat-completions schema at openrouter.ai, so any
    model on OpenRouter works (e.g. "google/gemini-2.5-flash",
    "openai/gpt-4o", "anthropic/claude-sonnet-4").
    Includes exponential backoff retry for transient errors.
    """

    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    DEFAULT_MODEL = "google/gemini-2.5-flash"
    MAX_RETRIES = 3
    BASE_DELAY = 1.0
    MAX_DELAY = 30.0
    _TRANSIENT_STATUS_CODES = {429, 500, 502, 503}

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_retries: int = MAX_RETRIES,
        timeout: int = 120,
    ):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key not provided. Set OPENROUTER_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model_name = model
        self.max_retries = max_retries
        self.timeout = timeout

        logger.info(f"Initialized OpenRouter provider with model: {model}")

    def _is_transient(self, error: Exception) -> bool:
        """Check if an error is transient and should be retried."""
        if isinstance(error, urllib.error.HTTPError):
            return error.code in self._TRANSIENT_STATUS_CODES

        error_str = str(error).lower()
        if any(
            kw in error_str
            for kw in ["rate limit", "overloaded", "unavailable", "timed out"]
        ):
            return True
        return False

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> tuple[str, int, int]:
        """Generate a response using OpenRouter with retry logic."""
        payload = json.dumps(
            {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        ).encode("utf-8")

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    self.API_URL,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                        # Optional attribution headers (see openrouter.ai/docs)
                        "HTTP-Referer": "https://github.com/Cuuper22/Erdos",
                        "X-Title": "Erdos",
                    },
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                choices = data.get("choices") or []
                message = choices[0].get("message", {}) if choices else {}
                response_text = message.get("content") or ""

                # OpenRouter reports token usage in the OpenAI format
                usage = data.get("usage") or {}
                input_tokens = usage.get("prompt_tokens") or len(prompt) // 4
                output_tokens = (
                    usage.get("completion_tokens") or len(response_text) // 4
                )

                logger.debug(
                    f"Generated {output_tokens} tokens "
                    f"(input: {input_tokens}, temp: {temperature})"
                )

                return response_text, input_tokens, output_tokens

            except Exception as e:
                last_error = e
                if isinstance(e, urllib.error.HTTPError):
                    error_body = ""
                    try:
                        error_body = e.read().decode("utf-8")
                    except Exception:
                        pass
                    logger.warning(
                        f"OpenRouter API error {e.code} on attempt "
                        f"{attempt + 1}/{self.max_retries + 1}: {error_body[:300]}"
                    )
                if attempt < self.max_retries and self._is_transient(e):
                    delay = min(
                        self.BASE_DELAY * (2**attempt) + random.uniform(0, 1),
                        self.MAX_DELAY,
                    )
                    logger.warning(
                        f"Transient error on attempt {attempt + 1}/{self.max_retries + 1}, "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)
                    continue
                break

        logger.error(
            f"OpenRouter generation failed after {self.max_retries + 1} attempts: {last_error}"
        )
        raise OpenRouterAPIError(
            f"Generation failed: {last_error}",
            status_code=getattr(last_error, "code", None),
        ) from last_error

    def __repr__(self) -> str:
        return f"OpenRouterProvider(model={self.model_name})"
