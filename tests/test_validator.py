"""
Tests for the validator module.
"""

import tempfile
import unittest
from pathlib import Path
from src.validator import (
    compute_theorem_hash,
    extract_theorem_statement,
    validate_theorem_integrity,
    validate_lean_file,
    check_banned_patterns,
    check_dangerous_io,
    check_suspicious_imports,
    run_security_check,
    SecurityReport,
    ValidationResult,
    TheoremLocker
)


class TestComputeHash(unittest.TestCase):
    """Test hash computation functionality."""
    
    def test_consistent_hash(self):
        """Test that compute_theorem_hash returns consistent SHA-256."""
        content = """
theorem test_theorem : 1 + 1 = 2 := by
  sorry
"""
        hash1 = compute_theorem_hash(content)
        hash2 = compute_theorem_hash(content)
        
        # Hash should be consistent
        self.assertEqual(hash1, hash2)
        
        # Hash should be SHA-256 (64 hex characters)
        self.assertEqual(len(hash1), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in hash1))
    
    def test_different_content_different_hash(self):
        """Test that different content produces different hashes."""
        content1 = "theorem test1 : 1 + 1 = 2 := by sorry"
        content2 = "theorem test2 : 2 + 2 = 4 := by sorry"
        
        hash1 = compute_theorem_hash(content1)
        hash2 = compute_theorem_hash(content2)
        
        self.assertNotEqual(hash1, hash2)
    
    def test_whitespace_normalized(self):
        """Test that whitespace differences don't affect hash."""
        content1 = "theorem test : 1 + 1 = 2 := by sorry"
        content2 = "theorem   test   :   1 + 1 = 2   :=   by sorry"
        
        hash1 = compute_theorem_hash(content1)
        hash2 = compute_theorem_hash(content2)
        
        # Hashes should be equal after normalization
        self.assertEqual(hash1, hash2)


class TestVerifyIntegrity(unittest.TestCase):
    """Test theorem integrity verification."""
    
    def test_detects_theorem_modification(self):
        """Test that theorem modification is detected."""
        original = "theorem test : 1 + 1 = 2 := by sorry"
        modified = "theorem test : 2 + 2 = 4 := by rfl"
        
        result = validate_theorem_integrity(original, modified)
        
        self.assertFalse(result.is_valid)
        self.assertTrue(any("modified" in error.lower() for error in result.errors))
    
    def test_allows_proof_change(self):
        """Test that changing proof body is allowed."""
        original = "theorem test : 1 + 1 = 2 := by sorry"
        candidate = "theorem test : 1 + 1 = 2 := by rfl"
        
        result = validate_theorem_integrity(original, candidate)
        
        # This should pass (same theorem, different proof)
        # Note: the current implementation may still flag this due to how it extracts statements
        # This test documents expected behavior
        self.assertTrue(result.is_valid or len(result.errors) == 0)


class TestBannedPatterns(unittest.TestCase):
    """Test banned pattern detection."""
    
    def test_detects_sorry(self):
        """Test detection of 'sorry' keyword."""
        content = "theorem test : 1 + 1 = 2 := by sorry"
        errors = check_banned_patterns(content)
        
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("sorry" in error.lower() for error in errors))
    
    def test_detects_admit(self):
        """Test detection of 'admit' keyword."""
        content = "theorem test : 1 + 1 = 2 := by admit"
        errors = check_banned_patterns(content)
        
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("admit" in error.lower() for error in errors))
    
    def test_detects_axiom(self):
        """Test detection of 'axiom' usage."""
        content = "theorem test : 1 + 1 = 2 := by axiom"
        errors = check_banned_patterns(content)
        
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("axiom" in error.lower() for error in errors))
    
    def test_allows_clean_proof(self):
        """Test that clean proofs pass."""
        content = "theorem test : 1 + 1 = 2 := by rfl"
        errors = check_banned_patterns(content)
        
        self.assertEqual(len(errors), 0)


class TestDangerousIO(unittest.TestCase):
    """Test dangerous IO pattern detection."""
    
    def test_detects_io_fs(self):
        """Test detection of IO.FS usage."""
        content = "import IO.FS\ntheorem test := by sorry"
        warnings = check_dangerous_io(content)
        
        self.assertTrue(len(warnings) > 0)
    
    def test_detects_system_process(self):
        """Test detection of System.Process usage."""
        content = "import System.Process\ntheorem test := by sorry"
        warnings = check_dangerous_io(content)
        
        self.assertTrue(len(warnings) > 0)
    
    def test_allows_safe_code(self):
        """Test that safe code passes."""
        content = "theorem test : 1 + 1 = 2 := by rfl"
        warnings = check_dangerous_io(content)
        
        self.assertEqual(len(warnings), 0)


