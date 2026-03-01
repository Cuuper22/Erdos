"""
Campaign management for the Erdos Proof Mining System.

Tracks problem attempt history, manages prioritization,
and persists completion data across sessions.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_DIR = Path.home() / ".erdos-prover"
HISTORY_FILENAME = "history.json"


@dataclass
class AttemptRecord:
    """Record of a single problem attempt."""
    timestamp: str
    result: str  # "solved", "failed", "skipped"
    attempts: int = 0
    cost_usd: float = 0.0
    error: str = ""


@dataclass
class ProblemHistory:
    """History for a single problem."""
    problem_id: str
    solved: bool = False
    total_attempts: int = 0
    total_cost_usd: float = 0.0
    records: list[AttemptRecord] = field(default_factory=list)

    @property
    def last_attempted(self) -> Optional[str]:
        if self.records:
            return self.records[-1].timestamp
        return None


class CampaignManager:
    """Manages problem prioritization and completion tracking."""

    def __init__(self, history_dir: Optional[Path] = None):
        self.history_dir = history_dir or DEFAULT_HISTORY_DIR
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self._history: dict[str, ProblemHistory] = {}
        self._load_history()

    @property
    def history_file(self) -> Path:
        return self.history_dir / HISTORY_FILENAME

    def _load_history(self) -> None:
        """Load history from disk."""
        if not self.history_file.exists():
            return
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for pid, entry in data.items():
                records = [AttemptRecord(**r) for r in entry.get("records", [])]
                self._history[pid] = ProblemHistory(
                    problem_id=pid,
                    solved=entry.get("solved", False),
                    total_attempts=entry.get("total_attempts", 0),
                    total_cost_usd=entry.get("total_cost_usd", 0.0),
                    records=records,
                )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load history: {e}")

    def _save_history(self) -> None:
        """Save history to disk."""
        data = {}
        for pid, ph in self._history.items():
            data[pid] = {
                "solved": ph.solved,
                "total_attempts": ph.total_attempts,
                "total_cost_usd": ph.total_cost_usd,
                "records": [asdict(r) for r in ph.records],
            }
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def record_attempt(
        self,
        problem_id: str,
        result: str,
        attempts: int = 0,
        cost_usd: float = 0.0,
        error: str = "",
    ) -> None:
        """Record a problem attempt result."""
        if problem_id not in self._history:
            self._history[problem_id] = ProblemHistory(problem_id=problem_id)

        ph = self._history[problem_id]
        record = AttemptRecord(
            timestamp=datetime.now().isoformat(),
            result=result,
            attempts=attempts,
            cost_usd=cost_usd,
            error=error,
        )
        ph.records.append(record)
        ph.total_attempts += attempts
        ph.total_cost_usd += cost_usd

        if result == "solved":
            ph.solved = True

        self._save_history()

    def is_solved(self, problem_id: str) -> bool:
        """Check if a problem has been solved."""
        ph = self._history.get(problem_id)
        return ph.solved if ph else False

    def get_history(self, problem_id: str) -> Optional[ProblemHistory]:
        """Get history for a specific problem."""
        return self._history.get(problem_id)

    def get_all_history(self) -> dict[str, ProblemHistory]:
        """Get all problem histories."""
        return dict(self._history)

    def get_solved_ids(self) -> set[str]:
        """Get the set of solved problem IDs."""
        return {pid for pid, ph in self._history.items() if ph.solved}

    def filter_unsolved(
        self,
        problem_ids: list[str],
        force: bool = False,
    ) -> list[str]:
        """Filter out already-solved problems.

        Args:
            problem_ids: List of problem IDs to filter
            force: If True, include solved problems too

        Returns:
            List of unsolved problem IDs (preserving order)
        """
        if force:
            return problem_ids
        solved = self.get_solved_ids()
        return [pid for pid in problem_ids if pid not in solved]

    def prioritize_problems(
        self,
        problems: list,
        force: bool = False,
    ) -> list:
        """Prioritize problems: unsolved first, then by manifest order.

        Args:
            problems: List of problem objects with .id attribute
            force: If True, include solved problems

        Returns:
            Reordered list with unsolved problems first
        """
        solved = self.get_solved_ids()

        if force:
            return list(problems)

        unsolved = [p for p in problems if p.id not in solved]
        already_solved = [p for p in problems if p.id in solved]

        return unsolved + already_solved

    def summary(self) -> dict:
        """Get a summary of campaign progress."""
        total = len(self._history)
        solved = sum(1 for ph in self._history.values() if ph.solved)
        total_cost = sum(ph.total_cost_usd for ph in self._history.values())
        total_attempts = sum(ph.total_attempts for ph in self._history.values())

        return {
            "total_problems": total,
            "solved": solved,
            "failed": total - solved,
            "total_attempts": total_attempts,
            "total_cost_usd": total_cost,
        }
