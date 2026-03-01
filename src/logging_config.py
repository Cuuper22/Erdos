"""Structured logging for the Erdos Proof Mining System.

Supports two output modes:
- Human-readable (default CLI mode)
- JSON Lines (for GUI/Tauri IPC parsing)
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional


class JsonFormatter(logging.Formatter):
    """Log formatter that outputs JSON Lines."""

    LEVEL_MAP = {
        "DEBUG": "debug",
        "INFO": "info",
        "WARNING": "warning",
        "ERROR": "error",
        "CRITICAL": "error",
    }

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "type": "log",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": self.LEVEL_MAP.get(record.levelname, "info"),
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Include structured data if attached to the record
        if hasattr(record, "data") and record.data:
            entry["data"] = record.data

        return json.dumps(entry, default=str)


class HumanFormatter(logging.Formatter):
    """Clean human-readable formatter for CLI."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%H:%M:%S")
        level = record.levelname[0]  # D, I, W, E, C
        msg = record.getMessage()
        return f"{ts} [{level}] {msg}"


def setup_logging(json_mode: bool = False, level: int = logging.INFO) -> None:
    """Configure logging for the application.

    Args:
        json_mode: If True, output JSON Lines to stdout.
        level: Logging level.
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if json_mode:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(HumanFormatter())

    root.addHandler(handler)


def log_with_data(
    logger: logging.Logger,
    level: int,
    message: str,
    data: Optional[dict[str, Any]] = None,
) -> None:
    """Log a message with optional structured data.

    In JSON mode, data appears in the 'data' field.
    In human mode, data is ignored (message should be self-explanatory).
    """
    record = logger.makeRecord(
        logger.name, level, "(unknown)", 0, message, (), None
    )
    if data:
        record.data = data
    logger.handle(record)
