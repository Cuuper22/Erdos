"""Gemini LLM provider using Google's official generative AI SDK.

This is a replacement for the REST-based GoogleProvider that uses
the official google-generativeai SDK for better reliability and features.
"""

import os
import logging
from typing import Optional

from .base import LLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """
    LLM provider using Google's Gemini models via official SDK.
    
    This provider uses the google-generativeai package which provides:
    - Better error handling and retries
    - Automatic token counting
    - Support for latest Gemini features
    - More robust API interactions
    
    Replaces the REST-based GoogleProvider for production use.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash"
    ):
        """
        Initialize the Gemini provider.
        
        Args:
            api_key: Google AI API key (defaults to GEMINI_API_KEY or GOOGLE_API_KEY env var)
            model: Model name to use (default: gemini-2.0-flash)
        """
        try:
            import google.generativeai as genai
            self._genai = genai
        except ImportError:
            raise ImportError(
                "google-generativeai package not installed. "
                "Install it with: pip install google-generativeai"
            )
        
        # Get API key (check both GEMINI_API_KEY and GOOGLE_API_KEY for compatibility)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key not provided. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        # Configure the SDK
        self._genai.configure(api_key=self.api_key)
        
        # Initialize model
        self.model_name = model
        try:
            self.model = self._genai.GenerativeModel(model)
            logger.info(f"Initialized Gemini provider with model: {model}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model {model}: {e}")
            raise
    
    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> tuple[str, int, int]:
        """
        Generate a response using Gemini.
        
        Args:
            prompt: The prompt to send
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response
        
        Returns:
            Tuple of (response_text, input_tokens, output_tokens)
        """
        try:
            # Configure generation parameters
            generation_config = self._genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            # Generate response
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # Extract text
            response_text = response.text if hasattr(response, 'text') else ""
            
            # Extract token counts from usage metadata
            # Gemini API provides usage_metadata with prompt_token_count and candidates_token_count
            input_tokens = 0
            output_tokens = 0
            
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                input_tokens = getattr(usage, 'prompt_token_count', 0)
                output_tokens = getattr(usage, 'candidates_token_count', 0)
            
            # Fallback: estimate tokens if not provided
            if input_tokens == 0:
                input_tokens = len(prompt) // 4  # Rough estimate
            if output_tokens == 0:
                output_tokens = len(response_text) // 4  # Rough estimate
            
            logger.debug(
                f"Generated {output_tokens} tokens "
                f"(input: {input_tokens}, temp: {temperature})"
            )
            
            return response_text, input_tokens, output_tokens
        
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            # Return error as text for graceful degradation
            return f"-- Generation error: {str(e)}", 0, 0
    
    def __repr__(self) -> str:
        """String representation."""
        return f"GeminiProvider(model={self.model_name})"


# Alias for backward compatibility with existing code that uses GoogleProvider
GoogleProvider = GeminiProvider
