"""
TradeOS India — IST date/time helpers and market hours checks.

All time operations in the app use IST (UTC+05:30).
"""

from datetime import datetime, time, timedelta
from typing import Optional

import pytz
from dateutil import parser as dateutil_parser

# ─── IST timezone ────────────────────────────────────────────────
IST = pytz.timezone("Asia/Kolkata")

# ─── Market hours ────────────────────────────────────────────────
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
PRE_OPEN_START = time(9, 0)
PRE_OPEN_END = time(9, 15)
MCX_CLOSE = time(23, 30)

# ─── Weekend days (Saturday=5, Sunday=6) ─────────────────────────
WEEKEND_DAYS = {5, 6}


def now_ist() -> datetime:
    """Return the current datetime in IST."""
    return datetime.now(IST)


def today_ist() -> str:
    """Return today's date as 'YYYY-MM-DD' string in IST."""
    return now_ist().strftime("%Y-%m-%d")


def ist_timestamp() -> str:
    """Return current IST datetime as 'YYYY-MM-DD HH:MM:SS' string."""
    return now_ist().strftime("%Y-%m-%d %H:%M:%S")


def ist_time_str() -> str:
    """Return current IST time as 'HH:MM:SS' string for status bar."""
    return now_ist().strftime("%H:%M:%S")


def is_market_open(segment: str = "NSE") -> bool:
    """Check if the Indian equity market is currently open.

    Args:
        segment: Market segment — 'NSE', 'BSE', 'NFO', 'CDS', 'MCX'.

    Returns:
        True if within trading hours on a weekday.
    """
    dt = now_ist()
    if dt.weekday() in WEEKEND_DAYS:
        return False

    current_time = dt.time()

    if segment == "MCX":
        return MARKET_OPEN <= current_time <= MCX_CLOSE

    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def is_pre_open() -> bool:
    """Check if we are in the NSE pre-open session (09:00–09:15 IST)."""
    dt = now_ist()
    if dt.weekday() in WEEKEND_DAYS:
        return False
    return PRE_OPEN_START <= dt.time() < PRE_OPEN_END


def is_market_hours() -> bool:
    """Check if current time is within broad market hours (9:15–15:30 IST).

    Used for LLM provider selection (primary during hours, overnight otherwise).
    """
    dt = now_ist()
    if dt.weekday() in WEEKEND_DAYS:
        return False
    return MARKET_OPEN <= dt.time() <= MARKET_CLOSE


def seconds_to_market_open() -> Optional[int]:
    """Return seconds until next market open, or None if market is open."""
    if is_market_open():
        return None

    dt = now_ist()
    open_today = dt.replace(
        hour=MARKET_OPEN.hour,
        minute=MARKET_OPEN.minute,
        second=0,
        microsecond=0,
    )

    if dt.time() > MARKET_CLOSE:
        # After close — next open is tomorrow (skip weekends)
        open_today += timedelta(days=1)

    while open_today.weekday() in WEEKEND_DAYS:
        open_today += timedelta(days=1)

    return int((open_today - dt).total_seconds())


def parse_datetime(value: str) -> datetime:
    """Parse a datetime string into an IST-aware datetime.

    Args:
        value: Datetime string in any common format.

    Returns:
        IST-localized datetime.
    """
    dt = dateutil_parser.parse(value)
    if dt.tzinfo is None:
        dt = IST.localize(dt)
    else:
        dt = dt.astimezone(IST)
    return dt


def format_date(dt: datetime, fmt: str = "%Y-%m-%d") -> str:
    """Format a datetime to string."""
    return dt.strftime(fmt)


def trading_day() -> str:
    """Return the current trading day as 'YYYY-MM-DD'.

    If before market open, returns today.
    If after market close, still returns today (trades belong to today).
    On weekends, returns the last Friday.
    """
    dt = now_ist()
    while dt.weekday() in WEEKEND_DAYS:
        dt -= timedelta(days=1)
    return dt.strftime("%Y-%m-%d")


__all__ = [
    "IST",
    "MARKET_OPEN",
    "MARKET_CLOSE",
    "now_ist",
    "today_ist",
    "ist_timestamp",
    "ist_time_str",
    "is_market_open",
    "is_pre_open",
    "is_market_hours",
    "seconds_to_market_open",
    "parse_datetime",
    "format_date",
    "trading_day",
]
