"""Tests for the event system."""

import json
from io import StringIO
from unittest.mock import patch

from src.events import (
    emit_event, ProblemStarted, CostUpdate, AttemptResult,
    SolutionFound, ProblemFailed, MiningComplete,
)


class TestEvents:
    """Tests for event emission."""

    def test_problem_started_event(self):
        """Test ProblemStarted event serialization."""
        event = ProblemStarted(problem_id="test-01", difficulty="Easy", max_retries=5)
        assert event.type == "problem_started"
        assert event.problem_id == "test-01"

    def test_cost_update_event(self):
        """Test CostUpdate event fields."""
        event = CostUpdate(
            cost_usd=0.01, total_spent_usd=0.05,
            remaining_usd=4.95, input_tokens=100, output_tokens=50,
        )
        assert event.type == "cost_update"
        assert event.cost_usd == 0.01

    def test_solution_found_event(self):
        """Test SolutionFound event."""
        event = SolutionFound(
            problem_id="p1", attempts=3,
            proof_preview="theorem ...", is_elegant=True,
        )
        assert event.type == "solution_found"
        assert event.is_elegant is True

    def test_mining_complete_event(self):
        """Test MiningComplete event."""
        event = MiningComplete(
            total_problems=10, solved=7, failed=3,
            total_cost_usd=2.50, duration_seconds=120.0,
        )
        assert event.type == "mining_complete"
        assert event.solved == 7

    def test_emit_event_outputs_json(self):
        """Test that emit_event outputs valid JSON line."""
        event = ProblemStarted(problem_id="test-01")
        buf = StringIO()
        with patch('builtins.print', side_effect=lambda *a, **kw: buf.write(a[0])):
            emit_event(event)
        data = json.loads(buf.getvalue())
        assert data["type"] == "problem_started"
        assert data["problem_id"] == "test-01"
        assert "timestamp" in data


class TestLoggingConfig:
    """Tests for logging configuration."""

    def test_json_formatter(self):
        """Test JSON log formatter."""
        from src.logging_config import JsonFormatter
        import logging

        formatter = JsonFormatter()
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "Test message", (), None
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["type"] == "log"
        assert data["level"] == "info"
        assert data["message"] == "Test message"

    def test_human_formatter(self):
        """Test human-readable formatter."""
        from src.logging_config import HumanFormatter
        import logging

        formatter = HumanFormatter()
        record = logging.LogRecord(
            "test", logging.WARNING, "", 0, "Watch out", (), None
        )
        output = formatter.format(record)
        assert "[W]" in output
        assert "Watch out" in output

    def test_setup_logging_json_mode(self):
        """Test that setup_logging configures JSON mode."""
        from src.logging_config import setup_logging, JsonFormatter
        import logging

        setup_logging(json_mode=True)
        root = logging.getLogger()
        assert any(
            isinstance(h.formatter, JsonFormatter)
            for h in root.handlers
        )
        # Restore default
        setup_logging(json_mode=False)
