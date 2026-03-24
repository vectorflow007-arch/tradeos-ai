"""
TradeOS India — Tick-to-OHLCV candle builder.

Aggregates raw ticks into OHLCV candles at multiple timeframes
(1m, 5m, 15m, 1h, 1D). Emits candle_closed signal when a candle
completes, and updates MarketState.
"""

from typing import Any, Optional

from core.event_bus import EventBus
from data.market_state import MarketState
from utils.logger import get_logger

log = get_logger("data.candle_builder")

# ─── Timeframe durations in seconds ─────────────────────────────
TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "1D": 86400,
}

# Default timeframes to build
DEFAULT_TIMEFRAMES = ["1m", "5m", "15m", "1h", "1D"]


class _CandleAccumulator:
    """Accumulates ticks into a single forming candle."""

    def __init__(self, timeframe: str, duration_s: int) -> None:
        self.timeframe = timeframe
        self.duration_s = duration_s
        self.open: float = 0.0
        self.high: float = 0.0
        self.low: float = 0.0
        self.close: float = 0.0
        self.volume: int = 0
        self.bucket_start: int = 0
        self.tick_count: int = 0

    def _bucket_for(self, timestamp: int) -> int:
        """Calculate the candle bucket start time for a tick timestamp.

        Args:
            timestamp: Unix timestamp of the tick.

        Returns:
            Bucket start timestamp (floored to timeframe boundary).
        """
        return (timestamp // self.duration_s) * self.duration_s

    def process_tick(
        self,
        ltp: float,
        volume: int,
        timestamp: int,
    ) -> Optional[dict[str, Any]]:
        """Process a single tick, returning a closed candle if the bucket rolled.

        Args:
            ltp: Last traded price.
            volume: Tick volume (incremental).
            timestamp: Unix timestamp of the tick.

        Returns:
            Completed candle dict if bucket rolled, else None.
        """
        bucket = self._bucket_for(timestamp)
        closed_candle: Optional[dict[str, Any]] = None

        if self.tick_count == 0:
            # First tick ever — initialize
            self.bucket_start = bucket
            self.open = ltp
            self.high = ltp
            self.low = ltp
            self.close = ltp
            self.volume = volume
            self.tick_count = 1
            return None

        if bucket != self.bucket_start:
            # Bucket rolled — close the current candle
            closed_candle = {
                "timestamp": self.bucket_start,
                "open": self.open,
                "high": self.high,
                "low": self.low,
                "close": self.close,
                "volume": self.volume,
            }

            # Start new candle
            self.bucket_start = bucket
            self.open = ltp
            self.high = ltp
            self.low = ltp
            self.close = ltp
            self.volume = volume
            self.tick_count = 1
        else:
            # Same bucket — update OHLCV
            self.high = max(self.high, ltp)
            self.low = min(self.low, ltp)
            self.close = ltp
            self.volume += volume
            self.tick_count += 1

        return closed_candle

    def get_forming_candle(self) -> Optional[dict[str, Any]]:
        """Return the current forming (incomplete) candle.

        Returns:
            Candle dict or None if no ticks received.
        """
        if self.tick_count == 0:
            return None
        return {
            "timestamp": self.bucket_start,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }

    def reset(self) -> None:
        """Reset the accumulator."""
        self.open = 0.0
        self.high = 0.0
        self.low = 0.0
        self.close = 0.0
        self.volume = 0
        self.bucket_start = 0
        self.tick_count = 0


class CandleBuilder:
    """Builds multi-timeframe OHLCV candles from raw ticks.

    One CandleBuilder instance per symbol. Maintains accumulators
    for each configured timeframe. Emits candle_closed on the event
    bus and updates MarketState when candles complete.

    Usage:
        builder = CandleBuilder("NSE:RELIANCE-EQ")
        builder.on_tick({"ltp": 2450.5, "volume": 100, "timestamp": 1722500100})
    """

    def __init__(
        self,
        symbol: str,
        timeframes: Optional[list[str]] = None,
    ) -> None:
        self._symbol = symbol
        self._timeframes = timeframes or DEFAULT_TIMEFRAMES
        self._accumulators: dict[str, _CandleAccumulator] = {}
        self._event_bus = EventBus.get_instance()
        self._market_state = MarketState.get_instance()

        for tf in self._timeframes:
            duration = TIMEFRAME_SECONDS.get(tf)
            if duration:
                self._accumulators[tf] = _CandleAccumulator(tf, duration)
            else:
                log.warning(f"Unknown timeframe: {tf}")

        log.debug(
            f"CandleBuilder created: {symbol}, "
            f"timeframes={self._timeframes}"
        )

    @property
    def symbol(self) -> str:
        """Return the symbol this builder handles."""
        return self._symbol

    def on_tick(self, tick_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Process a tick and build candles across all timeframes.

        Args:
            tick_data: Dict with at least 'ltp', 'volume', 'timestamp'.

        Returns:
            List of closed candle dicts (may be empty).
        """
        ltp = tick_data.get("ltp", 0.0)
        volume = tick_data.get("volume", 0)
        timestamp = tick_data.get("timestamp", 0)

        if ltp <= 0 or timestamp <= 0:
            return []

        closed_candles: list[dict[str, Any]] = []

        for tf, acc in self._accumulators.items():
            candle = acc.process_tick(ltp, volume, timestamp)
            if candle is not None:
                candle["timeframe"] = tf
                candle["symbol"] = self._symbol
                closed_candles.append(candle)

                # Update MarketState
                self._market_state.append_candle(
                    self._symbol, tf, candle
                )

                # Emit signal
                self._event_bus.candle_closed.emit(
                    self._symbol, tf, candle
                )

        return closed_candles

    def get_forming_candle(
        self,
        timeframe: str,
    ) -> Optional[dict[str, Any]]:
        """Get the current forming candle for a timeframe.

        Args:
            timeframe: Timeframe string (e.g. '1m').

        Returns:
            Forming candle dict or None.
        """
        acc = self._accumulators.get(timeframe)
        if acc:
            return acc.get_forming_candle()
        return None

    def reset(self) -> None:
        """Reset all accumulators."""
        for acc in self._accumulators.values():
            acc.reset()
        log.debug(f"CandleBuilder reset: {self._symbol}")


__all__ = [
    "CandleBuilder",
    "TIMEFRAME_SECONDS",
    "DEFAULT_TIMEFRAMES",
]
