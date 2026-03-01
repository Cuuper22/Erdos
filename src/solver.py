"""
Solver module for the Erdos Proof Mining System.

This module implements the main Prover/Critic loop that attempts to
generate and validate Lean 4 proofs using LLM assistance.
"""

import json
import logging
import os
import re
import time
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime

from .config import Config
from .validator import TheoremLocker, validate_theorem_integrity, ValidationResult
from .sandbox import Sandbox, SandboxManager, run_lake_build, BuildResult
from .llm import LLMProvider, MockLLMProvider, GeminiProvider, GeminiAPIError, create_provider
from .logging_config import setup_logging
from .events import (
    emit_event, ProblemStarted, CostUpdate, AttemptResult,
    SolutionFound, ProblemFailed, MiningComplete,
)

logger = logging.getLogger(__name__)


# Error classification
class _ErrorKind:
    TRANSIENT = "transient"  # Retry with backoff
    PERMANENT = "permanent"  # Stop immediately
    BUDGET = "budget"        # Budget exhausted


def _classify_error(error: Exception) -> str:
    """Classify an error as transient, permanent, or budget."""
    err_str = str(error).lower()
    if any(kw in err_str for kw in ["rate limit", "429", "503", "500", "overloaded", "unavailable", "timeout"]):
        return _ErrorKind.TRANSIENT
    if any(kw in err_str for kw in ["401", "403", "invalid", "authentication", "unauthorized"]):
        return _ErrorKind.PERMANENT
    if "budget" in err_str:
        return _ErrorKind.BUDGET
    # Default: treat as transient (allow retry)
    return _ErrorKind.TRANSIENT


@dataclass
class Problem:
    """Represents a proof mining problem."""
    id: str
    path: str
    difficulty: str = "Unknown"
    maintainer_note: str = ""
    original_content: Optional[str] = None


@dataclass
class Critique:
    """Result of the Critic agent's review."""
    status: str  # "PASS" or "FAIL"
    feedback: str
    is_elegant: bool = False
    security_concerns: list[str] = field(default_factory=list)


@dataclass
class ProofArtifact:
    """A validated proof ready for submission."""
    problem_id: str
    proof_content: str
    build_logs: str
    critique: Critique
    timestamp: datetime = field(default_factory=datetime.now)
    attempts: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "problem_id": self.problem_id,
            "proof_content": self.proof_content,
            "build_logs": self.build_logs,
            "critique": {
                "status": self.critique.status,
                "feedback": self.critique.feedback,
                "is_elegant": self.critique.is_elegant,
                "security_concerns": self.critique.security_concerns,
            },
            "timestamp": self.timestamp.isoformat(),
            "attempts": self.attempts,
        }




