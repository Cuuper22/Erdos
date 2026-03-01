"""Event system for solver-to-GUI communication.

Events are emitted as JSON Lines on stdout, interleaved with log lines.
Each event has a distinct 'type' field for the Tauri backend to parse.
"""

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProblemStarted:
    type: str = field(default="problem_started", init=False)
    timestamp: str = field(default_factory=_now)
    problem_id: str = ""
    difficulty: str = "Unknown"
    max_retries: int = 0


@dataclass
class CostUpdate:
    type: str = field(default="cost_update", init=False)
    timestamp: str = field(default_factory=_now)
    cost_usd: float = 0.0
    total_spent_usd: float = 0.0
    remaining_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class AttemptResult:
    type: str = field(default="attempt_result", init=False)
    timestamp: str = field(default_factory=_now)
    problem_id: str = ""
    attempt: int = 0
    status: str = ""  # "generated", "integrity_fail", "build_fail", "critic_fail", "critic_pass"
    message: str = ""


@dataclass
class SolutionFound:
    type: str = field(default="solution_found", init=False)
    timestamp: str = field(default_factory=_now)
    problem_id: str = ""
    attempts: int = 0
    proof_preview: str = ""
    is_elegant: bool = False


@dataclass
class ProblemFailed:
    type: str = field(default="problem_failed", init=False)
    timestamp: str = field(default_factory=_now)
    problem_id: str = ""
    attempts: int = 0
    last_error: str = ""


@dataclass
class MiningComplete:
    type: str = field(default="mining_complete", init=False)
    timestamp: str = field(default_factory=_now)
    total_problems: int = 0
    solved: int = 0
    failed: int = 0
    total_cost_usd: float = 0.0
    duration_seconds: float = 0.0


def emit_event(event) -> None:
    """Emit an event as a JSON line on stdout."""
    line = json.dumps(asdict(event), default=str)
    print(line, flush=True)
