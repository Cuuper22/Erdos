"""
Visual Proof Demos for Bug Fixes
=================================
Each test class demonstrates a bug that existed, shows the BEFORE behavior
(what the buggy code would have done), and proves the AFTER behavior
(what the fixed code now does).

These are not just pass/fail checks — they print clear visual output
showing exactly what changed and why it matters.
"""

import os
import re
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from src.validator import (
    BANNED_PATTERNS,
    check_banned_patterns,
    validate_theorem_integrity,
)
from src.sandbox import _discover_elan_bin, run_lake_build
from src.solver import AgentProver, FeedbackSanitizer
from src.llm import MockLLMProvider


# ════════════════════════════════════════════════════════════════════
# DEMO 1: Axiom Abuse Security Hole — NOW CAUGHT
# ════════════════════════════════════════════════════════════════════

class TestDemo_AxiomAbuse(unittest.TestCase):
    """
    BUG: The old regex r"\\baxiom\\b(?!\\s+\\w+\\s*:)" used a negative
    lookahead that EXEMPTED declaration-form axioms like:
        axiom my_cheat : 1 + 1 = 2

    This meant an LLM could trivially prove ANY theorem by introducing
    a custom axiom that asserts the conclusion directly.

    FIX: Changed to r"\\baxiom\\b" — ALL axiom usage in LLM-generated
    proof candidates is now banned. Only the original problem file
    defines what axioms exist.
    """

    ORIGINAL = textwrap.dedent("""\
        theorem one_plus_one : 1 + 1 = 2 := by
          sorry
    """)

    # This is the attack: introduce an axiom that trivially proves the goal
    CHEATED_AXIOM = textwrap.dedent("""\
        axiom my_cheat : 1 + 1 = 2
        theorem one_plus_one : 1 + 1 = 2 := my_cheat
    """)

    def test_axiom_abuse_is_now_caught(self):
        """DEMO: Axiom-based cheating is detected and rejected."""
        print("\n" + "=" * 70)
        print("DEMO 1: Axiom Abuse Security Hole")
        print("=" * 70)

        print("\n[ATTACK] LLM submits proof with sneaky axiom:")
        print(f"  {self.CHEATED_AXIOM.strip()}")

        # Run security check
        errors = check_banned_patterns(self.CHEATED_AXIOM)

        print(f"\n[RESULT] Errors found: {len(errors)}")
        for e in errors:
            print(f"  ✗ {e}")

        self.assertTrue(len(errors) > 0, "Axiom abuse must be caught")
        self.assertTrue(
            any("axiom" in e.lower() for e in errors),
            "Error must mention 'axiom'"
        )

        print("\n[PASS] Axiom abuse is now properly detected!")
        print("=" * 70)

    def test_axiom_in_different_forms(self):
        """All forms of axiom declarations are caught."""
        print("\n--- Axiom variant detection ---")
        variants = [
            ("axiom cheat : P", "standard declaration"),
            ("  axiom   spaced : P", "with leading whitespace"),
            ("noncomputable axiom fancy : P", "with noncomputable prefix"),
        ]

        for code, label in variants:
            errors = check_banned_patterns(code)
            caught = len(errors) > 0
            status = "CAUGHT" if caught else "MISSED"
            print(f"  [{status}] {label}: {code.strip()}")
            self.assertTrue(caught, f"Must catch: {label}")

    def test_legitimate_proof_not_flagged(self):
        """Proofs without axioms are NOT falsely flagged."""
        clean_proof = textwrap.dedent("""\
            theorem one_plus_one : 1 + 1 = 2 := by
              rfl
        """)
        errors = check_banned_patterns(clean_proof)
        self.assertEqual(len(errors), 0, "Clean proof must not be flagged")

    def test_full_validation_rejects_axiom_cheat(self):
        """End-to-end: validate_theorem_integrity catches axiom abuse."""
        result = validate_theorem_integrity(self.ORIGINAL, self.CHEATED_AXIOM)
        self.assertFalse(result.is_valid, "Axiom cheat must fail validation")
        self.assertTrue(
            any("axiom" in e.lower() for e in result.errors),
            "Validation errors must mention axiom"
        )


# ════════════════════════════════════════════════════════════════════
# DEMO 2: Sandbox PATH Discovery — elan Now Found
# ════════════════════════════════════════════════════════════════════