class AgentProver:
    """
    The Prover agent responsible for generating proof candidates.
    
    Uses an LLM to attempt to close 'sorry' gaps in Lean code.
    """
    
    SYSTEM_PROMPT = """You are a formalization expert specializing in Lean 4 proofs.
Your task is to complete mathematical proofs by replacing 'sorry' placeholders with valid Lean 4 tactics.

Rules:
1. Output ONLY raw Lean 4 code - no explanations, no markdown code blocks
2. Do NOT modify the theorem statement or imports
3. Use standard Lean 4 tactics: simp, ring, omega, rfl, exact, apply, have, etc.
4. Keep proofs concise and elegant when possible
5. Never use 'sorry', 'admit', or 'axiom' in your solution
"""
    
    def __init__(self, llm: LLMProvider, temperature: float = 0.7):
        """
        Initialize the Prover agent.
        
        Args:
            llm: The LLM provider to use
            temperature: Sampling temperature for generation
        """
        self.llm = llm
        self.temperature = temperature
    
    def generate(
        self,
        problem_content: str,
        instructions: str = "",
        error_log: Optional[str] = None
    ) -> tuple[str, int, int]:
        """
        Generate a proof candidate.
        
        Args:
            problem_content: The Lean file content with 'sorry' to replace
            instructions: Optional maintainer instructions/hints
            error_log: Optional previous error to learn from
        
        Returns:
            Tuple of (proof_candidate, input_tokens, output_tokens)
        """
        prompt_parts = [self.SYSTEM_PROMPT, "\n\n--- LEAN CODE ---\n", problem_content]
        
        if instructions:
            prompt_parts.extend(["\n\n--- MAINTAINER HINTS ---\n", instructions])
        
        if error_log:
            prompt_parts.extend([
                "\n\n--- PREVIOUS ERROR ---\n",
                "Your previous attempt failed with this error. Fix it:\n",
                error_log
            ])
        
        prompt_parts.append("\n\n--- YOUR SOLUTION ---\nReplace 'sorry' with a valid proof:")
        
        prompt = ''.join(prompt_parts)
        response, in_tokens, out_tokens = self.llm.generate(
            prompt,
            temperature=self.temperature
        )
        
        # Clean up the response
        candidate = self._clean_response(response, problem_content)
        
        return candidate, in_tokens, out_tokens
    
    def _clean_response(self, response: str, original: str) -> str:
        """Clean up the LLM response to extract valid Lean code."""
        # Remove markdown code blocks if present
        response = re.sub(r'```lean\n?', '', response)
        response = re.sub(r'```\n?', '', response)
        
        # If response looks like a complete file, use it
        if 'theorem' in response or 'lemma' in response:
            return response.strip()
        
        # Otherwise, try to insert the response into the original
        # replacing 'sorry' with the generated proof
        if 'sorry' in original:
            return original.replace('sorry', response.strip(), 1)
        
        return response.strip()


class AgentCritic:
    """
    The Critic agent responsible for quality control.
    
    Reviews proof candidates for correctness, elegance, and security.
    """
    
    SYSTEM_PROMPT = """You are a code review expert for Lean 4 proofs.
Your job is to evaluate proof quality and security.

Evaluate the following aspects:
1. CORRECTNESS: Does the proof logically follow from the premises?
2. ELEGANCE: Is the proof concise and well-structured, or is it brute-force?
3. SECURITY: Are there any dangerous IO operations or suspicious code patterns?

Respond in this exact JSON format:
{
    "status": "PASS" or "FAIL",
    "feedback": "Brief explanation",
    "is_elegant": true/false,
    "security_concerns": ["list", "of", "concerns"] or []
}
"""
    
    def __init__(self, llm: LLMProvider, temperature: float = 0.1):
        """
        Initialize the Critic agent.
        
        Args:
            llm: The LLM provider to use
            temperature: Sampling temperature (low for consistent critiques)
        """
        self.llm = llm
        self.temperature = temperature
    
    def review(self, proof_content: str, build_logs: str = "") -> tuple[Critique, int, int]:
        """
        Review a proof candidate.
        
        Args:
            proof_content: The Lean proof to review
            build_logs: Optional build logs from compilation
        
        Returns:
            Tuple of (Critique, input_tokens, output_tokens)
        """
        prompt = f"""{self.SYSTEM_PROMPT}

--- PROOF TO REVIEW ---
{proof_content}

--- BUILD LOGS ---
{build_logs if build_logs else "Build successful, no errors."}

--- YOUR REVIEW (JSON) ---"""
        
        response, in_tokens, out_tokens = self.llm.generate(
            prompt,
            temperature=self.temperature
        )
        
        critique = self._parse_critique(response)
        return critique, in_tokens, out_tokens
    
    def _parse_critique(self, response: str) -> Critique:
        """Parse the LLM response into a Critique object."""
        try:
            # Try to find and parse JSON from the response
            # Handle potentially nested JSON by finding balanced braces
            start_idx = response.find('{')
            if start_idx != -1:
                brace_count = 0
                end_idx = start_idx
                for i, char in enumerate(response[start_idx:], start_idx):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break
                
                if end_idx > start_idx:
                    json_str = response[start_idx:end_idx]
                    data = json.loads(json_str)
                    return Critique(
                        status=data.get("status", "FAIL"),
                        feedback=data.get("feedback", "Unable to parse feedback"),
                        is_elegant=data.get("is_elegant", False),
                        security_concerns=data.get("security_concerns", [])
                    )
        except json.JSONDecodeError:
            pass
        
        # Fallback: simple heuristic parsing
        status = "PASS" if "pass" in response.lower() else "FAIL"
        return Critique(
            status=status,
            feedback=response[:500],
            is_elegant=False,
            security_concerns=[]
        )


