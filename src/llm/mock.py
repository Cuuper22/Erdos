"""Mock LLM provider for testing."""

from .base import LLMProvider


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""
    
    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> tuple[str, int, int]:
        """Return a mock response."""
        # Simple mock that tries to generate a basic proof
        if "sorry" in prompt.lower():
            return "-- Mock proof generated\nby simp", 100, 20
        return "-- No proof generated", 50, 10
