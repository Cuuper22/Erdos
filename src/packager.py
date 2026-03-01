"""
Proof artifact packager for the Erdos Proof Mining System.

Packages verified proofs into ZIP bundles containing:
- proof.lean: The verified Lean 4 proof
- build_log.txt: Lake build output
- critique.json: Critic agent review
- metadata.json: Problem metadata, cost, hashes, etc.

Also maintains a local JSON index of all solutions for CLI querying.
"""

import json
import zipfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .validator import compute_theorem_hash


# Default solutions directory
DEFAULT_SOLUTIONS_DIR = Path.home() / ".erdos-prover" / "solutions"
INDEX_FILENAME = "solutions_index.json"


def _solutions_dir(output_dir: Optional[Path] = None) -> Path:
    """Get the solutions directory, creating it if needed."""
    d = output_dir or DEFAULT_SOLUTIONS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_index(solutions_dir: Path) -> list[dict]:
    """Load the solutions index from disk."""
    index_path = solutions_dir / INDEX_FILENAME
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_index(solutions_dir: Path, index: list[dict]) -> None:
    """Save the solutions index to disk."""
    index_path = solutions_dir / INDEX_FILENAME
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, default=str)


def package_artifact(
    artifact,
    output_dir: Optional[Path] = None,
    model_name: str = "unknown",
    cost_usd: float = 0.0,
) -> Path:
    """Package a ProofArtifact into a ZIP bundle.

    Args:
        artifact: A ProofArtifact instance from solver.py
        output_dir: Directory to store ZIP files (default: ~/.erdos-prover/solutions/)
        model_name: Name of the LLM model used
        cost_usd: Total cost in USD for this solution

    Returns:
        Path to the created ZIP file.
    """
    solutions_dir = _solutions_dir(output_dir)

    # Build the ZIP filename
    ts = artifact.timestamp.strftime("%Y%m%d_%H%M%S")
    zip_name = f"solution_{artifact.problem_id}_{ts}.zip"
    zip_path = solutions_dir / zip_name

    # Compute theorem hash for integrity tracking
    theorem_hash = compute_theorem_hash(artifact.proof_content)

    # Build metadata
    metadata = {
        "problem_id": artifact.problem_id,
        "timestamp": artifact.timestamp.isoformat(),
        "attempts": artifact.attempts,
        "model": model_name,
        "cost_usd": cost_usd,
        "theorem_hash": theorem_hash,
    }

    # Build critique dict
    critique_data = {
        "status": artifact.critique.status,
        "feedback": artifact.critique.feedback,
        "is_elegant": artifact.critique.is_elegant,
        "security_concerns": artifact.critique.security_concerns,
    }

    # Write the ZIP
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        prefix = f"solution_{artifact.problem_id}"
        zf.writestr(f"{prefix}/proof.lean", artifact.proof_content)
        zf.writestr(f"{prefix}/build_log.txt", artifact.build_logs)
        zf.writestr(
            f"{prefix}/critique.json",
            json.dumps(critique_data, indent=2, default=str),
        )
        zf.writestr(
            f"{prefix}/metadata.json",
            json.dumps(metadata, indent=2, default=str),
        )

    # Update the index
    _update_index(solutions_dir, metadata, zip_name, critique_data)

    return zip_path


def _update_index(
    solutions_dir: Path,
    metadata: dict,
    zip_name: str,
    critique: dict,
) -> None:
    """Add an entry to the solutions index."""
    index = _load_index(solutions_dir)
    entry = {
        **metadata,
        "zip_file": zip_name,
        "is_elegant": critique.get("is_elegant", False),
        "critique_status": critique.get("status", ""),
    }
    index.append(entry)
    _save_index(solutions_dir, index)


def list_solutions(output_dir: Optional[Path] = None) -> list[dict]:
    """List all packaged solutions.

    Returns:
        List of solution metadata dicts sorted by timestamp (newest first).
    """
    solutions_dir = _solutions_dir(output_dir)
    index = _load_index(solutions_dir)
    return sorted(index, key=lambda e: e.get("timestamp", ""), reverse=True)


def get_solution(
    problem_id: str,
    output_dir: Optional[Path] = None,
) -> Optional[dict]:
    """Get the most recent solution for a problem.

    Args:
        problem_id: The problem identifier.
        output_dir: Solutions directory.

    Returns:
        Solution metadata dict, or None if not found.
    """
    solutions = list_solutions(output_dir)
    for s in solutions:
        if s.get("problem_id") == problem_id:
            return s
    return None


def extract_solution(
    problem_id: str,
    extract_to: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Extract a solution ZIP to a directory.

    Args:
        problem_id: The problem identifier.
        extract_to: Directory to extract into (default: current dir).
        output_dir: Solutions directory.

    Returns:
        Path to the extracted directory, or None if not found.
    """
    solution = get_solution(problem_id, output_dir)
    if not solution:
        return None

    solutions_dir = _solutions_dir(output_dir)
    zip_path = solutions_dir / solution["zip_file"]
    if not zip_path.exists():
        return None

    target = extract_to or Path.cwd()
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target)

    return target / f"solution_{problem_id}"
