"""Tests for the campaign management module."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from src.campaign import CampaignManager, ProblemHistory, AttemptRecord


class TestCampaignManager:
    """Test campaign initialization and persistence."""

    def test_creates_history_dir(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path / "new_dir")
        assert (tmp_path / "new_dir").exists()

    def test_empty_history(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path)
        assert mgr.get_all_history() == {}

    def test_load_persisted_history(self, tmp_path):
        # Write history manually
        history = {
            "P001": {
                "solved": True,
                "total_attempts": 3,
                "total_cost_usd": 0.05,
                "records": [
                    {"timestamp": "2026-01-01", "result": "solved", "attempts": 3,
                     "cost_usd": 0.05, "error": ""},
                ],
            }
        }
        (tmp_path / "history.json").write_text(json.dumps(history))

        mgr = CampaignManager(history_dir=tmp_path)
        assert mgr.is_solved("P001")
        ph = mgr.get_history("P001")
        assert ph.total_attempts == 3


class TestRecordAttempt:
    """Test attempt recording."""

    def test_record_solved(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path)
        mgr.record_attempt("P001", result="solved", attempts=5, cost_usd=0.10)

        assert mgr.is_solved("P001")
        ph = mgr.get_history("P001")
        assert ph.total_attempts == 5
        assert ph.total_cost_usd == 0.10
        assert len(ph.records) == 1

    def test_record_failed(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path)
        mgr.record_attempt("P001", result="failed", attempts=10, error="Budget exhausted")

        assert not mgr.is_solved("P001")
        ph = mgr.get_history("P001")
        assert ph.records[0].error == "Budget exhausted"

    def test_multiple_attempts(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path)
        mgr.record_attempt("P001", result="failed", attempts=5, cost_usd=0.05)
        mgr.record_attempt("P001", result="solved", attempts=3, cost_usd=0.03)

        ph = mgr.get_history("P001")
        assert ph.solved
        assert ph.total_attempts == 8
        assert abs(ph.total_cost_usd - 0.08) < 0.001
        assert len(ph.records) == 2

    def test_persists_to_disk(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path)
        mgr.record_attempt("P001", result="solved", attempts=1)

        # Load fresh
        mgr2 = CampaignManager(history_dir=tmp_path)
        assert mgr2.is_solved("P001")


class TestFilterAndPrioritize:
    """Test problem filtering and prioritization."""

    def test_filter_unsolved(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path)
        mgr.record_attempt("P001", result="solved", attempts=1)

        result = mgr.filter_unsolved(["P001", "P002", "P003"])
        assert result == ["P002", "P003"]

    def test_filter_force_includes_all(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path)
        mgr.record_attempt("P001", result="solved", attempts=1)

        result = mgr.filter_unsolved(["P001", "P002"], force=True)
        assert result == ["P001", "P002"]

    def test_prioritize_unsolved_first(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path)
        mgr.record_attempt("P001", result="solved", attempts=1)

        problems = [
            MagicMock(id="P001"),
            MagicMock(id="P002"),
            MagicMock(id="P003"),
        ]
        ordered = mgr.prioritize_problems(problems)
        ids = [p.id for p in ordered]
        assert ids == ["P002", "P003", "P001"]

    def test_prioritize_force_keeps_order(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path)
        mgr.record_attempt("P001", result="solved", attempts=1)

        problems = [MagicMock(id="P001"), MagicMock(id="P002")]
        ordered = mgr.prioritize_problems(problems, force=True)
        ids = [p.id for p in ordered]
        assert ids == ["P001", "P002"]


class TestSolvedTracking:
    """Test solved problem tracking."""

    def test_get_solved_ids(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path)
        mgr.record_attempt("P001", result="solved", attempts=1)
        mgr.record_attempt("P002", result="failed", attempts=5)
        mgr.record_attempt("P003", result="solved", attempts=2)

        solved = mgr.get_solved_ids()
        assert solved == {"P001", "P003"}

    def test_is_solved_unknown(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path)
        assert not mgr.is_solved("unknown_problem")


class TestSummary:
    """Test campaign summary."""

    def test_summary(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path)
        mgr.record_attempt("P001", result="solved", attempts=3, cost_usd=0.05)
        mgr.record_attempt("P002", result="failed", attempts=10, cost_usd=0.20)

        s = mgr.summary()
        assert s["total_problems"] == 2
        assert s["solved"] == 1
        assert s["failed"] == 1
        assert s["total_attempts"] == 13
        assert abs(s["total_cost_usd"] - 0.25) < 0.001

    def test_empty_summary(self, tmp_path):
        mgr = CampaignManager(history_dir=tmp_path)
        s = mgr.summary()
        assert s["total_problems"] == 0
        assert s["solved"] == 0


class TestProblemHistory:
    """Test ProblemHistory dataclass."""

    def test_last_attempted(self):
        ph = ProblemHistory(
            problem_id="P001",
            records=[
                AttemptRecord(timestamp="2026-01-01", result="failed"),
                AttemptRecord(timestamp="2026-02-01", result="solved"),
            ],
        )
        assert ph.last_attempted == "2026-02-01"

    def test_last_attempted_empty(self):
        ph = ProblemHistory(problem_id="P001")
        assert ph.last_attempted is None
