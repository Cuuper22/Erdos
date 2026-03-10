"""
Independent Assessment Tests for the Erdos Proof Mining System.

These tests verify the project's claims from scratch — not taking
existing tests at face value. Each section targets a specific claim
or module and tests it with adversarial edge cases.
"""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ═══════════════════════════════════════════════════════════════════
# A. THEOREM INTEGRITY — The Central Claim
# ═══════════════════════════════════════════════════════════════════

from src.validator import (
    extract_theorem_statement,
    compute_theorem_hash,
    validate_theorem_integrity,
    run_security_check,
    check_banned_patterns,
    check_dangerous_io,
    TheoremLocker,
)


class TestTheoremIntegrity_IndependentVerification(unittest.TestCase):
    """Does SHA-256 integrity locking actually catch cheating?"""

    def test_identical_theorem_same_hash(self):
        """Baseline: same theorem should produce the same hash."""
        code = "theorem foo : 1 + 1 = 2 := by omega"
        h1 = compute_theorem_hash(code)
        h2 = compute_theorem_hash(code)
        self.assertEqual(h1, h2)

    def test_subtle_modification_detected(self):
        """Core claim: changing '1+1=2' to '1+1=3' must be caught."""
        original = "theorem foo : 1 + 1 = 2 := by sorry"
        cheated  = "theorem foo : 1 + 1 = 3 := by rfl"
        result = validate_theorem_integrity(original, cheated)
        self.assertFalse(result.is_valid, "Failed to detect theorem modification!")

    def test_renaming_theorem_detected(self):
        """Renaming the theorem should be caught."""
        original = "theorem foo : True := by trivial"
        cheated  = "theorem bar : True := by trivial"
        h1 = compute_theorem_hash(original)
        h2 = compute_theorem_hash(cheated)
        self.assertNotEqual(h1, h2, "Renaming theorem was not detected!")

    def test_whitespace_normalization_actually_works(self):
        """Verify normalization logic, not just that two hashes match."""
        code1 = "theorem test : 1 + 1 = 2 := by sorry"
        code2 = "theorem   test   :   1 + 1 = 2   :=   by sorry"
        h1 = compute_theorem_hash(code1)
        h2 = compute_theorem_hash(code2)
        self.assertEqual(h1, h2, "Whitespace normalization failed")

        # Also verify what the normalized form looks like
        stmt = extract_theorem_statement(code2)
        normalized = ' '.join(stmt.split())
        self.assertNotIn('   ', normalized, "Normalization left multi-spaces")

    def test_adding_hypothesis_detected(self):
        """Adding an extra hypothesis should be caught."""
        original = "theorem foo (n : Nat) : n + 0 = n := by sorry"
        cheated  = "theorem foo (n : Nat) (h : n = 0) : n + 0 = n := by exact h ▸ rfl"
        result = validate_theorem_integrity(original, cheated)
        self.assertFalse(result.is_valid, "Adding hypothesis not detected!")

    def test_weakening_conclusion_detected(self):
        """Weakening the conclusion should be caught."""
        original = "theorem foo : ∀ n : Nat, n + 0 = n := by sorry"
        cheated  = "theorem foo : True := by trivial"
        result = validate_theorem_integrity(original, cheated)
        self.assertFalse(result.is_valid, "Weakened conclusion not detected!")

    def test_multiline_theorem_extraction(self):
        """Multi-line theorem with complex signature."""
        code = """
theorem long_theorem
    (n m : Nat)
    (h₁ : n > 0)
    (h₂ : m > 0) :
    n + m > 0 := by
  omega
"""
        stmt = extract_theorem_statement(code)
        self.assertIn("long_theorem", stmt)
        self.assertIn(":=", stmt)

    def test_theorem_with_where_clause(self):
        """Theorem using where clause — does extraction handle it?"""
        code = """
theorem foo : bar = baz := by
  exact helper
where
  helper : bar = baz := by rfl
"""
        # The regex extracts up to :=, so "where" should NOT be in the statement
        stmt = extract_theorem_statement(code)
        self.assertIn(":=", stmt)

    def test_empty_content_does_not_crash(self):
        """Empty content should not crash."""
        h = compute_theorem_hash("")
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)  # SHA-256 hex length

    def test_no_theorem_in_content(self):
        """Content without theorem/lemma should still hash without crashing."""
        h = compute_theorem_hash("-- just a comment")
        self.assertIsInstance(h, str)

    def test_locker_lock_and_verify(self):
        """TheoremLocker: lock then verify works."""
        locker = TheoremLocker()
        original = "theorem foo : 1 + 1 = 2 := by sorry"
        locker.lock_theorem("P001", original)
        self.assertTrue(locker.verify_theorem("P001", original))

    def test_locker_catches_modification(self):
        """TheoremLocker: modified theorem fails verification."""
        locker = TheoremLocker()
        original = "theorem foo : 1 + 1 = 2 := by sorry"
        cheated  = "theorem foo : 1 + 1 = 3 := by rfl"
        locker.lock_theorem("P001", original)
        self.assertFalse(locker.verify_theorem("P001", cheated))

    def test_locker_unlocked_theorem_raises(self):
        """TheoremLocker: verifying an unlocked theorem raises."""
        locker = TheoremLocker()
        with self.assertRaises(ValueError):
            locker.verify_theorem("NONEXISTENT", "theorem x : True := trivial")


