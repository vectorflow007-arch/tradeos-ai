"""
TradeOS India — Abstract base broker and shared dataclasses.

All broker implementations must inherit BaseBroker and implement
every abstract method. OrderRequest/OrderResponse/Position provide
a broker-agnostic data layer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ═════════════════════════════════════════════════════════════════
# Enums
# ═════════════════════════════════════════════════════════════════

class Side(str, Enum):
    """Order side."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SLM = "SLM"


class ProductType(str, Enum):
    """Product type for Indian markets."""
    CNC = "CNC"       # Cash and carry (delivery)
    MIS = "MIS"       # Margin intraday square-off
    NRML = "NRML"     # Normal (F&O carry forward)


class OrderStatus(str, Enum):
    """Order lifecycle status."""
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


# ═════════════════════════════════════════════════════════════════
# Dataclasses
# ═════════════════════════════════════════════════════════════════

@dataclass
class OrderRequest:
    """Broker-agnostic order request."""

    symbol: str
    exchange: str
    side: Side
    quantity: int
    order_type: OrderType = OrderType.MARKET
    product: ProductType = ProductType.MIS
    price: float = 0.0
    trigger_price: float = 0.0
    disclosed_qty: int = 0
    validity: str = "DAY"
    strategy_name: Optional[str] = None
    agent_task_id: Optional[str] = None
    tag: str = ""


@dataclass
class OrderResponse:
    """Broker-agnostic order response."""

    order_id: str
    status: OrderStatus
    symbol: str
    exchange: str
    side: Side
    quantity: int
    filled_qty: int = 0
    avg_price: float = 0.0
    order_type: OrderType = OrderType.MARKET
    product: ProductType = ProductType.MIS
    message: str = ""
    broker_raw: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


@dataclass
class Position:
    """Broker-agnostic open position."""

    symbol: str
    exchange: str
    side: Side
    quantity: int
    avg_price: float
    ltp: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    product: ProductType = ProductType.MIS
    overnight_qty: int = 0
    day_qty: int = 0
    broker_raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class FundsData:
    """Broker-agnostic funds/margin info."""

    available_margin: float = 0.0
    used_margin: float = 0.0
    total_balance: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    broker_raw: dict[str, Any] = field(default_factory=dict)


# ═════════════════════════════════════════════════════════════════
# Abstract base broker
# ═════════════════════════════════════════════════════════════════

class BaseBroker(ABC):
    """Abstract base class for all broker integrations.

    Every broker must implement these methods. All methods are async
    to avoid blocking the Qt main thread.
    """

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """Return the broker identifier string."""
        ...

    @property
    @abstractmethod
    def is_authenticated(self) -> bool:
        """Return True if the broker session is valid."""
        ...

    @abstractmethod
    async def authenticate(self) -> bool:
        """Perform authentication / token refresh.

        Returns:
            True if authentication succeeded.
        """
        ...

    @abstractmethod
    async def get_profile(self) -> dict[str, Any]:
        """Fetch the user profile from the broker.

        Returns:
            Dict with at least 'name' and 'email' keys.
        """
        ...

    @abstractmethod
    async def get_funds(self) -> FundsData:
        """Fetch account funds and margin details.

        Returns:
            FundsData instance.
        """
        ...

    @abstractmethod
    async def place_order(self, request: OrderRequest) -> OrderResponse:
        """Place a new order.

        Args:
            request: OrderRequest with all order parameters.

        Returns:
            OrderResponse with order_id and initial status.
        """
        ...

    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        updates: dict[str, Any],
    ) -> OrderResponse:
        """Modify an existing open order.

        Args:
            order_id: The broker order ID to modify.
            updates: Dict of fields to change (price, qty, etc.).

        Returns:
            OrderResponse with updated status.
        """
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order.

        Args:
            order_id: The broker order ID to cancel.

        Returns:
            True if cancellation was accepted.
        """
        ...

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Get the current status of an order.

        Args:
            order_id: The broker order ID.

        Returns:
            OrderResponse with current status.
        """
        ...

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Fetch all open positions.

        Returns:
            List of Position instances.
        """
        ...

    @abstractmethod
    async def get_orders(self) -> list[OrderResponse]:
        """Fetch all orders for today.

        Returns:
            List of OrderResponse instances.
        """
        ...

    @abstractmethod
    async def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        from_date: str,
        to_date: str,
    ) -> list[dict[str, Any]]:
        """Fetch historical OHLCV candles.

        Args:
            symbol: Broker-format symbol.
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '1D').
            from_date: Start date 'YYYY-MM-DD'.
            to_date: End date 'YYYY-MM-DD'.

        Returns:
            List of candle dicts with keys: timestamp, open, high, low,
            close, volume.
        """
        ...

    @abstractmethod
    async def subscribe_symbols(self, symbols: list[str]) -> bool:
        """Subscribe to live tick data for symbols.

        Args:
            symbols: List of broker-format symbols.

        Returns:
            True if subscription was accepted.
        """
        ...

    @abstractmethod
    async def unsubscribe_symbols(self, symbols: list[str]) -> bool:
        """Unsubscribe from live tick data.

        Args:
            symbols: List of symbols to unsubscribe.

        Returns:
            True if unsubscription was accepted.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from broker — close WebSocket, cleanup."""
        ...


__all__ = [
    "Side",
    "OrderType",
    "ProductType",
    "OrderStatus",
    "OrderRequest",
    "OrderResponse",
    "Position",
    "FundsData",
    "BaseBroker",
]
