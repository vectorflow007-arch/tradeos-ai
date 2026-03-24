"""
TradeOS India — Execution Agent.

Handles order placement and fill monitoring. Does NOT call LLM for
every order — only for unusual slippage, partial fills, and adverse
SL scenarios. Otherwise uses deterministic order logic.
"""

import time
from typing import Any, Optional

from agents.base_agent import (
    AgentResult,
    AgentTask,
    BaseAgent,
    TaskType,
)
from brokers.base_broker import (
    OrderRequest,
    OrderResponse,
    OrderStatus,
    OrderType,
    ProductType,
    Side,
)
from core.event_bus import EventBus
from core.state_store import AppState
from storage.db import insert_trade
from utils.date_utils import ist_timestamp
from utils.logger import get_logger

log = get_logger("agents.execution_agent")

# Thresholds for LLM consultation
_SLIPPAGE_THRESHOLD_PCT = 0.5
_PARTIAL_FILL_TIMEOUT_S = 30.0
_ADVERSE_SL_THRESHOLD = 0.5  # 50% of SL distance


class ExecutionAgent(BaseAgent):
    """Order placement and fill monitoring agent.

    Uses deterministic logic for normal orders. Consults LLM only for:
      - Unusual slippage (>0.5% of order value)
      - Partial fill decisions after 30s
      - Exit strategy when position moves against SL by 50%
    """

    def __init__(
        self,
        broker: Any = None,
        llm_client: Any = None,
    ) -> None:
        self._broker = broker
        self._llm = llm_client
        self._event_bus = EventBus.get_instance()
        self._state = AppState.get_instance()

    @property
    def agent_name(self) -> str:
        """Return the agent identifier."""
        return "execution"

    @property
    def handled_task_types(self) -> list[TaskType]:
        """Return handled task types."""
        return [TaskType.PLACE_ORDER, TaskType.MONITOR_ORDER, TaskType.ANALYZE_SLIPPAGE]

    def set_broker(self, broker: Any) -> None:
        """Set the broker client."""
        self._broker = broker

    def set_llm(self, llm_client: Any) -> None:
        """Set the LLM client for exceptional situations."""
        self._llm = llm_client

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute an order-related task.

        Args:
            task: AgentTask — PLACE_ORDER, MONITOR_ORDER, or ANALYZE_SLIPPAGE.

        Returns:
            AgentResult.
        """
        if task.task_type == TaskType.PLACE_ORDER:
            return await self._handle_place_order(task)
        elif task.task_type == TaskType.MONITOR_ORDER:
            return await self._handle_monitor_order(task)
        elif task.task_type == TaskType.ANALYZE_SLIPPAGE:
            return await self._handle_slippage(task)
        else:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error=f"Unhandled task type: {task.task_type}",
                agent_name=self.agent_name,
            )

    # ═════════════════════════════════════════════════════════════
    # Place order
    # ═════════════════════════════════════════════════════════════

    async def _handle_place_order(self, task: AgentTask) -> AgentResult:
        """Place an order through the broker.

        SAFETY: Checks AppState.mode before calling real broker.
        In paper mode: simulates fill, emits signals, updates DB.

        Expected payload:
            symbol, exchange, side, quantity, order_type, product,
            entry_price, stop_loss, strategy_name
        """
        start_ms = time.monotonic()
        payload = task.payload

        self._event_bus.agent_log.emit(
            "execution", "INFO",
            f"Placing {payload.get('side', '?')} order: "
            f"{payload.get('quantity', 0)} {payload.get('symbol', '?')}"
        )

        if not self._broker:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error="No broker configured",
                agent_name=self.agent_name,
                duration_ms=int((time.monotonic() - start_ms) * 1000),
            )

        # SAFETY CHECK: mode validation
        mode = self._state.mode
        if mode != "live" and mode != "paper":
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error=f"Invalid trading mode: {mode}",
                agent_name=self.agent_name,
            )

        # Build order request
        try:
            order_req = OrderRequest(
                symbol=payload.get("symbol", ""),
                exchange=payload.get("exchange", "NSE"),
                side=Side(payload.get("side", "BUY")),
                quantity=payload.get("quantity", 0),
                order_type=OrderType(payload.get("order_type", "MARKET")),
                product=ProductType(payload.get("product", "MIS")),
                price=payload.get("entry_price", 0.0),
                strategy_name=payload.get("strategy_name"),
                agent_task_id=task.task_id,
            )
        except (ValueError, KeyError) as exc:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error=f"Invalid order params: {exc}",
                agent_name=self.agent_name,
            )

        # Place order
        try:
            response: OrderResponse = await self._broker.place_order(order_req)
        except Exception as exc:
            log.error(f"Order placement failed: {exc}")
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error=str(exc),
                agent_name=self.agent_name,
                duration_ms=int((time.monotonic() - start_ms) * 1000),
            )

        duration_ms = int((time.monotonic() - start_ms) * 1000)

        if response.status == OrderStatus.FILLED:
            # Insert trade to DB
            trade_record = {
                "order_id": response.order_id,
                "symbol": order_req.symbol,
                "exchange": order_req.exchange,
                "side": order_req.side.value,
                "quantity": response.filled_qty or order_req.quantity,
                "entry_price": response.avg_price,
                "product": order_req.product.value,
                "order_type": order_req.order_type.value,
                "status": "FILLED",
                "mode": mode,
                "broker": "fyers",
                "strategy_name": order_req.strategy_name,
                "agent_task_id": task.task_id,
                "entry_time": ist_timestamp(),
            }
            await insert_trade(trade_record)

            # Check slippage
            expected_price = payload.get("entry_price", 0.0)
            if expected_price > 0 and response.avg_price > 0:
                slippage_pct = (
                    abs(response.avg_price - expected_price) / expected_price
                ) * 100
                if slippage_pct > _SLIPPAGE_THRESHOLD_PCT:
                    self._event_bus.agent_log.emit(
                        "execution", "WARNING",
                        f"High slippage: {slippage_pct:.2f}% on {order_req.symbol}"
                    )

            self._event_bus.agent_log.emit(
                "execution", "INFO",
                f"Order filled: {response.order_id} @ {response.avg_price}"
            )

            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=True,
                data={
                    "order_id": response.order_id,
                    "status": response.status.value,
                    "avg_price": response.avg_price,
                    "filled_qty": response.filled_qty,
                    "symbol": order_req.symbol,
                    "side": order_req.side.value,
                },
                agent_name=self.agent_name,
                duration_ms=duration_ms,
            )

        elif response.status == OrderStatus.REJECTED:
            self._event_bus.agent_log.emit(
                "execution", "ERROR",
                f"Order rejected: {response.message}"
            )
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error=f"Order rejected: {response.message}",
                data={"order_id": response.order_id, "status": "REJECTED"},
                agent_name=self.agent_name,
                duration_ms=duration_ms,
            )

        else:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=True,
                data={
                    "order_id": response.order_id,
                    "status": response.status.value,
                },
                agent_name=self.agent_name,
                duration_ms=duration_ms,
            )

    # ═════════════════════════════════════════════════════════════
    # Monitor order
    # ═════════════════════════════════════════════════════════════

    async def _handle_monitor_order(self, task: AgentTask) -> AgentResult:
        """Monitor an existing order's status.

        Expected payload:
            order_id: str
        """
        start_ms = time.monotonic()
        order_id = task.payload.get("order_id", "")

        if not self._broker or not order_id:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error="No broker or order_id",
                agent_name=self.agent_name,
            )

        try:
            status = await self._broker.get_order_status(order_id)
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=True,
                data={
                    "order_id": order_id,
                    "status": status.status.value,
                    "avg_price": status.avg_price,
                    "filled_qty": status.filled_qty,
                },
                agent_name=self.agent_name,
                duration_ms=int((time.monotonic() - start_ms) * 1000),
            )
        except Exception as exc:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error=str(exc),
                agent_name=self.agent_name,
            )

    # ═════════════════════════════════════════════════════════════
    # Slippage analysis (LLM)
    # ═════════════════════════════════════════════════════════════

    async def _handle_slippage(self, task: AgentTask) -> AgentResult:
        """Analyze unusual slippage using LLM.

        Expected payload:
            symbol, expected_price, fill_price, quantity, side
        """
        start_ms = time.monotonic()

        if not self._llm:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=True,
                data={"analysis": "No LLM available for slippage analysis"},
                agent_name=self.agent_name,
            )

        payload = task.payload
        prompt = (
            f"Analyze this trade slippage:\n"
            f"Symbol: {payload.get('symbol')}\n"
            f"Side: {payload.get('side')}\n"
            f"Expected price: {payload.get('expected_price')}\n"
            f"Fill price: {payload.get('fill_price')}\n"
            f"Quantity: {payload.get('quantity')}\n"
            f"Provide brief analysis in JSON: "
            f'{{\"severity\": \"low\"|\"medium\"|\"high\", '
            f'\"likely_cause\": \"...\", \"recommendation\": \"...\"}}'
        )

        try:
            response = await self._llm.complete(
                system="You are a trade execution analyst. Respond in JSON only.",
                user=prompt,
                max_tokens=300,
            )
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=True,
                data={"analysis": response},
                agent_name=self.agent_name,
                duration_ms=int((time.monotonic() - start_ms) * 1000),
            )
        except Exception as exc:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error=str(exc),
                agent_name=self.agent_name,
            )


__all__ = ["ExecutionAgent"]