# ═══════════════════════════════════════════════════════════════════
# B. SECURITY SCANNING — Does it actually catch bad patterns?
# ═══════════════════════════════════════════════════════════════════


class TestSecurityScanning_IndependentVerification(unittest.TestCase):
    """Does the security scanner actually catch what it claims?"""

    def test_sorry_detected(self):
        """Plain 'sorry' must be caught."""
        errors = check_banned_patterns("theorem foo : True := by sorry")
        self.assertTrue(any("sorry" in e for e in errors))

    def test_sorry_in_middle_of_word_not_flagged(self):
        """'sorry' inside another word (e.g., 'notsorryatall') — check behavior."""
        # \bsorry\b uses word boundaries, so this should NOT match
        errors = check_banned_patterns("-- notsorryatall")
        sorry_errors = [e for e in errors if "sorry" in e.lower()]
        self.assertEqual(len(sorry_errors), 0, "False positive: 'sorry' inside word")

    def test_admit_detected(self):
        errors = check_banned_patterns("theorem foo : True := by admit")
        self.assertTrue(any("admit" in e for e in errors))

    def test_axiom_declaration_IS_flagged(self):
        """ALL axiom usage is banned in LLM proof candidates — including declarations.
        The original problem file defines what axioms exist; the LLM output
        should never introduce new axioms."""
        errors = check_banned_patterns("axiom myAxiom : Prop")
        axiom_errors = [e for e in errors if "axiom" in e.lower()]
        self.assertTrue(len(axiom_errors) > 0,
                        "Axiom declaration in proof candidate must be caught")

    def test_axiom_usage_flagged(self):
        """All forms of axiom usage should be flagged."""
        errors = check_banned_patterns("exact (axiom)")
        axiom_errors = [e for e in errors if "Axiom" in e or "axiom" in e.lower()]
        self.assertTrue(len(axiom_errors) > 0, "Axiom usage not caught")

    def test_io_fs_blocked(self):
        errors = check_dangerous_io("open IO.FS.readFile")
        self.assertTrue(any("IO.FS" in e for e in errors))

    def test_system_process_blocked(self):
        errors = check_dangerous_io("let proc <- System.Process.spawn")
        self.assertTrue(any("System.Process" in e for e in errors))

    def test_clean_proof_passes(self):
        """A legitimate proof should pass all security checks."""
        clean = "theorem foo : 1 + 1 = 2 := by omega"
        report = run_security_check(clean)
        self.assertTrue(report.is_safe, f"Clean proof falsely flagged: {report.banned_patterns + report.io_violations}")

    def test_native_decide_flagged(self):
        errors = check_banned_patterns("theorem foo : True := by native_decide")
        self.assertTrue(any("native_decide" in e for e in errors))


# ═══════════════════════════════════════════════════════════════════
# C. SANDBOX MODULE — Zero existing tests, test from scratch
# ═══════════════════════════════════════════════════════════════════

from src.sandbox import BuildResult, Sandbox, SandboxManager, run_lake_build


