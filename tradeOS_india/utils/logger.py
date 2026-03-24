"""
TradeOS India — Centralized logging configuration.

Uses loguru with IST timestamps, rotating file output, and colored console output.
All modules should import `logger` from this module.
"""

import sys
from pathlib import Path

from loguru import logger

# ─── Log directory ───────────────────────────────────────────────
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ─── IST format string ──────────────────────────────────────────
LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} IST | {level:<8} | "
    "{name:<30} | {message}"
)

# ─── Remove default loguru handler ──────────────────────────────
logger.remove()

# ─── Console handler — colored, INFO+ ───────────────────────────
logger.add(
    sys.stdout,
    format=LOG_FORMAT,
    level="INFO",
    colorize=True,
    backtrace=True,
    diagnose=False,
)

# ─── File handler — rotating 10 MB, 7-day retention ─────────────
logger.add(
    str(LOG_DIR / "tradeos_{time:YYYY-MM-DD}.log"),
    format=LOG_FORMAT,
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",
    encoding="utf-8",
    backtrace=True,
    diagnose=False,
)


def get_logger(name: str) -> "logger":
    """Return a logger bound to the given module name."""
    return logger.bind(name=name)


__all__ = ["logger", "get_logger", "LOG_DIR"]
