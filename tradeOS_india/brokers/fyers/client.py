"""
TradeOS India — FyersClient implements BaseBroker.

Composes FyersAuth, FyersContracts, FyersFeed, and FyersOrders
into a unified broker interface.
"""

import asyncio
from typing import Any, Optional

import httpx

from brokers.base_broker import (
    BaseBroker,
    FundsData,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    Position,
    Side,
    ProductType,
)
from brokers.fyers.auth import FyersAuth
from brokers.fyers.contracts import FyersContracts
from brokers.fyers.feed import FyersFeed
from brokers.fyers.orders import FyersOrders
from core.event_bus import EventBus
from core.state_store import AppState
from utils.keychain import get_secret
from utils.logger import get_logger

log = get_logger("brokers.fyers.client")


class FyersClient(BaseBroker):
    """Full Fyers broker implementation.

    Provides authentication, live feed, order management, historical data,
    and contract lookup — all through the BaseBroker interface.
    """

    def __init__(self) -> None:
        self._auth = FyersAuth()
        self._contracts = FyersContracts()
        self._feed: Optional[FyersFeed] = None
        self._orders: Optional[FyersOrders] = None
        self._access_token: str = ""
        self._app_id: str = ""
        self._authenticated = False
        self._event_bus = EventBus.get_instance()
        self._state = AppState.get_instance()
        self._fyers_model = None

    # ═════════════════════════════════════════════════════════════
    # Properties
    # ═════════════════════════════════════════════════════════════

    @property
    def broker_name(self) -> str:
        """Return the broker identifier."""
        return "fyers"

    @property
    def is_authenticated(self) -> bool:
        """Return True if the broker session is valid."""
        return self._authenticated

    @property
    def auth(self) -> FyersAuth:
        """Expose the auth component for OAuth flows."""
        return self._auth

    @property
    def contracts(self) -> FyersContracts:
        """Expose the contracts component for searches."""
        return self._contracts

    @property
    def feed(self) -> Optional[FyersFeed]:
        """Expose the feed component."""
        return self._feed

    # ═════════════════════════════════════════════════════════════
    # Authentication
    # ═════════════════════════════════════════════════════════════

    async def authenticate(self) -> bool:
        """Load credentials and validate the stored token.

        Returns:
            True if authentication succeeded.
        """
        try:
            # Load app_id from keyring
            self._auth.load_credentials()
            self._app_id = get_secret("fyers_app_id") or ""

            # Load token
            self._access_token = self._auth.load_token() or ""

            if not self._access_token:
                log.warning("No Fyers token found — need OAuth login")
                self._authenticated = False
                return False

            # Validate token
            valid = await self._auth.validate_token(self._access_token)
            if valid:
                self._authenticated = True
                self._init_components()
                self._event_bus.broker_connected.emit("fyers")
                self._state.broker_connected = True
                self._state.save()
                log.info("Fyers authentication successful")
                return True

            log.warning("Fyers token validation failed")
            self._authenticated = False
            return False

        except Exception as exc:
            log.error(f"Fyers authentication error: {exc}")
            self._event_bus.broker_error.emit("fyers", str(exc))
            self._authenticated = False
            return False

    def _init_components(self) -> None:
        """Initialize feed and orders with current credentials."""
        # Orders
        self._orders = FyersOrders(self._access_token, self._app_id)

        # Feed
        self._feed = FyersFeed(self._access_token, self._app_id)

        # Fyers model for direct API calls
        try:
            from fyers_apiv3 import fyersModel
            self._fyers_model = fyersModel.FyersModel(
                client_id=self._app_id,
                token=self._access_token,
                is_async=False,
                log_path="",
            )
        except ImportError:
            log.warning("fyers_apiv3 not installed — some features unavailable")
        except Exception as exc:
            log.error(f"Failed to init Fyers model: {exc}")

    # ═════════════════════════════════════════════════════════════
    # Profile & Funds
    # ═════════════════════════════════════════════════════════════

    async def get_profile(self) -> dict[str, Any]:
        """Fetch the user profile from Fyers.

        Returns:
            Dict with profile info.
        """
        if not self._fyers_model:
            return {"error": "Not authenticated"}

        try:
            result = self._fyers_model.get_profile()
            if result.get("s") == "ok":
                data = result.get("data", {})
                return {
                    "name": data.get("name", ""),
                    "email": data.get("email_id", ""),
                    "pan": data.get("pan", ""),
                    "broker": "fyers",
                }
            return {"error": result.get("message", "Unknown error")}
        except Exception as exc:
            log.error(f"Get profile error: {exc}")
            return {"error": str(exc)}

    async def get_funds(self) -> FundsData:
        """Fetch account funds from Fyers.

        Returns:
            FundsData with margin details.
        """
        if self._state.mode == "paper":
            return FundsData(
                available_margin=100000.0,
                used_margin=0.0,
                total_balance=100000.0,
            )

        if not self._fyers_model:
            return FundsData()

        try:
            result = self._fyers_model.funds()
            if result.get("s") == "ok":
                fund_data = result.get("fund_limit", [])
                funds = FundsData(broker_raw=result)

                for item in fund_data:
                    title = item.get("title", "").lower()
                    if "available" in title:
                        funds.available_margin = item.get(
                            "equityAmount", 0.0
                        )
                    elif "used" in title:
                        funds.used_margin = item.get("equityAmount", 0.0)
                    elif "total" in title or "balance" in title:
                        funds.total_balance = item.get("equityAmount", 0.0)

                self._event_bus.funds_updated.emit({
                    "available": funds.available_margin,
                    "used": funds.used_margin,
                    "total": funds.total_balance,
                })
                return funds

            return FundsData()
        except Exception as exc:
            log.error(f"Get funds error: {exc}")
            self._event_bus.broker_error.emit("fyers", str(exc))
            return FundsData()

    # ═════════════════════════════════════════════════════════════
    # Orders
    # ═════════════════════════════════════════════════════════════

    async def place_order(self, request: OrderRequest) -> OrderResponse:
        """Place an order (paper or live).

        Args:
            request: Order parameters.

        Returns:
            OrderResponse.
        """
        if not self._orders:
            self._orders = FyersOrders(self._access_token, self._app_id)
        return await self._orders.place_order(request)

    async def modify_order(
        self,
        order_id: str,
        updates: dict[str, Any],
    ) -> OrderResponse:
        """Modify an existing order.

        Args:
            order_id: Order to modify.
            updates: Fields to change.

        Returns:
            OrderResponse.
        """
        if not self._orders:
            return OrderResponse(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol="",
                exchange="",
                side=Side.BUY,
                quantity=0,
                message="Orders not initialized",
            )
        return await self._orders.modify_order(order_id, updates)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.

        Args:
            order_id: Order to cancel.

        Returns:
            True if cancellation accepted.
        """
        if not self._orders:
            return False
        return await self._orders.cancel_order(order_id)

    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Get order status.

        Args:
            order_id: Order to query.

        Returns:
            OrderResponse.
        """
        if not self._orders:
            return OrderResponse(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol="",
                exchange="",
                side=Side.BUY,
                quantity=0,
                message="Orders not initialized",
            )
        return await self._orders.get_order_status(order_id)

    async def get_orders(self) -> list[OrderResponse]:
        """Get all today's orders.

        Returns:
            List of OrderResponse.
        """
        if not self._orders:
            return []
        return await self._orders.get_orders()

    # ═════════════════════════════════════════════════════════════
    # Positions
    # ═════════════════════════════════════════════════════════════

    async def get_positions(self) -> list[Position]:
        """Fetch open positions.

        Returns:
            List of Position instances.
        """
        if self._state.mode == "paper":
            return [
                Position(
                    symbol=p.get("symbol", ""),
                    exchange=p.get("exchange", ""),
                    side=Side(p.get("side", "BUY")),
                    quantity=p.get("quantity", 0),
                    avg_price=p.get("avg_price", 0.0),
                    ltp=p.get("ltp", 0.0),
                    pnl=p.get("pnl", 0.0),
                    product=ProductType(p.get("product", "MIS")),
                )
                for p in self._state.open_positions
            ]

        if not self._fyers_model:
            return []

        try:
            result = self._fyers_model.positions()
            if result.get("s") != "ok":
                return []

            positions = []
            for pos in result.get("netPositions", []):
                fyers_sym = pos.get("symbol", "")
                parts = fyers_sym.split(":", 1)
                exchange = parts[0] if len(parts) == 2 else ""
                symbol = parts[1] if len(parts) == 2 else fyers_sym

                qty = pos.get("netQty", 0)
                if qty == 0:
                    continue

                positions.append(Position(
                    symbol=symbol,
                    exchange=exchange,
                    side=Side.BUY if qty > 0 else Side.SELL,
                    quantity=abs(qty),
                    avg_price=pos.get("avgPrice", 0.0),
                    ltp=pos.get("ltp", 0.0),
                    pnl=pos.get("pl", 0.0),
                    product=ProductType.MIS,
                    broker_raw=pos,
                ))

            self._event_bus.positions_updated.emit(
                [vars(p) for p in positions]
            )
            return positions

        except Exception as exc:
            log.error(f"Get positions error: {exc}")
            return []

    # ═════════════════════════════════════════════════════════════
    # Historical data
    # ═════════════════════════════════════════════════════════════

    async def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        from_date: str,
        to_date: str,
    ) -> list[dict[str, Any]]:
        """Fetch historical OHLCV from Fyers.

        Args:
            symbol: Fyers-format symbol.
            timeframe: '1m', '5m', '15m', '1h', '1D'.
            from_date: Start date 'YYYY-MM-DD'.
            to_date: End date 'YYYY-MM-DD'.

        Returns:
            List of candle dicts.
        """
        if not self._fyers_model:
            return []

        # Map timeframe to Fyers resolution
        resolution_map = {
            "1m": "1", "5m": "5", "15m": "15",
            "30m": "30", "1h": "60", "1D": "D",
        }
        resolution = resolution_map.get(timeframe, "15")

        try:
            data = {
                "symbol": symbol,
                "resolution": resolution,
                "date_format": "1",
                "range_from": from_date,
                "range_to": to_date,
                "cont_flag": "1",
            }
            result = self._fyers_model.history(data=data)

            if result.get("s") != "ok":
                log.error(
                    f"History error: {result.get('message', '?')}"
                )
                return []

            candles = []
            for row in result.get("candles", []):
                if len(row) >= 6:
                    candles.append({
                        "timestamp": row[0],
                        "open": row[1],
                        "high": row[2],
                        "low": row[3],
                        "close": row[4],
                        "volume": row[5],
                    })

            log.info(f"History: {symbol} {timeframe} -> {len(candles)} candles")
            return candles

        except Exception as exc:
            log.error(f"Get historical candles error: {exc}")
            return []

    # ═════════════════════════════════════════════════════════════
    # Live feed
    # ═════════════════════════════════════════════════════════════

    async def subscribe_symbols(self, symbols: list[str]) -> bool:
        """Subscribe to live tick data.

        Args:
            symbols: Fyers-format symbols.

        Returns:
            True if subscription started.
        """
        if not self._feed:
            self._feed = FyersFeed(self._access_token, self._app_id)

        self._feed.subscribe(symbols)

        if not self._feed.is_running:
            self._feed.start()

        return True

    async def unsubscribe_symbols(self, symbols: list[str]) -> bool:
        """Unsubscribe from live data.

        Args:
            symbols: Symbols to unsubscribe.

        Returns:
            True.
        """
        if self._feed:
            self._feed.unsubscribe(symbols)
        return True

    # ═════════════════════════════════════════════════════════════
    # Disconnect
    # ═════════════════════════════════════════════════════════════

    async def disconnect(self) -> None:
        """Disconnect from Fyers — stop feed, cleanup."""
        if self._feed:
            self._feed.stop()
            self._feed.wait(5000)
            self._feed = None

        self._authenticated = False
        self._fyers_model = None
        self._state.broker_connected = False
        self._state.save()
        self._event_bus.broker_disconnected.emit("fyers")
        log.info("Fyers client disconnected")


__all__ = ["FyersClient"]