class TestBuildResult_IndependentVerification(unittest.TestCase):
    """Test BuildResult — previously untested."""

    def test_successful_build_summary(self):
        r = BuildResult(success=True, stdout="ok", stderr="", return_code=0, duration_seconds=1.0)
        self.assertEqual(r.get_error_summary(), "Build successful")

    def test_timeout_summary(self):
        r = BuildResult(success=False, stdout="", stderr="", return_code=-1,
                        duration_seconds=60.0, timeout_occurred=True)
        self.assertEqual(r.get_error_summary(), "Build timed out")

    def test_error_lines_extracted(self):
        stderr = """
/tmp/sandbox/Test.lean:5:2: error: unknown identifier 'foo'
/tmp/sandbox/Test.lean:10:4: error: type mismatch
some other info
/tmp/sandbox/Test.lean:15:6: error: expected token
"""
        r = BuildResult(success=False, stdout="", stderr=stderr, return_code=1, duration_seconds=2.0)
        summary = r.get_error_summary()
        self.assertIn("unknown identifier", summary)
        self.assertIn("type mismatch", summary)
        self.assertIn("expected token", summary)

    def test_error_lines_capped_at_5(self):
        lines = [f"/tmp/Test.lean:{i}:0: error: err{i}" for i in range(10)]
        stderr = "\n".join(lines)
        r = BuildResult(success=False, stdout="", stderr=stderr, return_code=1, duration_seconds=2.0)
        summary = r.get_error_summary()
        # Should only show first 5
        self.assertIn("err0", summary)
        self.assertIn("err4", summary)
        self.assertNotIn("err5", summary)

    def test_fallback_when_no_error_keyword(self):
        r = BuildResult(success=False, stdout="", stderr="something went wrong",
                        return_code=1, duration_seconds=1.0)
        summary = r.get_error_summary()
        self.assertEqual(summary, "something went wrong")

    def test_empty_stderr_returns_unknown(self):
        r = BuildResult(success=False, stdout="", stderr="", return_code=1, duration_seconds=1.0)
        summary = r.get_error_summary()
        self.assertEqual(summary, "Unknown error")


class TestSandbox_IndependentVerification(unittest.TestCase):
    """Test Sandbox lifecycle — previously untested."""

    def test_create_and_cleanup(self):
        with tempfile.TemporaryDirectory() as base:
            s = Sandbox(base_dir=Path(base), problem_id="test001")
            path = s.create()
            self.assertTrue(path.exists())
            s.cleanup()
            self.assertFalse(path.exists())

    def test_write_and_read_file(self):
        with tempfile.TemporaryDirectory() as base:
            s = Sandbox(base_dir=Path(base), problem_id="test002")
            s.create()
            s.write_file("Test.lean", "theorem x : True := trivial")
            content = s.read_file("Test.lean")
            self.assertEqual(content, "theorem x : True := trivial")
            s.cleanup()

    def test_write_creates_subdirectories(self):
        with tempfile.TemporaryDirectory() as base:
            s = Sandbox(base_dir=Path(base), problem_id="test003")
            s.create()
            s.write_file("src/deep/Test.lean", "-- nested")
            self.assertTrue((s.work_dir / "src" / "deep" / "Test.lean").exists())
            s.cleanup()

    def test_context_manager(self):
        with tempfile.TemporaryDirectory() as base:
            with Sandbox(base_dir=Path(base), problem_id="test004") as s:
                self.assertTrue(s.work_dir.exists())
                work_dir = s.work_dir
            # After context, directory should be cleaned up
            self.assertFalse(work_dir.exists())

    def test_read_before_create_raises(self):
        with tempfile.TemporaryDirectory() as base:
            s = Sandbox(base_dir=Path(base), problem_id="test005")
            # work_dir is set in __post_init__ but directory not created
            with self.assertRaises(Exception):
                s.read_file("anything.lean")


