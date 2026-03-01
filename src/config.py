"""
Configuration management for the Erdos Proof Mining System.

This module handles loading, validating, and managing configuration
settings for the proof mining system.
"""

import os
import json
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""
    provider: str = "google"  # "openai", "anthropic", "google", or "ollama"
    api_key: Optional[str] = None
    model: str = "gemini-3-flash"
    temperature_prover: float = 0.7
    temperature_critic: float = 0.1
    ollama_url: str = "http://localhost:11434"
    
    def validate(self) -> bool:
        """Validate the LLM configuration."""
        if self.provider in ["openai", "anthropic", "google"]:
            if not self.api_key:
                raise ValueError(f"API key required for {self.provider}")
        return True


@dataclass
class CostConfig:
    """Configuration for cost management."""
    max_cost_usd: float = 5.0
    cost_per_1k_input_tokens: float = 0.01
    cost_per_1k_output_tokens: float = 0.03
    current_spent: float = 0.0
    
    def add_usage(self, input_tokens: int, output_tokens: int) -> float:
        """Add token usage and return the cost."""
        cost = (
            (input_tokens / 1000) * self.cost_per_1k_input_tokens +
            (output_tokens / 1000) * self.cost_per_1k_output_tokens
        )
        self.current_spent += cost
        return cost
    
    def check_budget(self) -> bool:
        """Check if we're still within budget."""
        return self.current_spent < self.max_cost_usd
    
    def remaining_budget(self) -> float:
        """Return remaining budget in USD."""
        return max(0, self.max_cost_usd - self.current_spent)


@dataclass
class SolverConfig:
    """Configuration for the solver loop."""
    max_retries: int = 10
    build_timeout_seconds: int = 60
    work_dir: Path = field(default_factory=lambda: Path.home() / ".erdos-prover" / "work")
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".erdos-prover" / "cache")
    
    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class Config:
    """Main configuration container."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    solver: SolverConfig = field(default_factory=SolverConfig)
    manifest_url: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        config = cls()
        
        # LLM configuration
        if os.environ.get("GOOGLE_API_KEY"):
            config.llm.provider = "google"
            config.llm.api_key = os.environ["GOOGLE_API_KEY"]
            config.llm.model = os.environ.get("LLM_MODEL", "gemini-3-flash")
        elif os.environ.get("OPENAI_API_KEY"):
            config.llm.provider = "openai"
            config.llm.api_key = os.environ["OPENAI_API_KEY"]
        elif os.environ.get("ANTHROPIC_API_KEY"):
            config.llm.provider = "anthropic"
            config.llm.api_key = os.environ["ANTHROPIC_API_KEY"]
        elif os.environ.get("OLLAMA_URL"):
            config.llm.provider = "ollama"
            config.llm.ollama_url = os.environ["OLLAMA_URL"]
        
        if os.environ.get("LLM_MODEL"):
            config.llm.model = os.environ["LLM_MODEL"]
        
        # Cost configuration
        if os.environ.get("MAX_COST_USD"):
            config.cost.max_cost_usd = float(os.environ["MAX_COST_USD"])
        
        # Solver configuration
        if os.environ.get("MAX_RETRIES"):
            config.solver.max_retries = int(os.environ["MAX_RETRIES"])
        
        if os.environ.get("BUILD_TIMEOUT"):
            config.solver.build_timeout_seconds = int(os.environ["BUILD_TIMEOUT"])
        
        # Manifest URL
        if os.environ.get("MANIFEST_URL"):
            config.manifest_url = os.environ["MANIFEST_URL"]
        
        # Early validation - check if API key is set when not using mock
        if config.llm.provider in ["openai", "anthropic", "google"] and not config.llm.api_key:
            # Check if we're in testing/mock mode
            if not os.environ.get("ERDOS_MOCK_MODE"):
                raise ValueError(
                    f"API key required for {config.llm.provider} provider. "
                    f"Set {config.llm.provider.upper()}_API_KEY environment variable or ERDOS_MOCK_MODE=1 for testing."
                )
        
        return config
    
    @classmethod
    def from_file(cls, path: Path) -> "Config":
        """Load configuration from a JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        
        config = cls()
        
        if "llm" in data:
            llm_data = data["llm"]
            config.llm.provider = llm_data.get("provider", config.llm.provider)
            config.llm.api_key = llm_data.get("api_key", config.llm.api_key)
            config.llm.model = llm_data.get("model", config.llm.model)
            config.llm.temperature_prover = llm_data.get("temperature_prover", config.llm.temperature_prover)
            config.llm.temperature_critic = llm_data.get("temperature_critic", config.llm.temperature_critic)
            config.llm.ollama_url = llm_data.get("ollama_url", config.llm.ollama_url)
        
        if "cost" in data:
            cost_data = data["cost"]
            config.cost.max_cost_usd = cost_data.get("max_cost_usd", config.cost.max_cost_usd)
        
        if "solver" in data:
            solver_data = data["solver"]
            config.solver.max_retries = solver_data.get("max_retries", config.solver.max_retries)
            config.solver.build_timeout_seconds = solver_data.get("build_timeout_seconds", config.solver.build_timeout_seconds)
            if "work_dir" in solver_data:
                config.solver.work_dir = Path(solver_data["work_dir"])
            if "cache_dir" in solver_data:
                config.solver.cache_dir = Path(solver_data["cache_dir"])
        
        config.manifest_url = data.get("manifest_url", config.manifest_url)
        
        return config
    
    def to_dict(self) -> dict:
        """Convert configuration to a dictionary."""
        return {
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "temperature_prover": self.llm.temperature_prover,
                "temperature_critic": self.llm.temperature_critic,
                "ollama_url": self.llm.ollama_url,
            },
            "cost": {
                "max_cost_usd": self.cost.max_cost_usd,
            },
            "solver": {
                "max_retries": self.solver.max_retries,
                "build_timeout_seconds": self.solver.build_timeout_seconds,
                "work_dir": str(self.solver.work_dir),
                "cache_dir": str(self.solver.cache_dir),
            },
            "manifest_url": self.manifest_url,
        }
    
    def save(self, path: Path) -> None:
        """Save configuration to a JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
