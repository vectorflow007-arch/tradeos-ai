"""
TradeOS India — Fyers WebSocket live feed.

Runs in a QThread, auto-reconnects on disconnect with exponential
backoff (1s -> 2s -> 4s -> 8s -> 30s max). Emits tick_received
signal for each symbol update.
"""

import json
import time
from typing import Optional

from PySide6.QtCore import QThread, Signal

from core.event_bus import EventBus
from utils.logger import get_logger

log = get_logger("brokers.fyers.feed")

# Reconnect backoff settings
_INITIAL_BACKOFF_S = 1.0
_MAX_BACKOFF_S = 30.0
_BACKOFF_MULTIPLIER = 2.0


class FyersFeed(QThread):
    """WebSocket live market data feed from Fyers.

    Runs in a separate QThread. Subscribes to symbols and emits
    tick_received for each update. Auto-reconnects on disconnect.

    Signals:
        feed_connected: Emitted when WebSocket connects.
        feed_disconnected: Emitted when WebSocket disconnects.
        feed_error: Emitted with error message string.
    """

    feed_connected = Signal()
    feed_disconnected = Signal()
    feed_error = Signal(str)

    def __init__(
        self,
        access_token: str = "",
        app_id: str = "",
        parent: Optional[QThread] = None,
    ) -> None:
        super().__init__(parent)
        self._access_token = access_token
        self._app_id = app_id
        self._symbols: list[str] = []
        self._running = False
        self._ws = None
        self._event_bus = EventBus.get_instance()

    # ═════════════════════════════════════════════════════════════
    # Configuration
    # ═════════════════════════════════════════════════════════════

    def set_credentials(self, access_token: str, app_id: str) -> None:
        """Update the access token and app ID for the feed.

        Args:
            access_token: Fyers access token.
            app_id: Fyers app ID.
        """
        self._access_token = access_token
        self._app_id = app_id

    def subscribe(self, symbols: list[str]) -> None:
        """Set symbols to subscribe to.

        Args:
            symbols: List of Fyers-format symbols (e.g. ['NSE:RELIANCE-EQ']).
        """
        self._symbols = list(set(symbols))
        log.info(f"Feed symbols set: {len(self._symbols)} symbols")

        # If already running, send subscribe message
        if self._ws and self._running:
            self._send_subscribe()

    def unsubscribe(self, symbols: list[str]) -> None:
        """Remove symbols from subscription.

        Args:
            symbols: Symbols to unsubscribe.
        """
        for sym in symbols:
            if sym in self._symbols:
                self._symbols.remove(sym)
        log.info(f"Unsubscribed {len(symbols)} symbols")

        if self._ws and self._running:
            self._send_unsubscribe(symbols)

    # ═════════════════════════════════════════════════════════════
    # QThread run loop
    # ═════════════════════════════════════════════════════════════

    def run(self) -> None:
        """Main thread loop — connect, subscribe, process messages.

        Auto-reconnects with exponential backoff on disconnect.
        """
        self._running = True
        backoff = _INITIAL_BACKOFF_S

        while self._running:
            try:
                self._connect_and_listen()
                # If we get here, connection closed normally
                backoff = _INITIAL_BACKOFF_S
            except Exception as exc:
                log.error(f"Feed error: {exc}")
                self.feed_error.emit(str(exc))

            if not self._running:
                break

            # Exponential backoff before reconnect
            log.info(f"Reconnecting in {backoff:.1f}s...")
            self.feed_disconnected.emit()
            time.sleep(backoff)
            backoff = min(backoff * _BACKOFF_MULTIPLIER, _MAX_BACKOFF_S)

        log.info("Feed thread stopped")

    def _connect_and_listen(self) -> None:
        """Establish WebSocket connection and process messages.

        Uses fyers_apiv3 data socket for SymbolUpdate data type.
        """
        if not self._access_token or not self._app_id:
            log.error("Cannot connect feed: missing credentials")
            self.feed_error.emit("Missing feed credentials")
            return

        try:
            from fyers_apiv3 import fyersModel

            # Create data socket
            self._ws = fyersModel.FyersDataSocket(
                access_token=f"{self._app_id}:{self._access_token}",
                log_path="",
                litemode=False,
                write_to_file=False,
                reconnect=False,  # We handle reconnect ourselves
                on_connect=self._on_connect,
                on_close=self._on_close,
                on_error=self._on_error,
                on_message=self._on_message,
            )

            if self._symbols:
                self._ws.subscribe(
                    symbols=self._symbols,
                    data_type="SymbolUpdate",
                )

            self._ws.keep_running()

        except ImportError:
            log.error("fyers_apiv3 not installed")
            self.feed_error.emit("fyers_apiv3 not installed")
        except Exception as exc:
            log.error(f"Feed connection error: {exc}")
            raise

    # ═════════════════════════════════════════════════════════════
    # WebSocket callbacks
    # ═════════════════════════════════════════════════════════════

    def _on_connect(self) -> None:
        """Called when WebSocket connects."""
        log.info("Feed WebSocket connected")
        self.feed_connected.emit()
        self._send_subscribe()

    def _on_close(self) -> None:
        """Called when WebSocket closes."""
        log.info("Feed WebSocket closed")

    def _on_error(self, error: str) -> None:
        """Called on WebSocket error."""
        log.error(f"Feed WebSocket error: {error}")
        self.feed_error.emit(str(error))

    def _on_message(self, message: dict) -> None:
        """Called for each incoming message/tick.

        Args:
            message: Raw message dict from Fyers WebSocket.
        """
        try:
            symbol = message.get("symbol", "")
            if not symbol:
                return

            tick_data = {
                "ltp": message.get("ltp", 0.0),
                "open": message.get("open_price", 0.0),
                "high": message.get("high_price", 0.0),
                "low": message.get("low_price", 0.0),
                "close": message.get("prev_close_price", 0.0),
                "volume": message.get("vol_traded_today", 0),
                "timestamp": message.get("exch_feed_time", 0),
                "change": message.get("ch", 0.0),
                "change_pct": message.get("chp", 0.0),
                "bid": message.get("bid_price", 0.0),
                "ask": message.get("ask_price", 0.0),
                "oi": message.get("open_interest", 0),
            }

            self._event_bus.tick_received.emit(symbol, tick_data)

        except Exception as exc:
            log.error(f"Error processing tick: {exc}")

    # ═════════════════════════════════════════════════════════════
    # Subscribe/unsubscribe helpers
    # ═════════════════════════════════════════════════════════════

    def _send_subscribe(self) -> None:
        """Send subscribe message for current symbols."""
        if self._ws and self._symbols:
            try:
                self._ws.subscribe(
                    symbols=self._symbols,
                    data_type="SymbolUpdate",
                )
                log.info(f"Subscribed to {len(self._symbols)} symbols")
            except Exception as exc:
                log.error(f"Subscribe error: {exc}")

    def _send_unsubscribe(self, symbols: list[str]) -> None:
        """Send unsubscribe message for given symbols."""
        if self._ws and symbols:
            try:
                self._ws.unsubscribe(symbols=symbols)
                log.info(f"Unsubscribed from {len(symbols)} symbols")
            except Exception as exc:
                log.error(f"Unsubscribe error: {exc}")

    # ═════════════════════════════════════════════════════════════
    # Stop
    # ═════════════════════════════════════════════════════════════

    def stop(self) -> None:
        """Signal the feed thread to stop and disconnect."""
        self._running = False
        if self._ws:
            try:
                self._ws.close_connection()
            except Exception as exc:
                log.error(f"Error closing WebSocket: {exc}")
            self._ws = None
        log.info("Feed stop requested")

    @property
    def is_running(self) -> bool:
        """Return True if the feed thread is active."""
        return self._running and self.isRunning()


__all__ = ["FyersFeed"]
