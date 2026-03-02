"""Lightweight timestamped logger for CLI diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable
import sys


def log_info(message: str, *, verbose: bool = True) -> None:
    """Log informational message to stderr with timestamp."""
    if verbose:
        print(f"[{_ts()}] INFO  {message}", file=sys.stderr)


def log_warn(message: str, *, verbose: bool = True) -> None:
    """Log warning message to stderr with timestamp."""
    if verbose:
        print(f"[{_ts()}] WARN  {message}", file=sys.stderr)


def log_error(message: str, *, verbose: bool = True) -> None:
    """Log error message to stderr with timestamp."""
    if verbose:
        print(f"[{_ts()}] ERROR {message}", file=sys.stderr)


def log_lines(lines: Iterable[str], *, prefix: str, verbose: bool = True) -> None:
    """Log multiple lines with timestamp and custom prefix."""
    if not verbose:
        return
    for line in lines:
        print(f"[{_ts()}] {prefix} {line}", file=sys.stderr)


def _ts() -> str:
    """Current local timestamp in HH:MM:SS format."""
    return datetime.now().strftime("%H:%M:%S")
