"""
TradeOS India — Risk Agent.

LLM-powered position sizing and daily loss gate. Validates proposed
trades against risk parameters, adjusts sizing, and enforces circuit
breaker rules.
"""

import json
import time
from typing import Any

from agents.base_agent import (
    AgentResult,
    AgentTask,
    BaseAgent,
    TaskType,
)
from core.event_bus import EventBus
from core.state_store import AppState
from utils.logger import get_logger

log = get_logger("agents.risk_agent")

RISK_SYSTEM_PROMPT = (
    "You are a strict risk manager for a retail trader with limited capital "
    "in Indian markets.\n"
    "Your job is to protect capital above all else. Apply conservative "
    "position sizing. Never approve trades that violate risk rules.\n"
    "RESPOND ONLY IN VALID JSON:\n"
    "{\n"
    '  "approved": <bool>,\n'
    '  "quantity": <int>,\n'
    '  "lots": <int>,\n'
    '  "adjusted_sl": <float>,\n'
    '  "adjusted_target": <float>,\n'
    '  "risk_amount_inr": <float>,\n'
    '  "risk_reward_ratio": <float>,\n'
    '  "position_size_pct": <float>,\n'
    '  "rejection_reason": <string or null>,\n'
    '  "warnings": [<string>]\n'
    "}"
)


