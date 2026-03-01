"""
Tests for the config module.
"""

import os
import json
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from src.config import Config, LLMConfig, CostConfig, SolverConfig


class TestConfigFromEnv(unittest.TestCase):
    """Test configuration loading from environment variables."""

    # Keys that must be preserved for Path.home() and OS functionality
    _SYSTEM_KEYS = {"HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}

    def setUp(self):
        """Save original environment."""
        self.original_env = os.environ.copy()

    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)

    def _clean_env(self):
        """Clear env but preserve system-critical keys."""
        saved = {k: os.environ[k] for k in self._SYSTEM_KEYS if k in os.environ}
        os.environ.clear()
        os.environ.update(saved)
    
    def test_loads_google_api_key(self):
        """Test that GOOGLE_API_KEY is detected."""
        self._clean_env()
        os.environ["GOOGLE_API_KEY"] = "test_key_123"
        
        config = Config.from_env()
        
        self.assertEqual(config.llm.provider, "google")
        self.assertEqual(config.llm.api_key, "test_key_123")
    
    def test_loads_openai_api_key(self):
        """Test that OPENAI_API_KEY is detected."""
        self._clean_env()
        os.environ["OPENAI_API_KEY"] = "sk-test123"
        
        config = Config.from_env()
        
        self.assertEqual(config.llm.provider, "openai")
        self.assertEqual(config.llm.api_key, "sk-test123")
    
    def test_loads_anthropic_api_key(self):
        """Test that ANTHROPIC_API_KEY is detected."""
        self._clean_env()
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test123"
        
        config = Config.from_env()
        
        self.assertEqual(config.llm.provider, "anthropic")
        self.assertEqual(config.llm.api_key, "sk-ant-test123")
    
    def test_loads_max_cost_usd(self):
        """Test that MAX_COST_USD is loaded."""
        self._clean_env()
        os.environ["ERDOS_MOCK_MODE"] = "1"
        os.environ["MAX_COST_USD"] = "10.0"
        
        config = Config.from_env()
        
        self.assertEqual(config.cost.max_cost_usd, 10.0)
    
    def test_loads_max_retries(self):
        """Test that MAX_RETRIES is loaded."""
        self._clean_env()
        os.environ["ERDOS_MOCK_MODE"] = "1"
        os.environ["MAX_RETRIES"] = "20"
        
        config = Config.from_env()
        
        self.assertEqual(config.solver.max_retries, 20)
    
    def test_raises_without_api_key(self):
        """Test that config raises error when no API key is set."""
        self._clean_env()
        
        with self.assertRaises(ValueError) as context:
            Config.from_env()
        
        self.assertIn("API key required", str(context.exception))
    
    def test_allows_mock_mode(self):
        """Test that ERDOS_MOCK_MODE bypasses API key requirement."""
        self._clean_env()
        os.environ["ERDOS_MOCK_MODE"] = "1"
        
        # Should not raise
        config = Config.from_env()
        
        self.assertIsNotNone(config)


class TestCostConfig(unittest.TestCase):
    """Test cost management functionality."""
    
    def test_tracks_spending(self):
        """Test that cost config tracks token usage."""
        cost_config = CostConfig(max_cost_usd=5.0)
        
        # Add some usage
        cost1 = cost_config.add_usage(input_tokens=1000, output_tokens=500)
        
        self.assertGreater(cost1, 0)
        self.assertEqual(cost_config.current_spent, cost1)
        
        # Add more usage
        cost2 = cost_config.add_usage(input_tokens=2000, output_tokens=1000)
        
        self.assertGreater(cost2, 0)
        self.assertEqual(cost_config.current_spent, cost1 + cost2)
    
    def test_enforces_budget(self):
        """Test that budget enforcement works."""
        cost_config = CostConfig(max_cost_usd=0.10)
        
        # Should be within budget initially
        self.assertTrue(cost_config.check_budget())
        
        # Spend the budget
        cost_config.add_usage(input_tokens=10000, output_tokens=5000)
        
        # Should be over budget now
        self.assertFalse(cost_config.check_budget())
    
    def test_remaining_budget(self):
        """Test remaining budget calculation."""
        cost_config = CostConfig(max_cost_usd=1.0)
        
        initial_remaining = cost_config.remaining_budget()
        self.assertEqual(initial_remaining, 1.0)
        
        # Spend some budget
        cost_config.add_usage(input_tokens=1000, output_tokens=500)
        
        remaining = cost_config.remaining_budget()
        self.assertLess(remaining, 1.0)
        self.assertGreaterEqual(remaining, 0.0)
    
    def test_computes_cost_correctly(self):
        """Test that cost computation is accurate."""
        cost_config = CostConfig(
            cost_per_1k_input_tokens=0.01,
            cost_per_1k_output_tokens=0.03
        )
        
        # 1000 input + 1000 output should cost 0.01 + 0.03 = 0.04
        cost = cost_config.add_usage(input_tokens=1000, output_tokens=1000)
        
        self.assertAlmostEqual(cost, 0.04, places=5)


class TestConfigSaveLoad(unittest.TestCase):
    """Test configuration save/load round-trip."""
    
    def test_json_round_trip(self):
        """Test that config can be saved and loaded from JSON."""
        # Create a config
        config = Config()
        config.llm.provider = "google"
        config.llm.model = "gemini-2.0-flash"
        config.llm.temperature_prover = 0.8
        config.cost.max_cost_usd = 10.0
        config.solver.max_retries = 15
        
        # Save to temp file
        with NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
            config.save(temp_path)
        
        try:
            # Load from file
            loaded_config = Config.from_file(temp_path)
            
            # Verify values
            self.assertEqual(loaded_config.llm.provider, "google")
            self.assertEqual(loaded_config.llm.model, "gemini-2.0-flash")
            self.assertEqual(loaded_config.llm.temperature_prover, 0.8)
            self.assertEqual(loaded_config.cost.max_cost_usd, 10.0)
            self.assertEqual(loaded_config.solver.max_retries, 15)
        finally:
            # Clean up
            temp_path.unlink()
    
    def test_to_dict(self):
        """Test that to_dict produces valid structure."""
        config = Config()
        config.llm.provider = "google"
        config.llm.model = "gemini-2.0-flash"
        
        config_dict = config.to_dict()
        
        # Verify structure
        self.assertIn("llm", config_dict)
        self.assertIn("cost", config_dict)
        self.assertIn("solver", config_dict)
        
        self.assertEqual(config_dict["llm"]["provider"], "google")
        self.assertEqual(config_dict["llm"]["model"], "gemini-2.0-flash")


if __name__ == '__main__':
    unittest.main()