class TestExtractTheoremStatement(unittest.TestCase):
    """Test theorem statement extraction."""
    
    def test_simple_theorem(self):
        """Test extraction of a simple theorem statement."""
        content = """
theorem simple_test : 1 + 1 = 2 := by
  rfl
"""
        statement = extract_theorem_statement(content)
        
        self.assertIn("theorem", statement.lower())
        self.assertIn("simple_test", statement)
        self.assertIn("1 + 1 = 2", statement)
    
    def test_complex_theorem(self):
        """Test extraction of a theorem with complex type signature."""
        content = """
theorem complex_test (n : Nat) (h : n > 0) : n + 1 > n := by
  omega
"""
        statement = extract_theorem_statement(content)
        
        self.assertIn("theorem", statement.lower())
        self.assertIn("complex_test", statement)


class TestTheoremLocker(unittest.TestCase):
    """Test TheoremLocker class."""
    
    def test_lock_and_verify(self):
        """Test locking and verifying a theorem."""
        locker = TheoremLocker()
        content = "theorem test : 1 + 1 = 2 := by sorry"
        
        # Lock the theorem
        hash_value = locker.lock_theorem("test_problem", content)
        
        # Hash should be stored
        self.assertIsNotNone(hash_value)
        
        # Verify with same content should pass
        self.assertTrue(locker.verify_theorem("test_problem", content))
        
        # Verify with different content should fail
        modified = "theorem test : 2 + 2 = 4 := by sorry"
        self.assertFalse(locker.verify_theorem("test_problem", modified))
    
    def test_get_hash(self):
        """Test retrieving stored hash."""
        locker = TheoremLocker()
        content = "theorem test : 1 + 1 = 2 := by sorry"
        
        hash_value = locker.lock_theorem("test_problem", content)
        retrieved_hash = locker.get_hash("test_problem")
        
        self.assertEqual(hash_value, retrieved_hash)
    
    def test_raises_on_uninitialized_verify(self):
        """Test that verify raises when theorem not locked."""
        locker = TheoremLocker()
        content = "theorem test : 1 + 1 = 2 := by sorry"
        
        with self.assertRaises(ValueError):
            locker.verify_theorem("unknown_problem", content)


class TestNewBannedPatterns(unittest.TestCase):
    """Test newly added banned patterns."""

    def test_detects_native_decide(self):
        content = "theorem test : True := by native_decide"
        errors = check_banned_patterns(content)
        self.assertTrue(any("native_decide" in e for e in errors))

    def test_detects_eval_io(self):
        content = '#eval IO.println "hello"'
        errors = check_banned_patterns(content)
        self.assertTrue(any("#eval" in e.lower() or "IO" in e for e in errors))

    def test_eval_without_io_is_clean(self):
        content = "#eval 1 + 1"
        errors = check_banned_patterns(content)
        self.assertFalse(any("#eval" in e.lower() for e in errors))

    def test_axiom_declaration_allowed(self):
        """axiom declarations (axiom name : type) should NOT be banned."""
        content = "axiom myAxiom : Nat -> Nat"
        errors = check_banned_patterns(content)
        self.assertFalse(any("axiom" in e.lower() for e in errors))


class TestNewIOPatterns(unittest.TestCase):
    """Test newly added IO patterns."""

    def test_detects_io_getstdin(self):
        content = "let input <- IO.getStdin"
        errors = check_dangerous_io(content)
        self.assertTrue(any("getStdin" in e for e in errors))

    def test_detects_io_print(self):
        content = "IO.print something"
        errors = check_dangerous_io(content)
        self.assertTrue(any("IO.print" in e for e in errors))

    def test_detects_system_filepath(self):
        content = "open System.FilePath"
        errors = check_dangerous_io(content)
        self.assertTrue(any("FilePath" in e for e in errors))

    def test_detects_io_process(self):
        content = "import IO.Process"
        errors = check_dangerous_io(content)
        self.assertTrue(any("IO.Process" in e for e in errors))


