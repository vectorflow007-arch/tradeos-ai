"""
TradeOS India — Fyers order placement, modification, and cancellation.

Supports both paper mode (simulated fills) and live mode (real broker API).
Paper mode simulates fill at LTP + random slippage (0-0.02%).
Live mode calls fyers_apiv3 place_order and polls status.
"""

import asyncio
import random
import uuid
from typing import Any, Optional

from core.event_bus import EventBus
from core.state_store import AppState
from brokers.base_broker import (
    OrderRequest,
    OrderResponse,
    OrderStatus,
    OrderType,
    ProductType,
    Side,
)
from utils.date_utils import ist_timestamp as now_ist_str
from utils.logger import get_logger

log = get_logger("brokers.fyers.orders")

# ─── Fyers API field mappings ────────────────────────────────────
_SIDE_MAP = {
    Side.BUY: 1,
    Side.SELL: -1,
}

_ORDER_TYPE_MAP = {
    OrderType.LIMIT: 1,
    OrderType.MARKET: 2,
    OrderType.SL: 3,
    OrderType.SLM: 4,
}

_PRODUCT_MAP = {
    ProductType.CNC: "CNC",
    ProductType.MIS: "INTRADAY",
    ProductType.NRML: "MARGIN",
}

# Paper mode slippage range
_PAPER_SLIPPAGE_MIN = 0.0
_PAPER_SLIPPAGE_MAX = 0.0002  # 0.02%

# Live mode order status polling
_POLL_INTERVAL_S = 2.0
_POLL_TIMEOUT_S = 60.0