class RiskAgent(BaseAgent):
    """LLM-powered risk validation and position sizing.

    Validates proposed trades against daily loss limits, max positions,
    stop-loss rules, and circuit breaker thresholds.
    """

    def __init__(self, llm_client: Any = None) -> None:
        self._llm = llm_client
        self._event_bus = EventBus.get_instance()
        self._state = AppState.get_instance()

    @property
    def agent_name(self) -> str:
        """Return the agent identifier."""
        return "risk"

    @property
    def handled_task_types(self) -> list[TaskType]:
        """Return handled task types."""
        return [TaskType.VALIDATE_RISK]

    def set_llm(self, llm_client: Any) -> None:
        """Set or update the LLM client."""
        self._llm = llm_client

    async def execute(self, task: AgentTask) -> AgentResult:
        """Validate a proposed trade against risk rules.

        Expected task.payload keys:
            signal: dict — the trading signal from StrategyAgent
            symbol: str — trading symbol
            capital: float — available capital
            lot_size: int — lot size for the instrument

        Args:
            task: AgentTask with VALIDATE_RISK type.

        Returns:
            AgentResult with approval decision in data.
        """
        start_ms = time.monotonic()

        self._event_bus.agent_log.emit(
            "risk", "INFO",
            f"Validating risk for {task.payload.get('symbol', '?')}"
        )

        # Pre-LLM deterministic checks
        pre_check = self._pre_validate(task.payload)
        if pre_check is not None:
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=True,
                data=pre_check,
                agent_name=self.agent_name,
                duration_ms=duration_ms,
            )

        if not self._llm:
            # No LLM — use deterministic fallback
            fallback = self._deterministic_validate(task.payload)
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=True,
                data=fallback,
                agent_name=self.agent_name,
                duration_ms=duration_ms,
            )

        # LLM validation
        user_prompt = self._build_prompt(task.payload)

        try:
            response_text = await self._llm.complete(
                system=RISK_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=600,
            )

            result_data = self._parse_response(response_text)
            duration_ms = int((time.monotonic() - start_ms) * 1000)

            if result_data.get("error"):
                # Fallback to deterministic
                result_data = self._deterministic_validate(task.payload)

            approved = result_data.get("approved", False)
            self._event_bus.agent_log.emit(
                "risk",
                "INFO" if approved else "WARNING",
                f"Risk verdict: {'APPROVED' if approved else 'REJECTED'} "
                f"for {task.payload.get('symbol', '?')}"
            )

            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=True,
                data=result_data,
                agent_name=self.agent_name,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            log.error(f"Risk agent error: {exc}")
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error=str(exc),
                agent_name=self.agent_name,
                duration_ms=duration_ms,
            )

    # ═════════════════════════════════════════════════════════════
    # Pre-validation (deterministic)
    # ═════════════════════════════════════════════════════════════

    def _pre_validate(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Run deterministic pre-checks before LLM call.

        Returns a rejection dict if a hard rule is violated, else None.
        """
        # Circuit breaker check
        loss_pct = 0.0
        if self._state.daily_loss_limit > 0:
            loss_pct = (
                self._state.daily_loss_used / self._state.daily_loss_limit
            ) * 100

        if loss_pct >= self._state.circuit_breaker_pct:
            self._event_bus.circuit_breaker_triggered.emit(loss_pct)
            self._event_bus.agent_log.emit(
                "risk", "CRITICAL",
                f"Circuit breaker! Loss at {loss_pct:.1f}%"
            )
            return {
                "approved": False,
                "quantity": 0,
                "lots": 0,
                "adjusted_sl": 0,
                "adjusted_target": 0,
                "risk_amount_inr": 0,
                "risk_reward_ratio": 0,
                "position_size_pct": 0,
                "rejection_reason": (
                    f"Circuit breaker triggered: daily loss at "
                    f"{loss_pct:.1f}% of limit"
                ),
                "warnings": ["CIRCUIT_BREAKER"],
            }

        # Max positions check
        if len(self._state.open_positions) >= self._state.max_positions:
            return {
                "approved": False,
                "quantity": 0,
                "lots": 0,
                "adjusted_sl": 0,
                "adjusted_target": 0,
                "risk_amount_inr": 0,
                "risk_reward_ratio": 0,
                "position_size_pct": 0,
                "rejection_reason": (
                    f"Max positions reached: "
                    f"{len(self._state.open_positions)}/{self._state.max_positions}"
                ),
                "warnings": ["MAX_POSITIONS"],
            }

        # Daily loss remaining check
        remaining = self._state.daily_loss_limit - self._state.daily_loss_used
        if remaining <= 0:
            return {
                "approved": False,
                "quantity": 0,
                "lots": 0,
                "adjusted_sl": 0,
                "adjusted_target": 0,
                "risk_amount_inr": 0,
                "risk_reward_ratio": 0,
                "position_size_pct": 0,
                "rejection_reason": "Daily loss limit exhausted",
                "warnings": ["DAILY_LIMIT_HIT"],
            }

        return None  # Pass to LLM

    # ═════════════════════════════════════════════════════════════
    # Deterministic fallback
    # ═════════════════════════════════════════════════════════════

    def _deterministic_validate(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Simple rule-based risk validation without LLM.

        Used as fallback when LLM is unavailable or returns bad data.
        """
        signal = payload.get("signal", {})
        capital = payload.get("capital", 100000.0)
        lot_size = payload.get("lot_size", 1)

        entry = signal.get("entry_price", 0.0)
        sl = signal.get("stop_loss", 0.0)
        target = signal.get("target_1", 0.0)

        if entry <= 0 or sl <= 0:
            return {
                "approved": False,
                "quantity": 0,
                "lots": 0,
                "adjusted_sl": sl,
                "adjusted_target": target,
                "risk_amount_inr": 0,
                "risk_reward_ratio": 0,
                "position_size_pct": 0,
                "rejection_reason": "Invalid entry or stop-loss price",
                "warnings": [],
            }

        # Risk per trade
        risk_pct = self._state.risk_per_trade_pct / 100.0
        risk_amount = capital * risk_pct
        risk_per_unit = abs(entry - sl)

        if risk_per_unit <= 0:
            return {
                "approved": False,
                "quantity": 0,
                "lots": 0,
                "adjusted_sl": sl,
                "adjusted_target": target,
                "risk_amount_inr": 0,
                "risk_reward_ratio": 0,
                "position_size_pct": 0,
                "rejection_reason": "Stop-loss equals entry price",
                "warnings": [],
            }

        # SL percentage check
        sl_pct = (risk_per_unit / entry) * 100
        warnings: list[str] = []
        if sl_pct > self._state.max_sl_pct:
            warnings.append(f"SL at {sl_pct:.1f}% exceeds max {self._state.max_sl_pct}%")

        # Position sizing
        quantity = int(risk_amount / risk_per_unit)
        quantity = max(lot_size, (quantity // lot_size) * lot_size)
        lots = quantity // lot_size

        actual_risk = quantity * risk_per_unit
        rr_ratio = abs(target - entry) / risk_per_unit if target > 0 else 0
        position_pct = (quantity * entry / capital) * 100

        return {
            "approved": True,
            "quantity": quantity,
            "lots": lots,
            "adjusted_sl": sl,
            "adjusted_target": target,
            "risk_amount_inr": round(actual_risk, 2),
            "risk_reward_ratio": round(rr_ratio, 2),
            "position_size_pct": round(position_pct, 2),
            "rejection_reason": None,
            "warnings": warnings,
        }

    # ═════════════════════════════════════════════════════════════
    # Prompt building
    # ═════════════════════════════════════════════════════════════

    def _build_prompt(self, payload: dict[str, Any]) -> str:
        """Build user prompt for LLM risk validation."""
        signal = payload.get("signal", {})
        capital = payload.get("capital", 100000.0)
        lot_size = payload.get("lot_size", 1)

        remaining_loss = (
            self._state.daily_loss_limit - self._state.daily_loss_used
        )

        return (
            f"Symbol: {payload.get('symbol', 'UNKNOWN')}\n"
            f"Signal: {json.dumps(signal, indent=2)}\n\n"
            f"Account capital: INR {capital:,.0f}\n"
            f"Lot size: {lot_size}\n"
            f"Risk per trade: {self._state.risk_per_trade_pct}%\n"
            f"Max SL: {self._state.max_sl_pct}%\n"
            f"Daily loss limit: INR {self._state.daily_loss_limit:,.0f}\n"
            f"Daily loss used: INR {self._state.daily_loss_used:,.0f}\n"
            f"Remaining loss budget: INR {remaining_loss:,.0f}\n"
            f"Open positions: {len(self._state.open_positions)}/{self._state.max_positions}\n"
            f"\nValidate this trade and respond with JSON."
        )

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        """Parse the LLM risk response into a dict."""
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start:end])
                except json.JSONDecodeError:
                    return {"error": "JSON parse failed"}
            else:
                return {"error": "No JSON in response"}

        if "approved" not in data:
            return {"error": "Missing 'approved' field"}

        return data


__all__ = ["RiskAgent", "RISK_SYSTEM_PROMPT"]
