"""
Logging configuration module for LLM Traffic Signal Cycle Benchmark.

Provides logging setup using loguru for both terminal and file output.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logging(level: str = "info", log_file: Path | None = None) -> None:
    """Configure loguru logger for benchmark runs.

    Removes all existing handlers and adds custom handlers for terminal
    and optional file output.

    Args:
        level: Logging level, either "info" or "debug".
               "info" shows INFO, WARNING, ERROR
               "debug" shows DEBUG, INFO, WARNING, ERROR
        log_file: Optional path to log file. If provided, adds file handler.

    Example:
        >>> from TSC_CYCLE.benchmark.logger import setup_logging
        >>> from pathlib import Path
        >>> setup_logging("debug", Path("benchmark/results/run.log"))
    """
    # Remove all existing handlers
    logger.remove()

    # Define log format
    log_format = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"

    # Determine log level
    log_level = "DEBUG" if level == "debug" else "INFO"

    # Add terminal handler (stdout)
    logger.add(
        sys.stdout,
        format=log_format,
        level=log_level,
        colorize=True
    )

    # Add file handler if log_file is provided
    if log_file is not None:
        # Ensure parent directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            str(log_file),
            format=log_format,
            level=log_level,
            colorize=False,
            encoding="utf-8"
        )