class FyersOrders:
    """Place, modify, and cancel orders via Fyers API or paper simulation.

    In paper mode: simulates fill at LTP with small random slippage.
    In live mode: calls fyers_apiv3 API and polls for fill status.
    """

    def __init__(
        self,
        access_token: str = "",
        app_id: str = "",
    ) -> None:
        self._access_token = access_token
        self._app_id = app_id
        self._fyers = None
        self._event_bus = EventBus.get_instance()
        self._state = AppState.get_instance()

    def set_credentials(self, access_token: str, app_id: str) -> None:
        """Update credentials and initialize the Fyers model.

        Args:
            access_token: Fyers access token.
            app_id: Fyers app ID.
        """
        self._access_token = access_token
        self._app_id = app_id
        self._init_fyers_model()

    def _init_fyers_model(self) -> None:
        """Initialize the fyers_apiv3 model for API calls."""
        if not self._access_token or not self._app_id:
            return
        try:
            from fyers_apiv3 import fyersModel
            self._fyers = fyersModel.FyersModel(
                client_id=self._app_id,
                token=self._access_token,
                is_async=False,
                log_path="",
            )
            log.info("Fyers order model initialized")
        except ImportError:
            log.error("fyers_apiv3 not installed")
        except Exception as exc:
            log.error(f"Failed to init Fyers model: {exc}")

    # ═════════════════════════════════════════════════════════════
    # Place order
    # ═════════════════════════════════════════════════════════════

    async def place_order(self, request: OrderRequest) -> OrderResponse:
        """Place an order — paper or live based on AppState.mode.

        Args:
            request: The OrderRequest with all parameters.

        Returns:
            OrderResponse with order ID and status.
        """
        mode = self._state.mode

        if mode == "paper":
            return await self._place_paper_order(request)
        elif mode == "live":
            return await self._place_live_order(request)
        else:
            log.error(f"Unknown trading mode: {mode}")
            return OrderResponse(
                order_id="",
                status=OrderStatus.REJECTED,
                symbol=request.symbol,
                exchange=request.exchange,
                side=request.side,
                quantity=request.quantity,
                message=f"Unknown mode: {mode}",
            )

    # ─── Paper mode ──────────────────────────────────────────────

    async def _place_paper_order(
        self,
        request: OrderRequest,
    ) -> OrderResponse:
        """Simulate an order fill in paper mode.

        Fill price = last known LTP + random slippage (0-0.02%).
        Emits all the same signals as a real order.

        Args:
            request: Order request.

        Returns:
            Simulated OrderResponse with FILLED status.
        """
        order_id = f"PAPER-{uuid.uuid4().hex[:8].upper()}"
        timestamp = now_ist_str()

        # Get LTP from market state or use entry price
        ltp = self._get_ltp(request.symbol)
        if ltp <= 0 and request.price > 0:
            ltp = request.price
        elif ltp <= 0:
            ltp = 100.0  # Fallback for testing

        # Apply random slippage
        slippage_pct = random.uniform(
            _PAPER_SLIPPAGE_MIN, _PAPER_SLIPPAGE_MAX
        )
        if request.side == Side.BUY:
            fill_price = ltp * (1 + slippage_pct)
        else:
            fill_price = ltp * (1 - slippage_pct)
        fill_price = round(fill_price, 2)

        response = OrderResponse(
            order_id=order_id,
            status=OrderStatus.FILLED,
            symbol=request.symbol,
            exchange=request.exchange,
            side=request.side,
            quantity=request.quantity,
            filled_qty=request.quantity,
            avg_price=fill_price,
            order_type=request.order_type,
            product=request.product,
            message="Paper order filled",
            timestamp=timestamp,
        )

        log.info(
            f"[PAPER] {request.side.value} {request.quantity} "
            f"{request.symbol} @ {fill_price} (order: {order_id})"
        )

        # Update state
        trade_record = {
            "order_id": order_id,
            "symbol": request.symbol,
            "exchange": request.exchange,
            "side": request.side.value,
            "quantity": request.quantity,
            "entry_price": fill_price,
            "product": request.product.value,
            "order_type": request.order_type.value,
            "status": "FILLED",
            "mode": "paper",
            "broker": "fyers",
            "strategy_name": request.strategy_name,
            "agent_task_id": request.agent_task_id,
            "entry_time": timestamp,
        }
        self._state.todays_trades.append(trade_record)

        # Add to open positions
        position = {
            "symbol": request.symbol,
            "exchange": request.exchange,
            "side": request.side.value,
            "quantity": request.quantity,
            "avg_price": fill_price,
            "ltp": ltp,
            "pnl": 0.0,
            "product": request.product.value,
        }
        self._state.open_positions.append(position)

        # Emit signals
        self._event_bus.order_placed.emit(trade_record)
        self._event_bus.order_filled.emit(trade_record)
        self._event_bus.positions_updated.emit(self._state.open_positions)

        return response

    # ─── Live mode ───────────────────────────────────────────────

    async def _place_live_order(
        self,
        request: OrderRequest,
    ) -> OrderResponse:
        """Place a real order through Fyers API.

        SAFETY: Only called when AppState.mode == 'live'.
        Polls order status every 2s for up to 60s.

        Args:
            request: Order request.

        Returns:
            OrderResponse with actual broker status.
        """
        if self._state.mode != "live":
            log.error("SAFETY: _place_live_order called in non-live mode!")
            return OrderResponse(
                order_id="",
                status=OrderStatus.REJECTED,
                symbol=request.symbol,
                exchange=request.exchange,
                side=request.side,
                quantity=request.quantity,
                message="Safety check: not in live mode",
            )

        if not self._fyers:
            self._init_fyers_model()

        if not self._fyers:
            return OrderResponse(
                order_id="",
                status=OrderStatus.REJECTED,
                symbol=request.symbol,
                exchange=request.exchange,
                side=request.side,
                quantity=request.quantity,
                message="Fyers model not initialized",
            )

        # Build Fyers order payload
        payload = {
            "symbol": f"{request.exchange}:{request.symbol}",
            "qty": request.quantity,
            "type": _ORDER_TYPE_MAP.get(request.order_type, 2),
            "side": _SIDE_MAP.get(request.side, 1),
            "productType": _PRODUCT_MAP.get(request.product, "INTRADAY"),
            "validity": request.validity,
            "disclosedQty": request.disclosed_qty,
            "offlineOrder": False,
        }

        if request.price > 0:
            payload["limitPrice"] = request.price
        if request.trigger_price > 0:
            payload["stopPrice"] = request.trigger_price

        try:
            result = self._fyers.place_order(data=payload)
            log.info(f"[LIVE] Order response: {result}")

            if result.get("s") != "ok":
                error_msg = result.get("message", "Order placement failed")
                response = OrderResponse(
                    order_id="",
                    status=OrderStatus.REJECTED,
                    symbol=request.symbol,
                    exchange=request.exchange,
                    side=request.side,
                    quantity=request.quantity,
                    message=error_msg,
                    broker_raw=result,
                )
                self._event_bus.order_rejected.emit(
                    {"symbol": request.symbol}, error_msg
                )
                return response

            order_id = result.get("id", "")
            response = OrderResponse(
                order_id=order_id,
                status=OrderStatus.PENDING,
                symbol=request.symbol,
                exchange=request.exchange,
                side=request.side,
                quantity=request.quantity,
                broker_raw=result,
                timestamp=now_ist_str(),
            )

            self._event_bus.order_placed.emit({
                "order_id": order_id,
                "symbol": request.symbol,
                "side": request.side.value,
                "quantity": request.quantity,
            })

            # Poll for fill
            filled_response = await self._poll_order_status(
                order_id, request
            )
            return filled_response

        except Exception as exc:
            log.error(f"Live order error: {exc}")
            self._event_bus.broker_error.emit("fyers", str(exc))
            return OrderResponse(
                order_id="",
                status=OrderStatus.REJECTED,
                symbol=request.symbol,
                exchange=request.exchange,
                side=request.side,
                quantity=request.quantity,
                message=str(exc),
            )

    async def _poll_order_status(
        self,
        order_id: str,
        request: OrderRequest,
    ) -> OrderResponse:
        """Poll order status every 2s for up to 60s until terminal state.

        Args:
            order_id: Fyers order ID.
            request: Original order request.

        Returns:
            Final OrderResponse.
        """
        elapsed = 0.0

        while elapsed < _POLL_TIMEOUT_S:
            await asyncio.sleep(_POLL_INTERVAL_S)
            elapsed += _POLL_INTERVAL_S

            try:
                status_resp = self._fyers.orderBook()
                if status_resp.get("s") != "ok":
                    continue

                orders = status_resp.get("orderBook", [])
                order_data = None
                for order in orders:
                    if order.get("id") == order_id:
                        order_data = order
                        break

                if not order_data:
                    continue

                fyers_status = order_data.get("status", 0)

                # Fyers status codes: 2=filled, 5=rejected, 1=cancelled
                if fyers_status == 2:
                    response = OrderResponse(
                        order_id=order_id,
                        status=OrderStatus.FILLED,
                        symbol=request.symbol,
                        exchange=request.exchange,
                        side=request.side,
                        quantity=request.quantity,
                        filled_qty=order_data.get("filledQty", 0),
                        avg_price=order_data.get("tradedPrice", 0.0),
                        order_type=request.order_type,
                        product=request.product,
                        message="Order filled",
                        broker_raw=order_data,
                        timestamp=now_ist_str(),
                    )
                    self._event_bus.order_filled.emit({
                        "order_id": order_id,
                        "symbol": request.symbol,
                        "side": request.side.value,
                        "avg_price": response.avg_price,
                    })
                    return response

                elif fyers_status == 5:
                    reason = order_data.get("message", "Rejected by exchange")
                    self._event_bus.order_rejected.emit(
                        {"order_id": order_id}, reason
                    )
                    return OrderResponse(
                        order_id=order_id,
                        status=OrderStatus.REJECTED,
                        symbol=request.symbol,
                        exchange=request.exchange,
                        side=request.side,
                        quantity=request.quantity,
                        message=reason,
                        broker_raw=order_data,
                    )

                elif fyers_status == 1:
                    self._event_bus.order_cancelled.emit(order_id)
                    return OrderResponse(
                        order_id=order_id,
                        status=OrderStatus.CANCELLED,
                        symbol=request.symbol,
                        exchange=request.exchange,
                        side=request.side,
                        quantity=request.quantity,
                        message="Order cancelled",
                        broker_raw=order_data,
                    )

            except Exception as exc:
                log.error(f"Poll error: {exc}")

        # Timeout — return pending
        log.warning(f"Order {order_id} poll timeout after {_POLL_TIMEOUT_S}s")
        return OrderResponse(
            order_id=order_id,
            status=OrderStatus.PENDING,
            symbol=request.symbol,
            exchange=request.exchange,
            side=request.side,
            quantity=request.quantity,
            message="Poll timeout",
        )

    # ═════════════════════════════════════════════════════════════
    # Modify / Cancel
    # ═════════════════════════════════════════════════════════════

    async def modify_order(
        self,
        order_id: str,
        updates: dict[str, Any],
    ) -> OrderResponse:
        """Modify an existing order.

        Args:
            order_id: The order ID to modify.
            updates: Dict with fields to change (qty, limitPrice, etc.).

        Returns:
            OrderResponse with updated status.
        """
        if self._state.mode == "paper":
            log.info(f"[PAPER] Modify order {order_id}: {updates}")
            return OrderResponse(
                order_id=order_id,
                status=OrderStatus.OPEN,
                symbol=updates.get("symbol", ""),
                exchange=updates.get("exchange", ""),
                side=Side(updates.get("side", "BUY")),
                quantity=updates.get("qty", 0),
                message="Paper order modified",
            )

        if not self._fyers:
            return OrderResponse(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol="",
                exchange="",
                side=Side.BUY,
                quantity=0,
                message="Fyers model not initialized",
            )

        try:
            payload = {"id": order_id, **updates}
            result = self._fyers.modify_order(data=payload)
            log.info(f"[LIVE] Modify result: {result}")

            if result.get("s") == "ok":
                return OrderResponse(
                    order_id=order_id,
                    status=OrderStatus.OPEN,
                    symbol=updates.get("symbol", ""),
                    exchange=updates.get("exchange", ""),
                    side=Side(updates.get("side", "BUY")),
                    quantity=updates.get("qty", 0),
                    message="Order modified",
                    broker_raw=result,
                )

            return OrderResponse(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol="",
                exchange="",
                side=Side.BUY,
                quantity=0,
                message=result.get("message", "Modify failed"),
                broker_raw=result,
            )

        except Exception as exc:
            log.error(f"Modify order error: {exc}")
            return OrderResponse(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol="",
                exchange="",
                side=Side.BUY,
                quantity=0,
                message=str(exc),
            )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order.

        Args:
            order_id: The order ID to cancel.

        Returns:
            True if cancellation was accepted.
        """
        if self._state.mode == "paper":
            log.info(f"[PAPER] Cancel order {order_id}")
            self._event_bus.order_cancelled.emit(order_id)
            return True

        if not self._fyers:
            log.error("Cannot cancel: Fyers model not initialized")
            return False

        try:
            result = self._fyers.cancel_order(data={"id": order_id})
            log.info(f"[LIVE] Cancel result: {result}")

            if result.get("s") == "ok":
                self._event_bus.order_cancelled.emit(order_id)
                return True

            log.error(f"Cancel failed: {result.get('message', '?')}")
            return False

        except Exception as exc:
            log.error(f"Cancel order error: {exc}")
            return False

    # ═════════════════════════════════════════════════════════════
    # Query
    # ═════════════════════════════════════════════════════════════

    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Get current status of an order.

        Args:
            order_id: The order ID to query.

        Returns:
            OrderResponse with current status.
        """
        if self._state.mode == "paper":
            # Look up in state
            for trade in self._state.todays_trades:
                if trade.get("order_id") == order_id:
                    return OrderResponse(
                        order_id=order_id,
                        status=OrderStatus.FILLED,
                        symbol=trade.get("symbol", ""),
                        exchange=trade.get("exchange", ""),
                        side=Side(trade.get("side", "BUY")),
                        quantity=trade.get("quantity", 0),
                        filled_qty=trade.get("quantity", 0),
                        avg_price=trade.get("entry_price", 0.0),
                        message="Paper order",
                    )
            return OrderResponse(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol="",
                exchange="",
                side=Side.BUY,
                quantity=0,
                message="Order not found in paper trades",
            )

        if not self._fyers:
            return OrderResponse(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol="",
                exchange="",
                side=Side.BUY,
                quantity=0,
                message="Fyers model not initialized",
            )

        try:
            result = self._fyers.orderBook()
            if result.get("s") == "ok":
                for order in result.get("orderBook", []):
                    if order.get("id") == order_id:
                        return self._parse_order_book_entry(order)

            return OrderResponse(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol="",
                exchange="",
                side=Side.BUY,
                quantity=0,
                message="Order not found",
            )

        except Exception as exc:
            log.error(f"Get order status error: {exc}")
            return OrderResponse(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol="",
                exchange="",
                side=Side.BUY,
                quantity=0,
                message=str(exc),
            )

    async def get_orders(self) -> list[OrderResponse]:
        """Get all today's orders.

        Returns:
            List of OrderResponse.
        """
        if self._state.mode == "paper":
            return [
                OrderResponse(
                    order_id=t.get("order_id", ""),
                    status=OrderStatus.FILLED,
                    symbol=t.get("symbol", ""),
                    exchange=t.get("exchange", ""),
                    side=Side(t.get("side", "BUY")),
                    quantity=t.get("quantity", 0),
                    filled_qty=t.get("quantity", 0),
                    avg_price=t.get("entry_price", 0.0),
                )
                for t in self._state.todays_trades
            ]

        if not self._fyers:
            return []

        try:
            result = self._fyers.orderBook()
            if result.get("s") == "ok":
                return [
                    self._parse_order_book_entry(o)
                    for o in result.get("orderBook", [])
                ]
            return []
        except Exception as exc:
            log.error(f"Get orders error: {exc}")
            return []

    def _parse_order_book_entry(
        self,
        entry: dict[str, Any],
    ) -> OrderResponse:
        """Parse a Fyers orderBook entry into OrderResponse.

        Args:
            entry: Raw order book dict from Fyers.

        Returns:
            OrderResponse.
        """
        status_map = {
            1: OrderStatus.CANCELLED,
            2: OrderStatus.FILLED,
            4: OrderStatus.OPEN,
            5: OrderStatus.REJECTED,
            6: OrderStatus.PENDING,
        }

        fyers_symbol = entry.get("symbol", "")
        parts = fyers_symbol.split(":", 1)
        exchange = parts[0] if len(parts) == 2 else ""
        symbol = parts[1] if len(parts) == 2 else fyers_symbol

        return OrderResponse(
            order_id=entry.get("id", ""),
            status=status_map.get(entry.get("status", 0), OrderStatus.PENDING),
            symbol=symbol,
            exchange=exchange,
            side=Side.BUY if entry.get("side", 1) == 1 else Side.SELL,
            quantity=entry.get("qty", 0),
            filled_qty=entry.get("filledQty", 0),
            avg_price=entry.get("tradedPrice", 0.0),
            message=entry.get("message", ""),
            broker_raw=entry,
        )

    # ═════════════════════════════════════════════════════════════
    # Helpers
    # ═════════════════════════════════════════════════════════════

    def _get_ltp(self, symbol: str) -> float:
        """Get last traded price from market state.

        Args:
            symbol: Symbol to look up.

        Returns:
            LTP as float, or 0.0 if not available.
        """
        try:
            from data.market_state import MarketState
            ms = MarketState.get_instance()
            tick = ms.get_tick(symbol)
            if tick:
                return tick.get("ltp", 0.0)
        except Exception:
            pass
        return 0.0


__all__ = ["FyersOrders"]