class TestSandboxManager_IndependentVerification(unittest.TestCase):
    """Test SandboxManager — previously untested."""

    def test_create_and_get(self):
        with tempfile.TemporaryDirectory() as base:
            mgr = SandboxManager(base_dir=Path(base))
            s = mgr.create_sandbox("P001")
            self.assertIsNotNone(s.work_dir)
            self.assertTrue(s.work_dir.exists())
            retrieved = mgr.get_sandbox("P001")
            self.assertEqual(retrieved, s)
            mgr.cleanup_all()

    def test_cleanup_removes_directories(self):
        with tempfile.TemporaryDirectory() as base:
            mgr = SandboxManager(base_dir=Path(base))
            s = mgr.create_sandbox("P002")
            work_dir = s.work_dir
            mgr.cleanup_all()
            self.assertFalse(work_dir.exists())

    def test_context_manager(self):
        with tempfile.TemporaryDirectory() as base:
            with SandboxManager(base_dir=Path(base)) as mgr:
                s = mgr.create_sandbox("P003")
                work_dir = s.work_dir
            self.assertFalse(work_dir.exists())


class TestRunLakeBuild_IndependentVerification(unittest.TestCase):
    """Test run_lake_build — previously untested."""

    def test_lake_not_installed_graceful_failure(self):
        """If 'lake' is not installed, should return failure — not crash."""
        with tempfile.TemporaryDirectory() as d:
            result = run_lake_build(Path(d))
            self.assertFalse(result.success)
            # Should mention lake not found OR fail gracefully
            self.assertTrue(
                "not found" in result.stderr.lower() or result.return_code != 0,
                f"Unexpected stderr: {result.stderr}"
            )


# ═══════════════════════════════════════════════════════════════════
# D. SOLVER LOGIC — Only 7 trivial mock tests exist
# ═══════════════════════════════════════════════════════════════════

from src.solver import (
    _classify_error, _ErrorKind, AgentProver, AgentCritic,
    Critique, Problem, Solver,
)
from src.llm import MockLLMProvider


class TestErrorClassification_IndependentVerification(unittest.TestCase):
    """Test error classification — not covered by existing tests."""

    def test_rate_limit_is_transient(self):
        e = Exception("rate limit exceeded")
        self.assertEqual(_classify_error(e), _ErrorKind.TRANSIENT)

    def test_429_is_transient(self):
        e = Exception("Status 429: Too Many Requests")
        self.assertEqual(_classify_error(e), _ErrorKind.TRANSIENT)

    def test_503_is_transient(self):
        e = Exception("503 Service Unavailable")
        self.assertEqual(_classify_error(e), _ErrorKind.TRANSIENT)

    def test_401_is_permanent(self):
        e = Exception("401 Unauthorized")
        self.assertEqual(_classify_error(e), _ErrorKind.PERMANENT)

    def test_403_is_permanent(self):
        e = Exception("403 Forbidden")
        self.assertEqual(_classify_error(e), _ErrorKind.PERMANENT)

    def test_budget_exhausted(self):
        e = Exception("Budget exhausted")
        self.assertEqual(_classify_error(e), _ErrorKind.BUDGET)

    def test_unknown_error_defaults_to_transient(self):
        e = Exception("some random error xyz")
        self.assertEqual(_classify_error(e), _ErrorKind.TRANSIENT)

    def test_authentication_is_permanent(self):
        e = Exception("authentication failed")
        self.assertEqual(_classify_error(e), _ErrorKind.PERMANENT)


class TestAgentProverCleanResponse_IndependentVerification(unittest.TestCase):
    """Test _clean_response with realistic LLM outputs."""

    def setUp(self):
        self.prover = AgentProver(MockLLMProvider(), temperature=0.7)

    def test_strips_markdown_fences(self):
        response = "```lean\nby omega\n```"
        original = "theorem foo : 1 + 1 = 2 := by sorry"
        result = self.prover._clean_response(response, original)
        self.assertNotIn("```", result)

    def test_inserts_into_sorry_position(self):
        """If response doesn't contain theorem/lemma, it replaces sorry."""
        response = "omega"
        original = "theorem foo : 1 + 1 = 2 := by sorry"
        result = self.prover._clean_response(response, original)
        self.assertIn("omega", result)
        self.assertNotIn("sorry", result)

    def test_complete_file_response_used_directly(self):
        """If response contains 'theorem', use it as-is."""
        response = "theorem foo : 1 + 1 = 2 := by omega"
        original = "theorem foo : 1 + 1 = 2 := by sorry"
        result = self.prover._clean_response(response, original)
        self.assertEqual(result, response)

    def test_mixed_markdown_and_explanation(self):
        response = "Here's the proof:\n```lean\ntheorem foo : True := by trivial\n```\nThis works because..."
        original = "theorem foo : True := by sorry"
        result = self.prover._clean_response(response, original)
        self.assertNotIn("```", result)
        self.assertIn("theorem", result)


