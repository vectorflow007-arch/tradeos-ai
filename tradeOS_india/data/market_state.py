"""
TradeOS India — Thread-safe singleton holding latest ticks and candles.

Provides fast, lock-protected access to the most recent market data
for any subscribed symbol. Candles are stored as Polars DataFrames.
"""

import threading
from typing import Any, Optional

import polars as pl

from utils.logger import get_logger

log = get_logger("data.market_state")

# ─── Candle DataFrame schema ────────────────────────────────────
CANDLE_SCHEMA = {
    "timestamp": pl.Int64,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Int64,
}


class MarketState:
    """Thread-safe singleton holding the latest market data.

    Stores:
      - Latest tick per symbol (dict)
      - OHLCV candles per symbol+timeframe (Polars DataFrame)

    All reads/writes are protected by a threading.Lock.
    """

    _instance: Optional["MarketState"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._ticks: dict[str, dict[str, Any]] = {}
        self._candles: dict[str, pl.DataFrame] = {}
        self._data_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "MarketState":
        """Return the singleton MarketState instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = MarketState()
                    log.info("MarketState singleton created")
        return cls._instance

    # ═════════════════════════════════════════════════════════════
    # Ticks
    # ═════════════════════════════════════════════════════════════

    def update_tick(self, symbol: str, tick_data: dict[str, Any]) -> None:
        """Update the latest tick for a symbol.

        Args:
            symbol: Trading symbol (e.g. 'NSE:RELIANCE-EQ').
            tick_data: Dict with ltp, open, high, low, close, volume, etc.
        """
        with self._data_lock:
            self._ticks[symbol] = tick_data

    def get_tick(self, symbol: str) -> Optional[dict[str, Any]]:
        """Get the latest tick for a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            Tick dict or None if no data.
        """
        with self._data_lock:
            return self._ticks.get(symbol)

    def get_all_ticks(self) -> dict[str, dict[str, Any]]:
        """Get a snapshot of all latest ticks.

        Returns:
            Dict mapping symbol -> tick_data.
        """
        with self._data_lock:
            return dict(self._ticks)

    def get_ltp(self, symbol: str) -> float:
        """Get the last traded price for a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            LTP float, or 0.0 if not available.
        """
        with self._data_lock:
            tick = self._ticks.get(symbol)
            return tick.get("ltp", 0.0) if tick else 0.0

    # ═════════════════════════════════════════════════════════════
    # Candles
    # ═════════════════════════════════════════════════════════════

    def _candle_key(self, symbol: str, timeframe: str) -> str:
        """Build internal key for candle storage."""
        return f"{symbol}|{timeframe}"

    def update_candles(
        self,
        symbol: str,
        timeframe: str,
        df: pl.DataFrame,
    ) -> None:
        """Replace the full candle DataFrame for a symbol+timeframe.

        Args:
            symbol: Trading symbol.
            timeframe: Candle timeframe ('1m', '5m', etc.).
            df: Polars DataFrame with OHLCV columns.
        """
        key = self._candle_key(symbol, timeframe)
        with self._data_lock:
            self._candles[key] = df

    def append_candle(
        self,
        symbol: str,
        timeframe: str,
        candle: dict[str, Any],
    ) -> None:
        """Append a single candle row to the DataFrame.

        Args:
            symbol: Trading symbol.
            timeframe: Candle timeframe.
            candle: Dict with timestamp, open, high, low, close, volume.
        """
        key = self._candle_key(symbol, timeframe)
        new_row = pl.DataFrame(
            {k: [candle.get(k, 0)] for k in CANDLE_SCHEMA},
            schema=CANDLE_SCHEMA,
        )

        with self._data_lock:
            existing = self._candles.get(key)
            if existing is not None:
                self._candles[key] = pl.concat([existing, new_row])
            else:
                self._candles[key] = new_row

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        last_n: Optional[int] = None,
    ) -> pl.DataFrame:
        """Get candle data for a symbol+timeframe.

        Args:
            symbol: Trading symbol.
            timeframe: Candle timeframe.
            last_n: If set, return only the last N candles.

        Returns:
            Polars DataFrame (empty if no data).
        """
        key = self._candle_key(symbol, timeframe)
        with self._data_lock:
            df = self._candles.get(key)
            if df is None:
                return pl.DataFrame(schema=CANDLE_SCHEMA)
            if last_n is not None and last_n < len(df):
                return df.tail(last_n)
            return df

    def get_latest_candle(
        self,
        symbol: str,
        timeframe: str,
    ) -> Optional[dict[str, Any]]:
        """Get the most recent candle as a dict.

        Args:
            symbol: Trading symbol.
            timeframe: Candle timeframe.

        Returns:
            Candle dict or None.
        """
        key = self._candle_key(symbol, timeframe)
        with self._data_lock:
            df = self._candles.get(key)
            if df is None or len(df) == 0:
                return None
            return df.tail(1).to_dicts()[0]

    # ═════════════════════════════════════════════════════════════
    # Housekeeping
    # ═════════════════════════════════════════════════════════════

    def clear_symbol(self, symbol: str) -> None:
        """Remove all data for a symbol.

        Args:
            symbol: Trading symbol to clear.
        """
        with self._data_lock:
            self._ticks.pop(symbol, None)
            keys_to_remove = [
                k for k in self._candles if k.startswith(f"{symbol}|")
            ]
            for k in keys_to_remove:
                del self._candles[k]

    def clear_all(self) -> None:
        """Remove all ticks and candles."""
        with self._data_lock:
            self._ticks.clear()
            self._candles.clear()
        log.info("MarketState cleared")

    def get_subscribed_symbols(self) -> list[str]:
        """Return list of symbols with tick data."""
        with self._data_lock:
            return list(self._ticks.keys())

    def get_candle_timeframes(self, symbol: str) -> list[str]:
        """Return list of timeframes available for a symbol."""
        prefix = f"{symbol}|"
        with self._data_lock:
            return [
                k.split("|", 1)[1]
                for k in self._candles
                if k.startswith(prefix)
            ]


__all__ = ["MarketState", "CANDLE_SCHEMA"]