class TestSuspiciousImports(unittest.TestCase):
    """Test suspicious import detection (warnings)."""

    def test_detects_system_import(self):
        content = "import System\ntheorem test := by rfl"
        warnings = check_suspicious_imports(content)
        self.assertTrue(any("System" in w for w in warnings))

    def test_detects_io_fs_import(self):
        content = "import IO.FS\ntheorem test := by rfl"
        warnings = check_suspicious_imports(content)
        self.assertTrue(any("IO.FS" in w for w in warnings))

    def test_detects_lean_elab_command(self):
        content = "import Lean.Elab.Command"
        warnings = check_suspicious_imports(content)
        self.assertTrue(any("metaprogramming" in w.lower() for w in warnings))

    def test_detects_lean_elab_tactic(self):
        content = "import Lean.Elab.Tactic"
        warnings = check_suspicious_imports(content)
        self.assertTrue(any("custom tactics" in w.lower() for w in warnings))

    def test_clean_imports_pass(self):
        content = "import Mathlib.Tactic\ntheorem test := by rfl"
        warnings = check_suspicious_imports(content)
        self.assertEqual(len(warnings), 0)


class TestSecurityReport(unittest.TestCase):
    """Test SecurityReport dataclass."""

    def test_clean_code_is_safe(self):
        report = run_security_check("theorem test : 1 + 1 = 2 := by rfl")
        self.assertTrue(report.is_safe)
        self.assertFalse(report.has_warnings)

    def test_sorry_makes_unsafe(self):
        report = run_security_check("theorem test := by sorry")
        self.assertFalse(report.is_safe)
        self.assertTrue(len(report.banned_patterns) > 0)

    def test_io_makes_unsafe(self):
        report = run_security_check("let x <- IO.FS.readFile \"test\"")
        self.assertFalse(report.is_safe)
        self.assertTrue(len(report.io_violations) > 0)

    def test_suspicious_import_gives_warning(self):
        report = run_security_check("import System\ntheorem test := by rfl")
        self.assertTrue(report.is_safe)  # warnings don't make it unsafe
        self.assertTrue(report.has_warnings)

    def test_combined_violations(self):
        content = "import System\nIO.FS.readFile \"x\"\ntheorem t := by sorry"
        report = run_security_check(content)
        self.assertFalse(report.is_safe)
        self.assertTrue(len(report.banned_patterns) > 0)
        self.assertTrue(len(report.io_violations) > 0)
        self.assertTrue(report.has_warnings)


class TestValidateIntegrityWithSecurity(unittest.TestCase):
    """Test that validate_theorem_integrity includes security analysis."""

    def test_result_includes_security_report(self):
        content = "theorem test : 1 + 1 = 2 := by rfl"
        result = validate_theorem_integrity(content, content)
        self.assertIsNotNone(result.security)
        self.assertIsInstance(result.security, SecurityReport)

    def test_banned_pattern_fails_validation(self):
        content = "theorem test : 1 + 1 = 2 := by sorry"
        result = validate_theorem_integrity(content, content)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("sorry" in e.lower() for e in result.errors))

    def test_suspicious_import_becomes_warning(self):
        content = "import Lean.Elab.Command\ntheorem test : 1 + 1 = 2 := by rfl"
        result = validate_theorem_integrity(content, content)
        self.assertTrue(result.is_valid)  # warnings don't fail
        self.assertTrue(len(result.warnings) > 0)


class TestValidateLeanFile(unittest.TestCase):
    """Test file-level validation."""

    def test_nonexistent_file(self):
        result = validate_lean_file(Path("/nonexistent/file.lean"))
        self.assertFalse(result.is_valid)
        self.assertTrue(any("does not exist" in e for e in result.errors))

    def test_non_lean_file(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"print('hello')")
            f.flush()
            result = validate_lean_file(Path(f.name))
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Not a Lean file" in e for e in result.errors))

    def test_valid_lean_file(self):
        with tempfile.NamedTemporaryFile(suffix=".lean", delete=False, mode="w") as f:
            f.write("theorem test : 1 + 1 = 2 := by rfl\n")
            f.flush()
            result = validate_lean_file(Path(f.name))
        self.assertTrue(result.is_valid)
        self.assertIsNotNone(result.security)

    def test_lean_file_with_sorry(self):
        with tempfile.NamedTemporaryFile(suffix=".lean", delete=False, mode="w") as f:
            f.write("theorem test : 1 + 1 = 2 := by sorry\n")
            f.flush()
            result = validate_lean_file(Path(f.name))
        self.assertFalse(result.is_valid)


if __name__ == '__main__':
    unittest.main()