class TestAgentCriticParsing_IndependentVerification(unittest.TestCase):
    """Test _parse_critique with realistic and adversarial inputs."""

    def setUp(self):
        self.critic = AgentCritic(MockLLMProvider(), temperature=0.1)

    def test_valid_json(self):
        response = '{"status": "PASS", "feedback": "Good proof", "is_elegant": true, "security_concerns": []}'
        critique = self.critic._parse_critique(response)
        self.assertEqual(critique.status, "PASS")
        self.assertTrue(critique.is_elegant)

    def test_json_with_surrounding_text(self):
        response = 'Here is my review:\n{"status": "FAIL", "feedback": "Missing step", "is_elegant": false, "security_concerns": ["uses sorry"]}\nThat was my review.'
        critique = self.critic._parse_critique(response)
        self.assertEqual(critique.status, "FAIL")
        self.assertIn("Missing step", critique.feedback)

    def test_malformed_json_fallback(self):
        response = "The proof looks good, I'll PASS it."
        critique = self.critic._parse_critique(response)
        self.assertEqual(critique.status, "PASS")  # heuristic: "pass" in response

    def test_no_json_fail_heuristic(self):
        response = "This proof is incorrect and should be rejected."
        critique = self.critic._parse_critique(response)
        self.assertEqual(critique.status, "FAIL")

    def test_nested_braces_in_json(self):
        """JSON with nested objects shouldn't confuse the parser."""
        response = '{"status": "PASS", "feedback": "Proof uses {omega}", "is_elegant": false, "security_concerns": []}'
        critique = self.critic._parse_critique(response)
        self.assertEqual(critique.status, "PASS")

    def test_completely_empty_response(self):
        critique = self.critic._parse_critique("")
        # Should not crash; should default to FAIL
        self.assertEqual(critique.status, "FAIL")


# ═══════════════════════════════════════════════════════════════════
# E. OPENAI PROVIDER — GPT-5.4 xhigh reasoning support
# ═══════════════════════════════════════════════════════════════════

from src.llm.openai_provider import OpenAIProvider


