"""
TradeOS India — Tick fanout to subscribers.

Receives ticks from the broker feed, updates MarketState,
routes ticks to CandleBuilders, and fans out to any registered
callback subscribers.
"""

from typing import Any, Callable, Optional

from core.event_bus import EventBus
from data.candle_builder import CandleBuilder
from data.market_state import MarketState
from utils.logger import get_logger

log = get_logger("data.feed_router")

# Type alias for tick callback
TickCallback = Callable[[str, dict[str, Any]], None]


class FeedRouter:
    """Routes incoming ticks to MarketState, CandleBuilders, and subscribers.

    Connects to the EventBus tick_received signal and distributes
    data to all interested consumers.

    Usage:
        router = FeedRouter()
        router.add_symbol("NSE:RELIANCE-EQ")
        router.subscribe(my_callback)
        # Ticks arrive via EventBus.tick_received -> router processes them
    """

    def __init__(self) -> None:
        self._event_bus = EventBus.get_instance()
        self._market_state = MarketState.get_instance()
        self._builders: dict[str, CandleBuilder] = {}
        self._subscribers: list[TickCallback] = []
        self._symbol_subscribers: dict[str, list[TickCallback]] = {}
        self._connected = False

    # ═════════════════════════════════════════════════════════════
    # Connection
    # ═════════════════════════════════════════════════════════════

    def connect(self) -> None:
        """Connect to the EventBus tick_received signal."""
        if not self._connected:
            self._event_bus.tick_received.connect(self._on_tick)
            self._connected = True
            log.info("FeedRouter connected to tick_received signal")

    def disconnect(self) -> None:
        """Disconnect from the EventBus tick_received signal."""
        if self._connected:
            try:
                self._event_bus.tick_received.disconnect(self._on_tick)
            except RuntimeError:
                pass
            self._connected = False
            log.info("FeedRouter disconnected")

    # ═════════════════════════════════════════════════════════════
    # Symbol management
    # ═════════════════════════════════════════════════════════════

    def add_symbol(
        self,
        symbol: str,
        timeframes: Optional[list[str]] = None,
    ) -> None:
        """Add a symbol for candle building.

        Creates a CandleBuilder for the symbol if one doesn't exist.

        Args:
            symbol: Trading symbol (e.g. 'NSE:RELIANCE-EQ').
            timeframes: Optional list of timeframes to build.
        """
        if symbol not in self._builders:
            self._builders[symbol] = CandleBuilder(symbol, timeframes)
            log.info(f"Symbol added to FeedRouter: {symbol}")

    def remove_symbol(self, symbol: str) -> None:
        """Remove a symbol and its CandleBuilder.

        Args:
            symbol: Trading symbol to remove.
        """
        if symbol in self._builders:
            del self._builders[symbol]
            self._market_state.clear_symbol(symbol)
            self._symbol_subscribers.pop(symbol, None)
            log.info(f"Symbol removed from FeedRouter: {symbol}")

    def get_symbols(self) -> list[str]:
        """Return list of symbols with active CandleBuilders."""
        return list(self._builders.keys())

    # ═════════════════════════════════════════════════════════════
    # Subscribers
    # ═════════════════════════════════════════════════════════════

    def subscribe(self, callback: TickCallback) -> None:
        """Register a callback to receive all ticks.

        Args:
            callback: Function(symbol, tick_data) called on every tick.
        """
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: TickCallback) -> None:
        """Remove a global tick callback.

        Args:
            callback: Previously registered callback.
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def subscribe_symbol(
        self,
        symbol: str,
        callback: TickCallback,
    ) -> None:
        """Register a callback for ticks of a specific symbol.

        Args:
            symbol: Symbol to subscribe to.
            callback: Function(symbol, tick_data).
        """
        if symbol not in self._symbol_subscribers:
            self._symbol_subscribers[symbol] = []
        if callback not in self._symbol_subscribers[symbol]:
            self._symbol_subscribers[symbol].append(callback)

    def unsubscribe_symbol(
        self,
        symbol: str,
        callback: TickCallback,
    ) -> None:
        """Remove a symbol-specific tick callback.

        Args:
            symbol: Symbol.
            callback: Previously registered callback.
        """
        subs = self._symbol_subscribers.get(symbol, [])
        if callback in subs:
            subs.remove(callback)

    # ═════════════════════════════════════════════════════════════
    # Tick processing
    # ═════════════════════════════════════════════════════════════

    def _on_tick(self, symbol: str, tick_data: dict[str, Any]) -> None:
        """Process an incoming tick from the EventBus.

        1. Update MarketState with latest tick
        2. Route to CandleBuilder for the symbol
        3. Fan out to global subscribers
        4. Fan out to symbol-specific subscribers

        Args:
            symbol: Trading symbol.
            tick_data: Tick data dict.
        """
        # 1. Update MarketState
        self._market_state.update_tick(symbol, tick_data)

        # 2. Build candles
        builder = self._builders.get(symbol)
        if builder:
            builder.on_tick(tick_data)

        # 3. Global subscribers
        for cb in self._subscribers:
            try:
                cb(symbol, tick_data)
            except Exception as exc:
                log.error(f"Subscriber error: {exc}")

        # 4. Symbol-specific subscribers
        sym_subs = self._symbol_subscribers.get(symbol, [])
        for cb in sym_subs:
            try:
                cb(symbol, tick_data)
            except Exception as exc:
                log.error(f"Symbol subscriber error: {exc}")

    def process_tick(self, symbol: str, tick_data: dict[str, Any]) -> None:
        """Manually process a tick (for testing or direct injection).

        Same as _on_tick but public.

        Args:
            symbol: Trading symbol.
            tick_data: Tick data dict.
        """
        self._on_tick(symbol, tick_data)

    # ═════════════════════════════════════════════════════════════
    # Cleanup
    # ═════════════════════════════════════════════════════════════

    def clear(self) -> None:
        """Remove all symbols, builders, and subscribers."""
        self._builders.clear()
        self._subscribers.clear()
        self._symbol_subscribers.clear()
        self._market_state.clear_all()
        log.info("FeedRouter cleared")


__all__ = ["FeedRouter", "TickCallback"]
