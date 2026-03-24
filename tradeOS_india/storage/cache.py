"""
TradeOS India — Polars parquet cache for candles and contracts.

Provides fast read/write of OHLCV candle data and master contract lists
using parquet format via Polars for high-performance columnar access.
"""

from pathlib import Path
from typing import Optional

import polars as pl

from config.settings import get_settings
from utils.logger import get_logger

log = get_logger("storage.cache")


# ═════════════════════════════════════════════════════════════════
# Contract cache
# ═════════════════════════════════════════════════════════════════

def _contracts_dir() -> Path:
    """Return the contracts cache directory, creating it if needed."""
    path = Path(get_settings().contracts_cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_contracts(segment: str, df: pl.DataFrame) -> Path:
    """Save a contracts DataFrame to parquet.

    Args:
        segment: Segment identifier (e.g. 'NSE_CM', 'NSE_FO').
        df: Polars DataFrame with contract data.

    Returns:
        Path to the saved parquet file.
    """
    file_path = _contracts_dir() / f"{segment}.parquet"
    try:
        df.write_parquet(str(file_path))
        log.info(f"Contracts cached: {segment} ({len(df)} rows) -> {file_path}")
    except Exception as exc:
        log.error(f"Failed to cache contracts for {segment}: {exc}")
        raise
    return file_path


def load_contracts(segment: str) -> Optional[pl.DataFrame]:
    """Load contracts from parquet cache.

    Args:
        segment: Segment identifier.

    Returns:
        Polars DataFrame or None if cache miss.
    """
    file_path = _contracts_dir() / f"{segment}.parquet"
    if not file_path.exists():
        log.debug(f"No contract cache for {segment}")
        return None

    try:
        df = pl.read_parquet(str(file_path))
        log.debug(f"Contracts loaded: {segment} ({len(df)} rows)")
        return df
    except Exception as exc:
        log.error(f"Failed to load contract cache for {segment}: {exc}")
        return None


def contracts_cache_age_hours(segment: str) -> Optional[float]:
    """Return the age of the contract cache file in hours.

    Args:
        segment: Segment identifier.

    Returns:
        Age in hours, or None if file doesn't exist.
    """
    import time

    file_path = _contracts_dir() / f"{segment}.parquet"
    if not file_path.exists():
        return None

    age_sec = time.time() - file_path.stat().st_mtime
    return age_sec / 3600.0


def is_contracts_stale(segment: str, max_age_hours: float = 24.0) -> bool:
    """Check if the contract cache is older than the threshold.

    Args:
        segment: Segment identifier.
        max_age_hours: Maximum acceptable age in hours.

    Returns:
        True if cache is stale or doesn't exist.
    """
    age = contracts_cache_age_hours(segment)
    if age is None:
        return True
    return age > max_age_hours


# ═════════════════════════════════════════════════════════════════
# Candle cache
# ═════════════════════════════════════════════════════════════════

def _candles_dir() -> Path:
    """Return the candles cache directory, creating it if needed."""
    path = Path(get_settings().candles_cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _candle_key(symbol: str, timeframe: str) -> str:
    """Generate a safe filename key from symbol and timeframe."""
    safe_symbol = symbol.replace(":", "_").replace("/", "_").replace("\\", "_")
    return f"{safe_symbol}_{timeframe}"


def save_candles(
    symbol: str,
    timeframe: str,
    df: pl.DataFrame,
) -> Path:
    """Save OHLCV candle data to parquet.

    Args:
        symbol: Trading symbol (e.g. 'NSE:RELIANCE-EQ').
        timeframe: Candle timeframe (e.g. '1m', '5m', '1D').
        df: Polars DataFrame with OHLCV columns.

    Returns:
        Path to the saved parquet file.
    """
    key = _candle_key(symbol, timeframe)
    file_path = _candles_dir() / f"{key}.parquet"
    try:
        df.write_parquet(str(file_path))
        log.debug(f"Candles cached: {symbol} {timeframe} ({len(df)} rows)")
    except Exception as exc:
        log.error(f"Failed to cache candles {symbol} {timeframe}: {exc}")
        raise
    return file_path


def load_candles(
    symbol: str,
    timeframe: str,
) -> Optional[pl.DataFrame]:
    """Load OHLCV candle data from parquet cache.

    Args:
        symbol: Trading symbol.
        timeframe: Candle timeframe.

    Returns:
        Polars DataFrame or None if cache miss.
    """
    key = _candle_key(symbol, timeframe)
    file_path = _candles_dir() / f"{key}.parquet"
    if not file_path.exists():
        return None

    try:
        df = pl.read_parquet(str(file_path))
        log.debug(f"Candles loaded: {symbol} {timeframe} ({len(df)} rows)")
        return df
    except Exception as exc:
        log.error(f"Failed to load candle cache {symbol} {timeframe}: {exc}")
        return None


def append_candles(
    symbol: str,
    timeframe: str,
    new_df: pl.DataFrame,
) -> pl.DataFrame:
    """Append new candles to existing cache, deduplicating by timestamp.

    Args:
        symbol: Trading symbol.
        timeframe: Candle timeframe.
        new_df: New candle data to append.

    Returns:
        The merged DataFrame (also saved to cache).
    """
    existing = load_candles(symbol, timeframe)
    if existing is not None:
        merged = pl.concat([existing, new_df]).unique(
            subset=["timestamp"], keep="last"
        ).sort("timestamp")
    else:
        merged = new_df.sort("timestamp")

    save_candles(symbol, timeframe, merged)
    return merged


def clear_cache(cache_type: str = "all") -> int:
    """Clear cached parquet files.

    Args:
        cache_type: 'contracts', 'candles', or 'all'.

    Returns:
        Number of files deleted.
    """
    count = 0
    dirs: list[Path] = []

    if cache_type in ("contracts", "all"):
        dirs.append(_contracts_dir())
    if cache_type in ("candles", "all"):
        dirs.append(_candles_dir())

    for cache_dir in dirs:
        for f in cache_dir.glob("*.parquet"):
            try:
                f.unlink()
                count += 1
            except Exception as exc:
                log.error(f"Failed to delete {f}: {exc}")

    log.info(f"Cache cleared: {cache_type} — {count} files deleted")
    return count


__all__ = [
    "save_contracts",
    "load_contracts",
    "contracts_cache_age_hours",
    "is_contracts_stale",
    "save_candles",
    "load_candles",
    "append_candles",
    "clear_cache",
]