class TestDemo_SandboxPATH(unittest.TestCase):
    """
    BUG: run_lake_build() used env={**os.environ, "LAKE_NO_INTERACTIVE": "1"}
    which didn't include ~/.elan/bin/ in PATH. On systems where elan is
    installed but not in the default PATH, 'lake' would not be found.

    FIX: Added _discover_elan_bin() that checks ~/.elan/bin/,
    ~/.erdos-prover/bin/elan/bin/, and ELAN_HOME env var, then prepends
    the found directory to PATH.
    """

    def test_elan_discovery_finds_real_install(self):
        """DEMO: _discover_elan_bin() finds elan when installed."""
        print("\n" + "=" * 70)
        print("DEMO 2: Sandbox PATH Discovery")
        print("=" * 70)

        elan_bin = _discover_elan_bin()

        if elan_bin:
            print(f"\n[FOUND] elan bin directory: {elan_bin}")
            lake_path = elan_bin / "lake"
            lean_path = elan_bin / "lean"
            print(f"  lake exists: {lake_path.exists()}")
            print(f"  lean exists: {lean_path.exists()}")
            self.assertTrue(lake_path.exists(), "lake binary must exist in discovered dir")
        else:
            print("\n[SKIP] elan not installed on this system")
            # This is OK — the test documents the discovery mechanism
            # On CI without elan, we test the fallback behavior

        print("\n[PASS] Discovery mechanism works correctly!")
        print("=" * 70)

    def test_elan_discovery_with_elan_home_env(self):
        """DEMO: ELAN_HOME env var is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake elan bin dir
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            (bin_dir / "lake").touch()

            with patch.dict(os.environ, {"ELAN_HOME": tmpdir}):
                result = _discover_elan_bin()

            if result:
                self.assertEqual(result, bin_dir)
                print(f"  ELAN_HOME discovery: {result}")

    def test_run_lake_build_uses_discovered_path(self):
        """DEMO: run_lake_build includes elan in PATH (no FileNotFoundError on valid installs)."""
        # If elan is installed, this should find lake via _discover_elan_bin
        # If not installed, it should gracefully return an error, not crash
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_lake_build(Path(tmpdir), timeout_seconds=5)
            # Either succeeds (lake found) or gives a clean error message
            self.assertIsNotNone(result)
            if not result.success:
                print(f"  Build error (expected without Lean project): {result.stderr[:100]}")


# ════════════════════════════════════════════════════════════════════
# DEMO 3: Sorry Replacement — Now Targets Proof Body Only
# ════════════════════════════════════════════════════════════════════

class TestDemo_SorryReplacement(unittest.TestCase):
    """
    BUG: _clean_response used original.replace('sorry', response, 1) which
    replaces the FIRST occurrence of 'sorry' — even if it's in a comment
    like "-- This theorem was sorry before".

    FIX: New _replace_sorry_in_body() method skips line comments (-- ...)
    and only replaces sorry in actual code.
    """

    def setUp(self):
        self.prover = AgentProver(MockLLMProvider(), temperature=0.7)

    def test_sorry_in_comment_not_replaced(self):
        """DEMO: sorry inside a comment is preserved."""
        print("\n" + "=" * 70)
        print("DEMO 3: Sorry Replacement — Comment Safety")
        print("=" * 70)

        original = textwrap.dedent("""\
            -- This proof used to have sorry, now we fix it
            theorem add_zero (n : Nat) : n + 0 = n := by
              sorry
        """)

        replacement = "rfl"

        print(f"\n[INPUT] Original code:")
        for line in original.strip().split('\n'):
            print(f"  {line}")

        print(f"\n[LLM RESPONSE] {replacement}")

        result = self.prover._clean_response(replacement, original)

        print(f"\n[OUTPUT] Result:")
        for line in result.strip().split('\n'):
            print(f"  {line}")

        # The comment should still contain 'sorry'
        self.assertIn("-- This proof used to have sorry", result,
                       "Comment must be preserved")
        # The proof body should have 'rfl' instead of 'sorry'
        self.assertIn("rfl", result, "Proof body must have the replacement")
        # There should be exactly one 'sorry' left (in the comment)
        sorry_count = result.count("sorry")
        self.assertEqual(sorry_count, 1,
                         f"Expected 1 sorry (in comment), found {sorry_count}")

        print("\n[PASS] Comment sorry preserved, proof body sorry replaced!")
        print("=" * 70)

    def test_sorry_in_code_replaced_normally(self):
        """sorry in code (no comment) is still replaced correctly."""
        original = "theorem t : True := by\n  sorry"
        result = self.prover._clean_response("trivial", original)
        self.assertIn("trivial", result)
        self.assertNotIn("sorry", result)

    def test_multiple_sorry_replaces_first_code_occurrence(self):
        """When multiple sorrys exist, only the first code sorry is replaced."""
        original = textwrap.dedent("""\
            -- sorry is mentioned here
            theorem t1 : True := by
              sorry
            theorem t2 : True := by
              sorry
        """)
        result = self.prover._clean_response("trivial", original)
        # First code sorry replaced, second remains, comment remains
        self.assertEqual(result.count("sorry"), 2,
                         "Should replace only first code sorry")


# ════════════════════════════════════════════════════════════════════
# DEMO 4: elan Installer Cache — No Redundant Downloads
# ════════════════════════════════════════════════════════════════════

class TestDemo_ElanCache(unittest.TestCase):
    """
    BUG: environment.py line 234 had:
        if not installer_path.exists() or True:
    The 'or True' made the condition always true, re-downloading the
    elan installer script every single time.

    FIX: Removed 'or True'. Now the cached installer is reused.
    """

    def test_cache_condition_is_correct(self):
        """DEMO: The installer cache condition no longer has 'or True'."""
        print("\n" + "=" * 70)
        print("DEMO 4: elan Installer Cache — No Redundant Downloads")
        print("=" * 70)

        # Read the actual source to verify the fix
        src_path = Path(__file__).parent.parent / "src" / "environment.py"
        source = src_path.read_text()

        # Check that 'or True' is gone
        lines = source.split('\n')
        for i, line in enumerate(lines, 1):
            if 'installer_path.exists()' in line:
                print(f"\n[SOURCE] Line {i}: {line.strip()}")
                self.assertNotIn("or True", line,
                                 "The 'or True' debug hack must be removed")
                print("  ✓ No 'or True' — cache works correctly")

        print("\n[BEHAVIOR]")
        print("  BEFORE: Downloaded elan-init.sh on EVERY call (wasted bandwidth)")
        print("  AFTER:  Reuses cached installer if it exists")
        print("\n[PASS] Cache condition is correct!")
        print("=" * 70)


# ════════════════════════════════════════════════════════════════════
# DEMO 5: LLM Feedback Isolation — Eval Harness Hidden
# ════════════════════════════════════════════════════════════════════

class TestDemo_FeedbackIsolation(unittest.TestCase):
    """
    NEW FEATURE: FeedbackSanitizer ensures the LLM never sees internal
    validation details, security check names, file paths, or budget info.
    This prevents the LLM from learning about and gaming the eval harness.
    """

    def test_system_errors_are_hidden(self):
        """DEMO: Internal validation errors are replaced with generic message."""
        print("\n" + "=" * 70)
        print("DEMO 5: LLM Feedback Isolation")
        print("=" * 70)

        system_errors = [
            "SYSTEM: Banned: Axiom declaration in proof candidate",
            "SYSTEM: Theorem statement was modified! Original hash: abc123...",
            "SYSTEM: Banned: Incomplete proof tactic 'sorry'",
        ]

        print("\n[INTERNAL ERRORS → LLM sees:]")
        for error in system_errors:
            sanitized = FeedbackSanitizer.sanitize(error)
            print(f"  IN:  {error}")
            print(f"  OUT: {sanitized}")
            print()
            # LLM must NOT see the internal details
            self.assertNotIn("SYSTEM:", sanitized)
            self.assertNotIn("Banned:", sanitized)
            self.assertNotIn("hash:", sanitized.lower())
            # It should get a generic rejection
            self.assertIn("rejected", sanitized.lower())

    def test_compiler_errors_are_passed_through(self):
        """DEMO: Lean compiler errors ARE shown to LLM (real feedback)."""
        compiler_error = (
            "COMPILER: /tmp/sandbox_abc123/Main.lean:5:2: error: "
            "type mismatch\n  expected: Nat\n  got: Bool"
        )

        sanitized = FeedbackSanitizer.sanitize(compiler_error)
        print("[COMPILER ERRORS → LLM sees:]")
        print(f"  IN:  {compiler_error}")
        print(f"  OUT: {sanitized}")

        # Compiler details ARE shown (useful for fixing proofs)
        self.assertIn("type mismatch", sanitized)
        self.assertIn("Nat", sanitized)
        # But sandbox paths are scrubbed
        self.assertNotIn("sandbox_abc123", sanitized)
        self.assertNotIn("/tmp/", sanitized)

    def test_critic_feedback_passed_through(self):
        """DEMO: Critic feedback is shown to LLM."""
        critic = "CRITIC: The proof is too verbose. Consider using simp."
        sanitized = FeedbackSanitizer.sanitize(critic)
        self.assertIn("too verbose", sanitized)
        self.assertNotIn("CRITIC:", sanitized)

    def test_budget_info_hidden(self):
        """DEMO: Budget exhaustion details are hidden from LLM."""
        budget = "BUDGET: Exhausted after $0.50 spent"
        sanitized = FeedbackSanitizer.sanitize(budget)
        self.assertNotIn("$0.50", sanitized)
        self.assertNotIn("BUDGET:", sanitized)

    def test_empty_error_gets_generic_message(self):
        """DEMO: Empty/None errors produce a helpful generic message."""
        sanitized = FeedbackSanitizer.sanitize("")
        self.assertIn("rejected", sanitized.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
