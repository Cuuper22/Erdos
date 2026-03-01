"""
Validator module for the Erdos Proof Mining System.

Provides theorem integrity validation and security checks
to ensure proofs are legitimate and don't escape the sandbox.
"""

import re
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Banned patterns (errors — proof is invalid) ──

BANNED_PATTERNS = [
    (re.compile(r"\bsorry\b"), "Incomplete proof tactic 'sorry'"),
    (re.compile(r"\badmit\b"), "Incomplete proof tactic 'admit'"),
    (re.compile(r"\baxiom\b(?!\s+\w+\s*:)"), "Axiom usage (non-declaration)"),
    (re.compile(r"\bnative_decide\b"), "Unsafe native_decide tactic"),
    (re.compile(r"#eval\s+.*\bIO\b"), "#eval with IO side effects"),
]

# ── Dangerous IO patterns (errors — blocked) ──

DANGEROUS_IO_PATTERNS = [
    (re.compile(r"\bIO\.FS\b"), "File system access (IO.FS)"),
    (re.compile(r"\bSystem\.Process\b"), "Process spawning (System.Process)"),
    (re.compile(r"\bIO\.Process\b"), "Process spawning (IO.Process)"),
    (re.compile(r"\bIO\.getStdin\b"), "Stdin access (IO.getStdin)"),
    (re.compile(r"\bIO\.print\b"), "Print to stdout (IO.print)"),
    (re.compile(r"\bSystem\.FilePath\b"), "File path manipulation (System.FilePath)"),
]

# ── Suspicious imports (warnings) ──

SUSPICIOUS_IMPORTS = [
    (re.compile(r"import\s+System\b"), "Import of System module"),
    (re.compile(r"import\s+IO\.FS\b"), "Import of IO.FS module"),
    (re.compile(r"import\s+Lean\.Elab\.Command\b"), "Import of Lean.Elab.Command (metaprogramming)"),
    (re.compile(r"import\s+Lean\.Elab\.Tactic\b"), "Import of Lean.Elab.Tactic (custom tactics)"),
]


@dataclass
class SecurityReport:
    """Detailed security analysis of a proof."""
    banned_patterns: list[str] = field(default_factory=list)
    io_violations: list[str] = field(default_factory=list)
    suspicious_imports: list[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        return not self.banned_patterns and not self.io_violations

    @property
    def has_warnings(self) -> bool:
        return bool(self.suspicious_imports)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    security: Optional[SecurityReport] = None

    def __bool__(self) -> bool:
        return self.is_valid


def extract_theorem_statement(content: str, theorem_name: Optional[str] = None) -> str:
    """Extract the theorem statement from Lean code (up to :=)."""
    if theorem_name:
        pattern = rf'(?:theorem\s+{re.escape(theorem_name)}|lemma\s+{re.escape(theorem_name)}).*?:='
    else:
        pattern = r'(?:theorem\s+\w+|lemma\s+\w+).*?:='

    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(0)

    # Fallback: line-by-line search
    lines = content.split('\n')
    theorem_lines = []
    in_theorem = False

    for line in lines:
        if re.match(r'\s*(theorem|lemma)\s+\w+', line):
            in_theorem = True
        if in_theorem:
            theorem_lines.append(line)
            if ':=' in line or 'where' in line:
                break

    return '\n'.join(theorem_lines)


def compute_theorem_hash(content: str, theorem_name: Optional[str] = None) -> str:
    """Compute SHA-256 hash of the normalized theorem statement."""
    statement = extract_theorem_statement(content, theorem_name)
    normalized = ' '.join(statement.split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def check_banned_patterns(content: str) -> list[str]:
    """Check for banned patterns in the proof."""
    errors = []
    for pattern, description in BANNED_PATTERNS:
        if pattern.search(content):
            errors.append(f"Banned: {description}")
    return errors


def check_dangerous_io(content: str) -> list[str]:
    """Check for dangerous IO patterns (blocked)."""
    errors = []
    for pattern, description in DANGEROUS_IO_PATTERNS:
        if pattern.search(content):
            errors.append(f"Blocked: {description}")
    return errors


def check_suspicious_imports(content: str) -> list[str]:
    """Check for suspicious imports (warnings only)."""
    warnings = []
    for pattern, description in SUSPICIOUS_IMPORTS:
        if pattern.search(content):
            warnings.append(f"Suspicious: {description}")
    return warnings


def run_security_check(content: str) -> SecurityReport:
    """Run comprehensive security analysis on proof content."""
    return SecurityReport(
        banned_patterns=check_banned_patterns(content),
        io_violations=check_dangerous_io(content),
        suspicious_imports=check_suspicious_imports(content),
    )


def validate_theorem_integrity(
    original_content: str,
    candidate_content: str,
    theorem_name: Optional[str] = None,
) -> ValidationResult:
    """Validate that the theorem statement hasn't been modified."""
    errors = []
    warnings = []

    # Hash comparison
    original_hash = compute_theorem_hash(original_content, theorem_name)
    candidate_hash = compute_theorem_hash(candidate_content, theorem_name)

    if original_hash != candidate_hash:
        errors.append(
            f"Theorem statement was modified! "
            f"Original hash: {original_hash[:16]}... "
            f"Candidate hash: {candidate_hash[:16]}..."
        )

    # Security analysis
    security = run_security_check(candidate_content)
    errors.extend(security.banned_patterns)
    errors.extend(security.io_violations)
    warnings.extend(security.suspicious_imports)

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        security=security,
    )


def validate_lean_file(file_path: Path) -> ValidationResult:
    """Perform validation on a Lean file."""
    errors = []
    warnings = []

    if not file_path.exists():
        errors.append(f"File does not exist: {file_path}")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    if file_path.suffix != '.lean':
        errors.append(f"Not a Lean file: {file_path}")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    try:
        content = file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        errors.append(f"Could not read file as UTF-8: {file_path}")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    security = run_security_check(content)
    errors.extend(security.banned_patterns)
    errors.extend(security.io_violations)
    warnings.extend(security.suspicious_imports)

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        security=security,
    )


class TheoremLocker:
    """Manages theorem statement integrity across proof attempts."""

    def __init__(self):
        self._hash_cache: dict[str, str] = {}

    def lock_theorem(self, problem_id: str, content: str, theorem_name: Optional[str] = None) -> str:
        """Lock a theorem by computing and storing its hash."""
        cache_key = f"{problem_id}:{theorem_name or 'default'}"
        hash_value = compute_theorem_hash(content, theorem_name)
        self._hash_cache[cache_key] = hash_value
        return hash_value

    def verify_theorem(
        self, problem_id: str, candidate_content: str,
        theorem_name: Optional[str] = None,
    ) -> bool:
        """Verify a candidate proof hasn't modified the theorem statement."""
        cache_key = f"{problem_id}:{theorem_name or 'default'}"
        if cache_key not in self._hash_cache:
            raise ValueError(f"Theorem not locked: {cache_key}")
        candidate_hash = compute_theorem_hash(candidate_content, theorem_name)
        return self._hash_cache[cache_key] == candidate_hash

    def get_hash(self, problem_id: str, theorem_name: Optional[str] = None) -> Optional[str]:
        """Get the stored hash for a theorem."""
        cache_key = f"{problem_id}:{theorem_name or 'default'}"
        return self._hash_cache.get(cache_key)