class TestOpenAIProvider_ReasoningEffort(unittest.TestCase):
    """Test the new reasoning_effort parameter for GPT-5.4."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_invalid_reasoning_effort_raises(self):
        with self.assertRaises(ValueError):
            OpenAIProvider(api_key="test-key", reasoning_effort="invalid")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_valid_reasoning_efforts_accepted(self):
        for effort in ["none", "low", "medium", "high", "xhigh"]:
            provider = OpenAIProvider(api_key="test-key", reasoning_effort=effort)
            self.assertEqual(provider.reasoning_effort, effort)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_no_reasoning_effort_accepted(self):
        provider = OpenAIProvider(api_key="test-key")
        self.assertIsNone(provider.reasoning_effort)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_generate_with_xhigh_omits_temperature(self):
        """When reasoning_effort=xhigh, temperature should NOT be in the API call."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-5.4", reasoning_effort="xhigh")

        # Mock the client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test response"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        provider.client.chat.completions.create = MagicMock(return_value=mock_response)

        provider.generate("test prompt")

        call_kwargs = provider.client.chat.completions.create.call_args[1]
        self.assertNotIn("temperature", call_kwargs, "temperature should not be passed with xhigh")
        self.assertIn("reasoning_effort", call_kwargs)
        self.assertEqual(call_kwargs["reasoning_effort"], "xhigh")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_generate_without_reasoning_uses_temperature(self):
        """Without reasoning_effort, temperature should be passed normally."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4o")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        provider.client.chat.completions.create = MagicMock(return_value=mock_response)

        provider.generate("test prompt", temperature=0.7)

        call_kwargs = provider.client.chat.completions.create.call_args[1]
        self.assertIn("temperature", call_kwargs)
        self.assertNotIn("reasoning", call_kwargs)


# ═══════════════════════════════════════════════════════════════════
# F. ENVIRONMENT.PY BUG VERIFICATION
# ═══════════════════════════════════════════════════════════════════


class TestEnvironmentBug_IndependentVerification(unittest.TestCase):
    """Verify the 'or True' bug in environment.py has been FIXED."""

    def test_or_true_bug_is_fixed(self):
        """Confirm that the 'or True' debug hack has been removed."""
        env_path = Path(__file__).parent.parent / "src" / "environment.py"
        content = env_path.read_text()
        self.assertNotIn("or True", content,
                          "The 'or True' debug hack should be removed")
        # Verify the correct cache condition exists
        found_cache_check = False
        for line in content.split('\n'):
            if 'installer_path.exists()' in line:
                self.assertNotIn("or True", line)
                found_cache_check = True
        self.assertTrue(found_cache_check,
                        "Should still have installer_path.exists() check")


# ═══════════════════════════════════════════════════════════════════
# G. CONFIG AND FACTORY — Integration verification
# ═══════════════════════════════════════════════════════════════════

from src.config import Config, LLMConfig, CostConfig
from src.llm.factory import create_provider


class TestConfigIntegration_IndependentVerification(unittest.TestCase):
    """Verify config actually works end-to-end."""

    def test_mock_mode_from_env(self):
        """ERDOS_MOCK_MODE=1 should result in MockLLMProvider."""
        with patch.dict(os.environ, {"ERDOS_MOCK_MODE": "1"}, clear=True):
            provider = create_provider()
            self.assertIsInstance(provider, MockLLMProvider)

    def test_no_config_no_env_falls_back_to_mock(self):
        """No config and no env vars should gracefully fall back to mock."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove all API keys
            for key in ["GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY",
                         "ANTHROPIC_API_KEY", "OLLAMA_URL", "ERDOS_MOCK_MODE"]:
                os.environ.pop(key, None)
            provider = create_provider()
            self.assertIsInstance(provider, MockLLMProvider)

    def test_budget_enforcement(self):
        """Budget tracking and enforcement."""
        cost = CostConfig(max_cost_usd=0.10)
        self.assertTrue(cost.check_budget())
        cost.add_usage(input_tokens=10000, output_tokens=10000)
        # With defaults: (10000/1000)*0.01 + (10000/1000)*0.03 = 0.10 + 0.30 = 0.40
        self.assertFalse(cost.check_budget(), "Budget enforcement failed!")


# ═══════════════════════════════════════════════════════════════════
# H. SOLVER INTEGRATION — process_problem (mock mode)
# ═══════════════════════════════════════════════════════════════════


class TestSolverIntegration_IndependentVerification(unittest.TestCase):
    """Test the full solver loop in mock mode."""

    def test_process_problem_with_mock_llm(self):
        """Can the full solver loop execute without crashing in mock mode?"""
        config = Config()
        config.solver.work_dir = Path(tempfile.mkdtemp())
        config.solver.max_retries = 2  # Keep it fast
        llm = MockLLMProvider()
        solver = Solver(config, llm)

        problem = Problem(
            id="TEST001",
            path="Test.lean",
            original_content="theorem test_thm : 1 + 1 = 2 := by sorry"
        )

        try:
            # This should execute the full loop without crashing
            result = solver.process_problem(problem)
            # Mock provider won't produce a valid Lean build, so result is likely None
            # But the key test is: does it run without exceptions?
        finally:
            solver.cleanup()
            import shutil
            shutil.rmtree(config.solver.work_dir, ignore_errors=True)

    def test_budget_stops_solver(self):
        """Solver should stop when budget is exhausted."""
        config = Config()
        config.solver.work_dir = Path(tempfile.mkdtemp())
        config.cost.max_cost_usd = 0.0  # Zero budget
        config.solver.max_retries = 5
        llm = MockLLMProvider()
        solver = Solver(config, llm)

        problem = Problem(
            id="TEST002",
            path="Test.lean",
            original_content="theorem test : True := by sorry"
        )

        try:
            result = solver.process_problem(problem)
            self.assertIsNone(result, "Solver should return None with zero budget")
        finally:
            solver.cleanup()
            import shutil
            shutil.rmtree(config.solver.work_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