class Solver:
    """
    Main solver that orchestrates the Prover/Critic loop.
    
    This class manages the entire proof generation pipeline:
    1. Set up sandbox environment
    2. Lock theorem statement (integrity check)
    3. Run prover/critic loop
    4. Package successful proofs
    """
    
    def __init__(self, config: Config, llm: LLMProvider):
        """
        Initialize the solver.
        
        Args:
            config: Configuration settings
            llm: LLM provider for agents
        """
        self.config = config
        self.prover = AgentProver(llm, temperature=config.llm.temperature_prover)
        self.critic = AgentCritic(llm, temperature=config.llm.temperature_critic)
        self.theorem_locker = TheoremLocker()
        self.sandbox_manager = SandboxManager(config.solver.work_dir)
    
    def process_problem(
        self,
        problem: Problem,
        source_dir: Optional[Path] = None
    ) -> Optional[ProofArtifact]:
        """
        Attempt to solve a proof mining problem.
        
        Args:
            problem: The problem to solve
            source_dir: Optional source directory with Lean project
        
        Returns:
            ProofArtifact if successful, None otherwise
        """
        logger.info(f"Processing problem: {problem.id}")
        
        # Check budget
        if not self.config.cost.check_budget():
            logger.warning("Budget exhausted, stopping")
            return None
        
        # Create sandbox
        sandbox = self.sandbox_manager.create_sandbox(problem.id, source_dir)
        
        try:
            # Load original content
            if problem.original_content:
                original_content = problem.original_content
            else:
                try:
                    original_content = sandbox.read_file(problem.path)
                except FileNotFoundError:
                    logger.error(f"Problem file not found: {problem.path}")
                    return None
            
            # Lock theorem statement
            self.theorem_locker.lock_theorem(problem.id, original_content)
            
            # Run the solving loop
            return self._solve_loop(
                problem=problem,
                sandbox=sandbox,
                original_content=original_content
            )
        
        finally:
            self.sandbox_manager.cleanup_sandbox(problem.id)
    
    def _solve_loop(
        self,
        problem: Problem,
        sandbox: Sandbox,
        original_content: str
    ) -> Optional[ProofArtifact]:
        """
        Run the main prover/critic loop.
        
        Args:
            problem: The problem being solved
            sandbox: The sandbox environment
            original_content: Original Lean file content
        
        Returns:
            ProofArtifact if successful, None otherwise
        """
        last_error: Optional[str] = None
        max_retries = self.config.solver.max_retries

        emit_event(ProblemStarted(
            problem_id=problem.id,
            difficulty=problem.difficulty,
            max_retries=max_retries,
        ))

        for attempt in range(max_retries):
            logger.info(f"Attempt {attempt + 1}/{max_retries}")

            # Check budget before each attempt
            if not self.config.cost.check_budget():
                logger.warning(f"Budget exhausted after {attempt} attempts")
                emit_event(ProblemFailed(
                    problem_id=problem.id, attempts=attempt,
                    last_error="Budget exhausted",
                ))
                break

            # A. GENERATE proof candidate
            try:
                candidate, in_tokens, out_tokens = self.prover.generate(
                    problem_content=original_content,
                    instructions=problem.maintainer_note,
                    error_log=last_error
                )
                cost = self.config.cost.add_usage(in_tokens, out_tokens)
                emit_event(CostUpdate(
                    cost_usd=cost,
                    total_spent_usd=self.config.cost.current_spent,
                    remaining_usd=self.config.cost.remaining_budget(),
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                ))
            except Exception as e:
                kind = _classify_error(e)
                logger.error(f"Prover generation failed ({kind}): {e}")
                last_error = str(e)
                emit_event(AttemptResult(
                    problem_id=problem.id, attempt=attempt + 1,
                    status="generation_error", message=str(e),
                ))
                if kind == _ErrorKind.PERMANENT:
                    logger.error("Permanent error — stopping retries")
                    break
                if kind == _ErrorKind.TRANSIENT and attempt < max_retries - 1:
                    delay = min(1.0 * (2 ** attempt) + random.uniform(0, 1), 30.0)
                    logger.info(f"Backing off {delay:.1f}s before retry")
                    time.sleep(delay)
                continue

            # B. INTEGRITY CHECK
            validation = validate_theorem_integrity(original_content, candidate)
            if not validation.is_valid:
                last_error = f"SYSTEM: {'; '.join(validation.errors)}"
                logger.warning(f"Integrity check failed: {last_error}")
                emit_event(AttemptResult(
                    problem_id=problem.id, attempt=attempt + 1,
                    status="integrity_fail", message=last_error,
                ))
                continue

            # Write candidate to sandbox
            sandbox.write_file(problem.path, candidate)

            # C. COMPILATION CHECK
            if sandbox.work_dir:
                build_result = run_lake_build(
                    sandbox.work_dir,
                    timeout_seconds=self.config.solver.build_timeout_seconds
                )
            else:
                build_result = BuildResult(
                    success=False, stdout="",
                    stderr="Sandbox not initialized",
                    return_code=-1, duration_seconds=0,
                )

            if not build_result.success:
                last_error = f"COMPILER: {build_result.get_error_summary()}"
                logger.info(f"Build failed: {last_error[:200]}")
                emit_event(AttemptResult(
                    problem_id=problem.id, attempt=attempt + 1,
                    status="build_fail", message=last_error[:200],
                ))
                continue

            logger.info("Build successful, running critic review")

            # D. CRITIC CHECK
            try:
                critique, in_tokens, out_tokens = self.critic.review(
                    candidate,
                    build_result.stdout + build_result.stderr
                )
                cost = self.config.cost.add_usage(in_tokens, out_tokens)
                emit_event(CostUpdate(
                    cost_usd=cost,
                    total_spent_usd=self.config.cost.current_spent,
                    remaining_usd=self.config.cost.remaining_budget(),
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                ))
            except Exception as e:
                logger.error(f"Critic review failed: {e}")
                last_error = str(e)
                emit_event(AttemptResult(
                    problem_id=problem.id, attempt=attempt + 1,
                    status="critic_error", message=str(e),
                ))
                continue

            if critique.status == "PASS":
                logger.info(f"Proof found after {attempt + 1} attempts")
                emit_event(SolutionFound(
                    problem_id=problem.id,
                    attempts=attempt + 1,
                    proof_preview=candidate[:200],
                    is_elegant=critique.is_elegant,
                ))
                return ProofArtifact(
                    problem_id=problem.id,
                    proof_content=candidate,
                    build_logs=build_result.stdout,
                    critique=critique,
                    attempts=attempt + 1
                )
            else:
                last_error = f"CRITIC: {critique.feedback}"
                logger.info(f"Critic rejected proof: {critique.feedback[:200]}")
                emit_event(AttemptResult(
                    problem_id=problem.id, attempt=attempt + 1,
                    status="critic_fail", message=critique.feedback[:200],
                ))

        logger.warning(f"Failed to solve after {max_retries} attempts")
        emit_event(ProblemFailed(
            problem_id=problem.id,
            attempts=max_retries,
            last_error=last_error or "Max retries exhausted",
        ))
        return None
    
    def cleanup(self) -> None:
        """Clean up all resources."""
        self.sandbox_manager.cleanup_all()


