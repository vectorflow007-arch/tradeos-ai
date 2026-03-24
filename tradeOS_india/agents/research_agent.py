"""
TradeOS India — Research Agent.

LLM-powered backtest analysis, Monte Carlo simulation evaluation,
and strategy quality assessment. Identifies overfitting and regime
weaknesses.
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

log = get_logger("agents.research_agent")

RESEARCH_SYSTEM_PROMPT = (
    "You are a quantitative research analyst. Analyze backtest results "
    "rigorously. Identify overfitting, data snooping bias, and "
    "regime-specific weaknesses.\n"
    "RESPOND ONLY IN VALID JSON:\n"
    "{\n"
    '  "stability_score": <float 0.0-1.0>,\n'
    '  "overfitting_risk": "low" | "medium" | "high",\n'
    '  "key_metrics": {\n'
    '    "sharpe_ratio": <float>,\n'
    '    "sortino_ratio": <float>,\n'
    '    "max_drawdown_pct": <float>,\n'
    '    "win_rate": <float>,\n'
    '    "profit_factor": <float>,\n'
    '    "avg_trade_duration_minutes": <float>,\n'
    '    "total_trades": <int>\n'
    "  },\n"
    '  "regime_analysis": {\n'
    '    "trending_performance": <float>,\n'
    '    "ranging_performance": <float>,\n'
    '    "volatile_performance": <float>\n'
    "  },\n"
    '  "weaknesses": [<string>],\n'
    '  "suggested_improvements": [<string>],\n'
    '  "monte_carlo_summary": <string>,\n'
    '  "anti_overfitting_gate": "PASSED" | "FAILED",\n'
    '  "recommendation": "deploy" | "optimize" | "reject"\n'
    "}"
)


class ResearchAgent(BaseAgent):
    """LLM-powered backtest and strategy analysis.

    Accepts backtest results and produces rigorous analysis including
    overfitting detection, regime breakdown, and deployment recommendation.
    """

    def __init__(self, llm_client: Any = None) -> None:
        self._llm = llm_client
        self._event_bus = EventBus.get_instance()

    @property
    def agent_name(self) -> str:
        """Return the agent identifier."""
        return "research"

    @property
    def handled_task_types(self) -> list[TaskType]:
        """Return handled task types."""
        return [TaskType.RUN_BACKTEST, TaskType.ANALYZE_BACKTEST, TaskType.RESEARCH]

    def set_llm(self, llm_client: Any) -> None:
        """Set or update the LLM client."""
        self._llm = llm_client

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute a research task.

        Args:
            task: AgentTask — ANALYZE_BACKTEST, RUN_BACKTEST, or RESEARCH.

        Returns:
            AgentResult with analysis data.
        """
        if task.task_type == TaskType.ANALYZE_BACKTEST:
            return await self._analyze_backtest(task)
        elif task.task_type == TaskType.RUN_BACKTEST:
            return await self._run_backtest(task)
        elif task.task_type == TaskType.RESEARCH:
            return await self._general_research(task)
        else:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error=f"Unhandled task type: {task.task_type}",
                agent_name=self.agent_name,
            )

    # ═════════════════════════════════════════════════════════════
    # Analyze backtest
    # ═════════════════════════════════════════════════════════════

    async def _analyze_backtest(self, task: AgentTask) -> AgentResult:
        """Analyze backtest results using LLM.

        Expected payload:
            strategy_name: str
            trades: list[dict] — trade-by-trade results
            equity_curve: list[float]
            metrics: dict — basic computed metrics
        """
        start_ms = time.monotonic()

        self._event_bus.agent_log.emit(
            "research", "INFO",
            f"Analyzing backtest: {task.payload.get('strategy_name', '?')}"
        )

        if not self._llm:
            # Return basic analysis without LLM
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=True,
                data=self._basic_analysis(task.payload),
                agent_name=self.agent_name,
                duration_ms=int((time.monotonic() - start_ms) * 1000),
            )

        user_prompt = self._build_analysis_prompt(task.payload)

        try:
            response_text = await self._llm.complete(
                system=RESEARCH_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=1200,
            )

            result_data = self._parse_response(response_text)
            duration_ms = int((time.monotonic() - start_ms) * 1000)

            if result_data.get("error"):
                result_data = self._basic_analysis(task.payload)

            recommendation = result_data.get("recommendation", "?")
            self._event_bus.agent_log.emit(
                "research", "INFO",
                f"Analysis complete: recommendation={recommendation}"
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
            log.error(f"Research agent error: {exc}")
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error=str(exc),
                agent_name=self.agent_name,
                duration_ms=int((time.monotonic() - start_ms) * 1000),
            )

    # ═════════════════════════════════════════════════════════════
    # Run backtest (placeholder)
    # ═════════════════════════════════════════════════════════════

    async def _run_backtest(self, task: AgentTask) -> AgentResult:
        """Run a strategy backtest.

        Expected payload:
            strategy_code: str
            symbol: str
            timeframe: str
            from_date: str
            to_date: str
        """
        start_ms = time.monotonic()

        self._event_bus.agent_log.emit(
            "research", "INFO",
            f"Running backtest: {task.payload.get('symbol', '?')}"
        )

        # Placeholder — actual backtesting engine would go here
        return AgentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            success=True,
            data={
                "status": "completed",
                "message": "Backtest engine placeholder",
                "trades": [],
                "metrics": {
                    "sharpe_ratio": 0.0,
                    "max_drawdown_pct": 0.0,
                    "win_rate": 0.0,
                    "total_trades": 0,
                },
            },
            agent_name=self.agent_name,
            duration_ms=int((time.monotonic() - start_ms) * 1000),
        )

    # ═════════════════════════════════════════════════════════════
    # General research
    # ═════════════════════════════════════════════════════════════

    async def _general_research(self, task: AgentTask) -> AgentResult:
        """Handle a general research query via LLM.

        Expected payload:
            query: str
        """
        start_ms = time.monotonic()

        if not self._llm:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=False,
                error="No LLM client for research",
                agent_name=self.agent_name,
            )

        query = task.payload.get("query", "")
        try:
            response = await self._llm.complete(
                system=(
                    "You are a quantitative research analyst for Indian markets. "
                    "Provide concise, data-driven answers."
                ),
                user=query,
                max_tokens=1000,
            )
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                success=True,
                data={"response": response},
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
    # Helpers
    # ═════════════════════════════════════════════════════════════

    def _build_analysis_prompt(self, payload: dict[str, Any]) -> str:
        """Build user prompt for backtest analysis."""
        metrics = payload.get("metrics", {})
        trades = payload.get("trades", [])
        equity = payload.get("equity_curve", [])

        prompt = (
            f"Strategy: {payload.get('strategy_name', 'Unknown')}\n\n"
            f"Basic metrics:\n{json.dumps(metrics, indent=2)}\n\n"
            f"Total trades: {len(trades)}\n"
        )

        if trades:
            # Show sample trades
            sample = trades[:10]
            prompt += f"Sample trades (first 10):\n{json.dumps(sample, indent=2)}\n\n"

        if equity:
            prompt += (
                f"Equity curve length: {len(equity)} points\n"
                f"Start: {equity[0] if equity else 0}\n"
                f"End: {equity[-1] if equity else 0}\n"
                f"Min: {min(equity) if equity else 0}\n"
                f"Max: {max(equity) if equity else 0}\n\n"
            )

        prompt += "Analyze this strategy thoroughly and respond with JSON."
        return prompt

    def _basic_analysis(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Simple deterministic analysis without LLM."""
        metrics = payload.get("metrics", {})
        return {
            "stability_score": 0.5,
            "overfitting_risk": "medium",
            "key_metrics": {
                "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                "sortino_ratio": metrics.get("sortino_ratio", 0),
                "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
                "win_rate": metrics.get("win_rate", 0),
                "profit_factor": metrics.get("profit_factor", 0),
                "avg_trade_duration_minutes": 0,
                "total_trades": metrics.get("total_trades", 0),
            },
            "regime_analysis": {
                "trending_performance": 0.0,
                "ranging_performance": 0.0,
                "volatile_performance": 0.0,
            },
            "weaknesses": ["No LLM analysis available"],
            "suggested_improvements": ["Connect LLM for detailed analysis"],
            "monte_carlo_summary": "Not available without LLM",
            "anti_overfitting_gate": "FAILED",
            "recommendation": "optimize",
        }

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        """Parse the LLM research response into a dict."""
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    return {"error": "JSON parse failed"}
            return {"error": "No JSON in response"}


__all__ = ["ResearchAgent", "RESEARCH_SYSTEM_PROMPT"]
