"""
TradeOS India — Strategy Agent.

LLM-powered signal generation. Sends OHLCV candle data and market
context to the LLM, receives a structured JSON trading signal.
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
from utils.logger import get_logger

log = get_logger("agents.strategy_agent")

STRATEGY_SYSTEM_PROMPT = (
    "You are an expert quantitative trader specializing in Indian equity "
    "and derivatives markets (NSE, BSE, NFO, MCX). You have deep knowledge "
    "of technical analysis, options Greeks, volatility patterns, and Indian "
    "market microstructure.\n"
    "Given OHLCV candle data, current market context, and optional news "
    "sentiment, generate a precise trading signal.\n"
    "RESPOND ONLY IN VALID JSON. No explanation outside the JSON.\n"
    "Required JSON structure:\n"
    "{\n"
    '  "signal": "BUY" | "SELL" | "HOLD",\n'
    '  "confidence": <float 0.0-1.0>,\n'
    '  "entry_price": <float>,\n'
    '  "stop_loss": <float>,\n'
    '  "target_1": <float>,\n'
    '  "target_2": <float>,\n'
    '  "risk_reward": <float>,\n'
    '  "timeframe": <string>,\n'
    '  "reasoning": <string max 100 words>,\n'
    '  "indicators_used": [<string>],\n'
    '  "market_regime": "trending" | "ranging" | "volatile" | "breakout",\n'
    '  "expiry_preference": <string or null>,\n'
    '  "option_type": "CE" | "PE" | null,\n'
    '  "strike_preference": <float or null>\n'
    "}"
)


class StrategyAgent(BaseAgent):
    """LLM-powered trading signal generator.

    Accepts GENERATE_SIGNAL tasks, sends market data to the configured
    LLM provider, and returns a structured trading signal.
    """

    def __init__(self, llm_client: Any = None) -> None:
        self._llm = llm_client
        self._event_bus = EventBus.get_instance()

    @property
    def agent_name(self) -> str:
        """Return the agent identifier."""
        return "strategy"

    @property
    def handled_task_types(self) -> list[TaskType]:
        """Return handled task types."""
        return [TaskType.GENERATE_SIGNAL]

    def set_llm(self, llm_client: Any) -> None:
        """Set or update the LLM client.

        Args:
            llm_client: An instance implementing BaseLLM.
        """
        self._llm = llm_client

    async def execute(self, task: AgentTask) -> AgentResult:
        """Generate a trading signal from market data.

        Expected task.payload keys:
            symbol: str — trading symbol
            candles: list[dict] — recent OHLCV candles
            context: str — optional market context
            timeframe: str — candle timeframe

        Args:
            task: AgentTask with GENERATE_SIGNAL type.

        Returns:
            AgentResult with parsed signal in data.
        """
        start_ms = time.monotonic()

        self._event_bus.agent_log.emit(
            "strategy", "INFO",
            f"Generating signal for {task.payload.get('symbol', '?')}"
        )

        if not self._llm:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error="No LLM client configured",
                agent_name=self.agent_name,
            )

        # Build user prompt from payload
        symbol = task.payload.get("symbol", "UNKNOWN")
        candles = task.payload.get("candles", [])
        context = task.payload.get("context", "")
        timeframe = task.payload.get("timeframe", "15m")

        user_prompt = self._build_prompt(symbol, candles, context, timeframe)

        try:
            response_text = await self._llm.complete(
                system=STRATEGY_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=800,
            )

            signal_data = self._parse_signal(response_text)
            duration_ms = int((time.monotonic() - start_ms) * 1000)

            if signal_data.get("error"):
                self._event_bus.agent_log.emit(
                    "strategy", "WARNING",
                    f"Signal parse error: {signal_data['error']}"
                )
                return AgentResult(
                    task_id=task.task_id,
                    task_type=task.task_type,
                    success=False,
                    error=signal_data["error"],
                    agent_name=self.agent_name,
                    duration_ms=duration_ms,
                )

            self._event_bus.agent_log.emit(
                "strategy", "INFO",
                f"Signal: {signal_data.get('signal')} "
                f"{symbol} confidence={signal_data.get('confidence', 0):.2f}"
            )

            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=True,
                data=signal_data,
                agent_name=self.agent_name,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            log.error(f"Strategy agent error: {exc}")
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error=str(exc),
                agent_name=self.agent_name,
                duration_ms=duration_ms,
            )

    def _build_prompt(
        self,
        symbol: str,
        candles: list[dict[str, Any]],
        context: str,
        timeframe: str,
    ) -> str:
        """Build the user prompt for signal generation.

        Args:
            symbol: Trading symbol.
            candles: Recent OHLCV candle dicts.
            context: Optional market context.
            timeframe: Candle timeframe.

        Returns:
            Formatted user prompt string.
        """
        candle_text = ""
        for c in candles[-20:]:  # Last 20 candles max
            candle_text += (
                f"  ts={c.get('timestamp', 0)} "
                f"O={c.get('open', 0)} H={c.get('high', 0)} "
                f"L={c.get('low', 0)} C={c.get('close', 0)} "
                f"V={c.get('volume', 0)}\n"
            )

        prompt = (
            f"Symbol: {symbol}\n"
            f"Timeframe: {timeframe}\n"
            f"Recent candles (OHLCV):\n{candle_text}\n"
        )
        if context:
            prompt += f"Market context: {context}\n"
        prompt += "\nGenerate a trading signal as JSON."
        return prompt

    def _parse_signal(self, response_text: str) -> dict[str, Any]:
        """Parse the LLM response into a signal dict.

        Attempts to extract JSON from the response, handles cases where
        the LLM wraps JSON in markdown code blocks.

        Args:
            response_text: Raw LLM response.

        Returns:
            Parsed signal dict, or dict with 'error' key.
        """
        text = response_text.strip()

        # Strip markdown code block wrappers
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start:end])
                except json.JSONDecodeError as exc:
                    return {"error": f"JSON parse failed: {exc}"}
            else:
                return {"error": "No JSON found in response"}

        # Validate required fields
        required = ["signal", "confidence"]
        for field in required:
            if field not in data:
                return {"error": f"Missing required field: {field}"}

        if data["signal"] not in ("BUY", "SELL", "HOLD"):
            return {"error": f"Invalid signal: {data['signal']}"}

        return data


__all__ = ["StrategyAgent", "STRATEGY_SYSTEM_PROMPT"]
