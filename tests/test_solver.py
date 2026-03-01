"""
Comprehensive tests for the solver module.
"""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from src.solver import (
    AgentProver,
    AgentCritic,
    Solver,
    Problem,
    Critique,
    ProofArtifact,
    load_manifest
)
from src.config import Config
from src.llm import MockLLMProvider


class TestAgentProver(unittest.TestCase):
    """Test the AgentProver class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.llm = MockLLMProvider()
        self.prover = AgentProver(self.llm, temperature=0.7)
    
    def test_prover_initialization(self):
        """Test that prover initializes correctly."""
        self.assertIsNotNone(self.prover.llm)
        self.assertEqual(self.prover.temperature, 0.7)
    
    def test_generate_basic_proof(self):
        """Test basic proof generation."""
        problem_content = "theorem test : 1 + 1 = 2 := by sorry"
        
        candidate, in_tokens, out_tokens = self.prover.generate(
            problem_content=problem_content
        )
        
        self.assertIsInstance(candidate, str)
        self.assertTrue(len(candidate) > 0)
        self.assertGreaterEqual(in_tokens, 0)
        self.assertGreaterEqual(out_tokens, 0)
    
    def test_generate_with_instructions(self):
        """Test proof generation with maintainer instructions."""
        problem_content = "theorem test : 1 + 1 = 2 := by sorry"
        instructions = "Use the ring tactic"
        
        candidate, _, _ = self.prover.generate(
            problem_content=problem_content,
            instructions=instructions
        )
        
        self.assertIsInstance(candidate, str)
        self.assertTrue(len(candidate) > 0)


class TestAgentCritic(unittest.TestCase):
    """Test the AgentCritic class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.llm = MockLLMProvider()
        self.critic = AgentCritic(self.llm, temperature=0.1)
    
    def test_critic_initialization(self):
        """Test that critic initializes correctly."""
        self.assertIsNotNone(self.critic.llm)
        self.assertEqual(self.critic.temperature, 0.1)
    
    def test_review_proof(self):
        """Test basic proof review."""
        proof_content = "theorem test : 1 + 1 = 2 := by rfl"
        build_logs = "Build successful"
        
        critique, in_tokens, out_tokens = self.critic.review(
            proof_content=proof_content,
            build_logs=build_logs
        )
        
        self.assertIsInstance(critique, Critique)
        self.assertIn(critique.status, ["PASS", "FAIL"])
        self.assertIsInstance(critique.feedback, str)
        self.assertIsInstance(critique.is_elegant, bool)
        self.assertIsInstance(critique.security_concerns, list)
        self.assertGreaterEqual(in_tokens, 0)
        self.assertGreaterEqual(out_tokens, 0)


class TestProblem(unittest.TestCase):
    """Test the Problem dataclass."""
    
    def test_problem_creation(self):
        """Test creating a Problem instance."""
        problem = Problem(
            id="test_001",
            path="src/test.lean",
            difficulty="Easy",
            maintainer_note="Use ring tactic"
        )
        
        self.assertEqual(problem.id, "test_001")
        self.assertEqual(problem.path, "src/test.lean")
        self.assertEqual(problem.difficulty, "Easy")
        self.assertEqual(problem.maintainer_note, "Use ring tactic")


class TestLoadManifest(unittest.TestCase):
    """Test manifest loading functionality."""
    
    def test_load_valid_manifest(self):
        """Test loading a valid manifest file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("""
            {
                "priority_problems": [
                    {
                        "id": "test_001",
                        "path": "src/test1.lean",
                        "difficulty": "Easy"
                    }
                ]
            }
            """)
            manifest_path = Path(f.name)
        
        try:
            problems = load_manifest(manifest_path)
            self.assertEqual(len(problems), 1)
            self.assertEqual(problems[0].id, "test_001")
        finally:
            manifest_path.unlink()


if __name__ == "__main__":
    unittest.main()
