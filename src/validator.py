"""
Validator module for the Erdos Proof Mining System.

This module provides theorem integrity validation and sanity checks
to ensure proofs are legitimate and don't modify theorem statements.
"""

import re
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Banned patterns that indicate incomplete or invalid proofs
BANNED_PATTERNS = [
    r'\bsorry\b',
    r'\badmit\b',
    r'\baxiom\b(?!\s+\w+\s*:)',  # axiom declarations are ok, but axiom usage is not
]

# Dangerous IO patterns that should be blocked
DANGEROUS_IO_PATTERNS = [
    r'\bIO\.FS\b',
    r'\bSystem\.Process\b',
    r'\bIO\.Process\b',
]


@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    
    def __bool__(self) -> bool:
        return self.is_valid


def extract_theorem_statement(content: str, theorem_name: Optional[str] = None) -> str:
    """
    Extract the theorem statement from Lean code.
    
    The theorem statement is everything up to and including the := or where
    keyword, but not the proof body.
    """
    # Pattern to match theorem/lemma declarations
    if theorem_name:
        pattern = rf'(theorem\s+{re.escape(theorem_name)}|lemma\s+{re.escape(theorem_name)})\s*[^:]*:[^:=]*(?::=|where)'
    else:
        pattern = r'(theorem\s+\w+|lemma\s+\w+)\s*[^:]*:[^:=]*(?::=|where)'
    
    matches = re.findall(pattern, content, re.DOTALL)
    
    if not matches:
        # Fallback: try to find any theorem/lemma line
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
    
    return matches[0] if isinstance(matches[0], str) else matches[0][0]


def compute_theorem_hash(content: str, theorem_name: Optional[str] = None) -> str:
    """
    Compute SHA-256 hash of the theorem statement.
    
    This is used to verify that the theorem statement hasn't been modified.
    """
    statement = extract_theorem_statement(content, theorem_name)
    # Normalize whitespace for consistent hashing
    normalized = ' '.join(statement.split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def check_banned_patterns(content: str) -> list[str]:
    """Check for banned patterns in the proof."""
    errors = []
    
    for pattern in BANNED_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            errors.append(f"Found banned pattern: {matches[0]}")
    
    return errors


def check_dangerous_io(content: str) -> list[str]:
    """Check for dangerous IO patterns in the code."""
    warnings = []
    
    for pattern in DANGEROUS_IO_PATTERNS:
        if re.search(pattern, content):
            warnings.append(f"Potentially dangerous IO pattern found: {pattern}")
    
    return warnings


def validate_theorem_integrity(
    original_content: str,
    candidate_content: str,
    theorem_name: Optional[str] = None
) -> ValidationResult:
    """
    Validate that the theorem statement hasn't been modified.
    
    Args:
        original_content: The original Lean file content
        candidate_content: The candidate proof content
        theorem_name: Optional specific theorem name to validate
    
    Returns:
        ValidationResult indicating if the proof is valid
    """
    errors = []
    warnings = []
    
    # Compute hashes
    original_hash = compute_theorem_hash(original_content, theorem_name)
    candidate_hash = compute_theorem_hash(candidate_content, theorem_name)
    
    if original_hash != candidate_hash:
        errors.append(
            f"Theorem statement was modified! "
            f"Original hash: {original_hash[:16]}... "
            f"Candidate hash: {candidate_hash[:16]}..."
        )
    
    # Check for banned patterns
    banned_errors = check_banned_patterns(candidate_content)
    errors.extend(banned_errors)
    
    # Check for dangerous IO
    io_warnings = check_dangerous_io(candidate_content)
    warnings.extend(io_warnings)
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def validate_lean_file(file_path: Path) -> ValidationResult:
    """
    Perform basic validation on a Lean file.
    
    Args:
        file_path: Path to the Lean file
    
    Returns:
        ValidationResult indicating if the file is valid
    """
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
    
    # Check for banned patterns
    banned_errors = check_banned_patterns(content)
    errors.extend(banned_errors)
    
    # Check for dangerous IO
    io_warnings = check_dangerous_io(content)
    warnings.extend(io_warnings)
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


class TheoremLocker:
    """
    Manages theorem statement integrity across proof attempts.
    
    This class maintains a cache of theorem hashes to quickly validate
    that proof candidates haven't modified the original theorem statements.
    """
    
    def __init__(self):
        self._hash_cache: dict[str, str] = {}
    
    def lock_theorem(self, problem_id: str, content: str, theorem_name: Optional[str] = None) -> str:
        """
        Lock a theorem statement by computing and storing its hash.
        
        Args:
            problem_id: Unique identifier for the problem
            content: The original Lean file content
            theorem_name: Optional specific theorem name
        
        Returns:
            The computed hash
        """
        cache_key = f"{problem_id}:{theorem_name or 'default'}"
        hash_value = compute_theorem_hash(content, theorem_name)
        self._hash_cache[cache_key] = hash_value
        return hash_value
    
    def verify_theorem(
        self,
        problem_id: str,
        candidate_content: str,
        theorem_name: Optional[str] = None
    ) -> bool:
        """
        Verify that a candidate proof hasn't modified the theorem statement.
        
        Args:
            problem_id: Unique identifier for the problem
            candidate_content: The candidate proof content
            theorem_name: Optional specific theorem name
        
        Returns:
            True if the theorem statement is unchanged
        """
        cache_key = f"{problem_id}:{theorem_name or 'default'}"
        
        if cache_key not in self._hash_cache:
            raise ValueError(f"Theorem not locked: {cache_key}")
        
        candidate_hash = compute_theorem_hash(candidate_content, theorem_name)
        return self._hash_cache[cache_key] == candidate_hash
    
    def get_hash(self, problem_id: str, theorem_name: Optional[str] = None) -> Optional[str]:
        """Get the stored hash for a theorem."""
        cache_key = f"{problem_id}:{theorem_name or 'default'}"
        return self._hash_cache.get(cache_key)
