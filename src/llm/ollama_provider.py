"""Ollama LLM provider for local model inference."""

import json
import logging
import urllib.request
import urllib.error
from typing import Optional

from .base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaAPIError(Exception):
    """Raised when the Ollama API returns an error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class OllamaProvider(LLMProvider):
    """
    LLM provider using local Ollama instance.

    Communicates via REST API at localhost:11434 (default).
    No external SDK dependency required.
    """

    DEFAULT_MODEL = "llama3.2"
    DEFAULT_URL = "http://localhost:11434"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_URL,
        timeout: int = 120,
    ):
        self.model_name = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        logger.info(f"Initialized Ollama provider: {model} @ {self.base_url}")

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> tuple[str, int, int]:
        """Generate a response using local Ollama."""
        url = f"{self.base_url}/api/generate"

        payload = json.dumps({
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise OllamaAPIError(
                f"Cannot connect to Ollama at {self.base_url}: {e}"
            ) from e
        except urllib.error.HTTPError as e:
            raise OllamaAPIError(
                f"Ollama API error: {e.code} {e.reason}",
                status_code=e.code,
            ) from e

        response_text = data.get("response", "")

        # Ollama provides token counts in eval_count and prompt_eval_count
        input_tokens = data.get("prompt_eval_count", len(prompt) // 4)
        output_tokens = data.get("eval_count", len(response_text) // 4)

        logger.debug(
            f"Generated {output_tokens} tokens "
            f"(input: {input_tokens}, temp: {temperature})"
        )

        return response_text, input_tokens, output_tokens

    def __repr__(self) -> str:
        return f"OllamaProvider(model={self.model_name}, url={self.base_url})"
