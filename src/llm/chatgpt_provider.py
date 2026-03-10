"""ChatGPT OAuth provider for the Erdos Proof Mining System.

Uses the ChatGPT backend API with Codex-style OAuth tokens.
No API key required — authenticates via ChatGPT account tokens.
"""

import json
import time
import base64
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from .base import LLMProvider

logger = logging.getLogger(__name__)


class ChatGPTAPIError(Exception):
    """Raised when the ChatGPT backend API returns an error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class ChatGPTProvider(LLMProvider):
    """
    LLM provider using ChatGPT OAuth (Codex auth flow).

    Authenticates via OAuth access_token from a ChatGPT account,
    calling the ChatGPT backend API at chatgpt.com/backend-api/codex/responses.
    No OPENAI_API_KEY needed — uses the user's ChatGPT subscription.
    """

    CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex/responses"
    TOKEN_URL = "https://auth.openai.com/oauth/token"
    CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
    DEFAULT_MODEL = "gpt-5.4"
    MAX_RETRIES = 3
    BASE_DELAY = 1.0
    MAX_DELAY = 30.0

    def __init__(
        self,
        auth_file: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        reasoning_effort: str = "high",
        max_retries: int = MAX_RETRIES,
    ):
        self.model_name = model
        self.reasoning_effort = reasoning_effort
        self.max_retries = max_retries

        # Load auth tokens
        auth_path = Path(auth_file or "chatgpt_auth.json")
        if not auth_path.exists():
            raise FileNotFoundError(
                f"ChatGPT auth file not found: {auth_path}\n"
                "Create it with your ChatGPT OAuth tokens:\n"
                '  {"access_token": "eyJ...", "refresh_token": "rt_...", "account_id": "..."}'
            )

        with open(auth_path) as f:
            auth_data = json.load(f)

        self.access_token = auth_data["access_token"]
        self.refresh_token = auth_data["refresh_token"]
        self.account_id = auth_data.get("account_id") or self._extract_account_id(self.access_token)
        self.auth_path = auth_path

        # Check token expiry from JWT
        self._token_exp = self._get_token_expiry(self.access_token)

        logger.info(
            f"Initialized ChatGPT provider with model: {model}, "
            f"reasoning_effort: {reasoning_effort}, account: {self.account_id[:8]}..."
        )

    def _decode_jwt_payload(self, token: str) -> dict:
        """Decode a JWT token payload (no signature verification)."""
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT token format")
        # Add padding for base64
        payload = parts[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)

    def _extract_account_id(self, access_token: str) -> str:
        """Extract chatgpt_account_id from JWT claims."""
        payload = self._decode_jwt_payload(access_token)
        auth_claims = payload.get("https://api.openai.com/auth", {})
        account_id = auth_claims.get("chatgpt_account_id")
        if not account_id:
            raise ValueError(
                "Could not extract chatgpt_account_id from access_token JWT. "
                "Provide account_id in the auth file."
            )
        return account_id

    def _get_token_expiry(self, access_token: str) -> float:
        """Get token expiry timestamp from JWT."""
        try:
            payload = self._decode_jwt_payload(access_token)
            return float(payload.get("exp", 0))
        except Exception:
            return 0

    def _is_token_expired(self) -> bool:
        """Check if the access token is expired or will expire within 5 minutes."""
        return time.time() > (self._token_exp - 300)

    def _refresh_tokens(self) -> None:
        """Refresh the access token using the refresh token."""
        logger.info("Refreshing ChatGPT OAuth token...")
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.CLIENT_ID,
        }).encode()

        req = urllib.request.Request(
            self.TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            import urllib.parse
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())

            self.access_token = result["access_token"]
            self.refresh_token = result["refresh_token"]
            self._token_exp = time.time() + result.get("expires_in", 3600)

            # Persist refreshed tokens
            auth_data = {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "account_id": self.account_id,
            }
            with open(self.auth_path, "w") as f:
                json.dump(auth_data, f, indent=2)

            logger.info("Token refreshed successfully")
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise ChatGPTAPIError(f"Token refresh failed: {e}") from e

    def _ensure_valid_token(self) -> str:
        """Ensure we have a valid access token, refreshing if needed."""
        if self._is_token_expired():
            self._refresh_tokens()
        return self.access_token

    def _parse_sse_response(self, raw: str) -> dict:
        """Parse SSE stream to extract the final response.done event."""
        for line in raw.split("\n"):
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    if data.get("type") in ("response.done", "response.completed"):
                        return data.get("response", data)
                except json.JSONDecodeError:
                    continue

        # Fallback: try parsing the whole thing as JSON
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise ChatGPTAPIError(f"Could not parse API response: {raw[:500]}")

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> tuple[str, int, int]:
        """Generate a response using the ChatGPT backend API."""
        import urllib.parse

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                token = self._ensure_valid_token()

                body = {
                    "model": self.model_name,
                    "instructions": "You are a Lean 4 theorem prover. Return only valid Lean 4 code.",
                    "input": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": prompt}
                            ],
                        }
                    ],
                    "store": False,
                    "stream": True,
                    "reasoning": {"effort": self.reasoning_effort},
                }

                payload = json.dumps(body).encode()

                req = urllib.request.Request(
                    self.CODEX_BASE_URL,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token}",
                        "chatgpt-account-id": self.account_id,
                        "OpenAI-Beta": "responses=experimental",
                        "originator": "codex_cli_rs",
                    },
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=120) as resp:
                    raw = resp.read().decode()

                # Parse response — could be JSON or SSE
                if raw.startswith("data: ") or "event:" in raw[:100]:
                    response_data = self._parse_sse_response(raw)
                else:
                    response_data = json.loads(raw)

                # Extract text from Responses API format
                text = ""
                output = response_data.get("output", [])
                for item in output:
                    if item.get("type") == "message":
                        for content in item.get("content", []):
                            if content.get("type") == "output_text":
                                text += content.get("text", "")

                # If output format is different, try direct text field
                if not text:
                    text = response_data.get("text", "")
                if not text and isinstance(output, str):
                    text = output

                # Extract token usage
                usage = response_data.get("usage", {})
                input_tokens = usage.get("input_tokens", len(prompt) // 4)
                output_tokens = usage.get("output_tokens", len(text) // 4)

                logger.debug(
                    f"Generated {output_tokens} tokens "
                    f"(input: {input_tokens}, reasoning_effort: {self.reasoning_effort})"
                )

                return text, input_tokens, output_tokens

            except urllib.error.HTTPError as e:
                last_error = e
                status = e.code
                error_body = ""
                try:
                    error_body = e.read().decode()
                except Exception:
                    pass

                logger.warning(
                    f"ChatGPT API error {status} on attempt {attempt + 1}/{self.max_retries + 1}: "
                    f"{error_body[:300]}"
                )

                # 401 = token expired, try refresh
                if status == 401 and attempt < self.max_retries:
                    self._token_exp = 0  # force refresh
                    continue

                # 429 = rate limit, retry with backoff
                if status == 429 and attempt < self.max_retries:
                    delay = min(self.BASE_DELAY * (2 ** attempt), self.MAX_DELAY)
                    logger.info(f"Rate limited, waiting {delay:.1f}s")
                    time.sleep(delay)
                    continue

                # 404 with usage_limit = treat as rate limit
                if status == 404 and "usage_limit" in error_body.lower():
                    if attempt < self.max_retries:
                        delay = min(self.BASE_DELAY * (2 ** attempt), self.MAX_DELAY)
                        logger.info(f"Usage limit hit, waiting {delay:.1f}s")
                        time.sleep(delay)
                        continue

                # 400 = bad request, don't retry
                if status == 400:
                    break

                break

            except Exception as e:
                last_error = e
                logger.warning(
                    f"ChatGPT API error on attempt {attempt + 1}/{self.max_retries + 1}: {e}"
                )
                if attempt < self.max_retries:
                    delay = min(self.BASE_DELAY * (2 ** attempt), self.MAX_DELAY)
                    time.sleep(delay)
                    continue
                break

        raise ChatGPTAPIError(
            f"ChatGPT generation failed after {self.max_retries + 1} attempts: {last_error}",
            status_code=getattr(last_error, "code", None),
        ) from last_error

    def __repr__(self) -> str:
        return f"ChatGPTProvider(model={self.model_name}, reasoning_effort={self.reasoning_effort})"