def load_manifest(manifest_path: Path) -> list[Problem]:
    """
    Load problems from a manifest file.
    
    Args:
        manifest_path: Path to the manifest.json file
    
    Returns:
        List of Problem objects
    """
    with open(manifest_path, 'r') as f:
        data = json.load(f)
    
    problems = []
    for p in data.get("priority_problems", []):
        problems.append(Problem(
            id=p["id"],
            path=p["path"],
            difficulty=p.get("difficulty", "Unknown"),
            maintainer_note=p.get("maintainer_note", "")
        ))
    
    return problems


def main():
    """Main entry point for the solver."""
    import argparse

    parser = argparse.ArgumentParser(description="Erdos Proof Mining System")
    parser.add_argument("--config", type=Path, help="Path to configuration file")
    parser.add_argument("--manifest", type=Path, default=Path("manifest.json"), help="Path to problem manifest")
    parser.add_argument("--problem-id", type=str, help="Solve a specific problem by ID")
    parser.add_argument("--json-logs", action="store_true", help="Output JSON Lines for GUI consumption")
    parser.add_argument("--list-solutions", action="store_true", help="List all packaged solutions")
    parser.add_argument("--view", type=str, metavar="PROBLEM_ID", help="View details of a solution")

    args = parser.parse_args()

    # Configure logging
    setup_logging(json_mode=args.json_logs)

    # Handle solution queries (no LLM needed)
    if args.list_solutions or args.view:
        from .packager import list_solutions, get_solution
        if args.list_solutions:
            solutions = list_solutions()
            if not solutions:
                print("No solutions found.")
                return
            for s in solutions:
                elegant = " [elegant]" if s.get("is_elegant") else ""
                print(f"  {s['problem_id']:20s}  {s.get('timestamp', '?'):25s}  "
                      f"{s.get('attempts', '?')} attempts  ${s.get('cost_usd', 0):.4f}{elegant}")
            return
        if args.view:
            solution = get_solution(args.view)
            if not solution:
                print(f"No solution found for: {args.view}")
                return
            print(json.dumps(solution, indent=2, default=str))
            return

    # Load configuration
    if args.config and args.config.exists():
        config = Config.from_file(args.config)
    else:
        config = Config.from_env()

    config.solver.ensure_directories()

    # Create LLM provider
    try:
        llm = create_provider(config)
        logger.info(f"Using provider: {llm!r}")
    except Exception as e:
        logger.error(f"Failed to initialize LLM provider: {e}")
        llm = MockLLMProvider()

    solver = Solver(config, llm)
    start_time = time.time()
    solved = 0
    failed = 0

    try:
        if args.manifest.exists():
            problems = load_manifest(args.manifest)
        else:
            logger.error(f"Manifest not found: {args.manifest}")
            return

        if args.problem_id:
            problems = [p for p in problems if p.id == args.problem_id]
            if not problems:
                logger.error(f"Problem not found: {args.problem_id}")
                return

        for problem in problems:
            result = solver.process_problem(problem)

            if result:
                solved += 1
                output_path = config.solver.work_dir / f"solution_{problem.id}.json"
                with open(output_path, 'w') as f:
                    json.dump(result.to_dict(), f, indent=2)
                logger.info(f"Solution saved to: {output_path}")

                # Package into ZIP bundle
                try:
                    from .packager import package_artifact
                    zip_path = package_artifact(
                        result,
                        model_name=config.llm.model,
                        cost_usd=config.cost.current_spent,
                    )
                    logger.info(f"Solution packaged: {zip_path}")
                except Exception as e:
                    logger.warning(f"Failed to package solution: {e}")
            else:
                failed += 1

            remaining = config.cost.remaining_budget()
            logger.info(f"Remaining budget: ${remaining:.2f}")

            if remaining <= 0:
                logger.warning("Budget exhausted, stopping")
                break

        # Emit mining complete summary
        emit_event(MiningComplete(
            total_problems=len(problems),
            solved=solved,
            failed=failed,
            total_cost_usd=config.cost.current_spent,
            duration_seconds=time.time() - start_time,
        ))

    finally:
        solver.cleanup()


if __name__ == "__main__":
    main()
