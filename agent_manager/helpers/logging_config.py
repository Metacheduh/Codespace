"""
Structured JSON logging configuration for Agent Manager.

Logs are output as JSON to stdout and optionally to a file,
making them easy to parse and aggregate with log aggregation services.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

try:
    from pythonjsonlogger import jsonlogger
except ImportError:
    jsonlogger = None  # type: ignore


def setup_logging(
    log_file: str | Path | None = None,
    level: int = logging.INFO,
    json_format: bool = True,
) -> None:
    """Configure structured JSON logging.

    Args:
        log_file: Optional file path for logging. If None, logs to stdout only.
        level: Logging level (default: INFO).
        json_format: If True, use JSON format; if False, use plain text.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers = []

    if json_format and jsonlogger:
        formatter = jsonlogger.JsonFormatter(
            fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
            timestamp=True,
        )
    else:
        formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        )

    # Stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)

    # File handler (if log_file specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            str(log_path),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


class StructuredLogger:
    """Helper class for structured logging with context."""

    def __init__(self, name: str) -> None:
        self.logger = logging.getLogger(name)

    def info(self, message: str, **context: Any) -> None:
        """Log info with structured context."""
        if context:
            self.logger.info(f"{message} | {json.dumps(context, default=str)}")
        else:
            self.logger.info(message)

    def warning(self, message: str, **context: Any) -> None:
        """Log warning with structured context."""
        if context:
            self.logger.warning(f"{message} | {json.dumps(context, default=str)}")
        else:
            self.logger.warning(message)

    def error(self, message: str, **context: Any) -> None:
        """Log error with structured context."""
        if context:
            self.logger.error(f"{message} | {json.dumps(context, default=str)}")
        else:
            self.logger.error(message)

    def debug(self, message: str, **context: Any) -> None:
        """Log debug with structured context."""
        if context:
            self.logger.debug(f"{message} | {json.dumps(context, default=str)}")
        else:
            self.logger.debug(message)
