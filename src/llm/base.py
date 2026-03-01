"""Base LLM provider interface."""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> tuple[str, int, int]:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The prompt to send to the LLM
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        
        Returns:
            Tuple of (response_text, input_tokens, output_tokens)
        """
        pass
