"""
TradeOS India — Agent orchestrator.

Priority asyncio.Queue with QThread runner. Routes tasks to the correct
agent, manages LLM provider selection (market hours vs overnight),
logs results to the database, and emits signals for the UI.
"""

import asyncio
import time
from typing import Any, Optional

from PySide6.QtCore import QThread, Signal

from agents.base_agent import (
    AgentResult,
    AgentTask,
    BaseAgent,
    TaskPriority,
    TaskType,
)
from core.event_bus import EventBus
from core.state_store import AppState
from storage.db import insert_agent_log
from utils.date_utils import is_market_hours
from utils.logger import get_logger

log = get_logger("agents.orchestrator")


class AgentOrchestrator(QThread):
    """Priority task queue with async runner.

    Routes tasks to registered agents, selects the appropriate LLM
    provider based on market hours, and manages agent lifecycle.

    Signals:
        orchestrator_started: Emitted when the orchestrator starts.
        orchestrator_stopped: Emitted when the orchestrator stops.
    """

    orchestrator_started = Signal()
    orchestrator_stopped = Signal()

    def __init__(self, parent: Optional[QThread] = None) -> None:
        super().__init__(parent)
        self._agents: dict[str, BaseAgent] = {}
        self._llm_clients: dict[str, Any] = {}
        self._task_queue: asyncio.PriorityQueue[
            tuple[int, float, AgentTask]
        ] = asyncio.PriorityQueue()
        self._running = False
        self._event_bus = EventBus.get_instance()
        self._state = AppState.get_instance()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ═════════════════════════════════════════════════════════════
    # Agent registration
    # ═════════════════════════════════════════════════════════════

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent with the orchestrator.

        Args:
            agent: BaseAgent subclass instance.
        """
        self._agents[agent.agent_name] = agent
        log.info(f"Agent registered: {agent.agent_name}")

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get a registered agent by name.

        Args:
            name: Agent name.

        Returns:
            The agent, or None.
        """
        return self._agents.get(name)

    # ═════════════════════════════════════════════════════════════
    # LLM provider management
    # ═════════════════════════════════════════════════════════════

    def register_llm(self, provider: str, client: Any) -> None:
        """Register an LLM client.

        Args:
            provider: Provider name ('claude', 'openai', 'groq').
            client: BaseLLM implementation.
        """
        self._llm_clients[provider] = client
        log.info(f"LLM registered: {provider}")

    def get_active_llm(self) -> Optional[Any]:
        """Get the appropriate LLM client based on market hours.

        During market hours (9:15-15:30 IST): use llm_primary (default Claude)
        After hours / overnight: use llm_overnight (default Groq)

        Returns:
            BaseLLM instance or None.
        """
        if is_market_hours():
            provider = self._state.llm_primary
        else:
            provider = self._state.llm_overnight

        client = self._llm_clients.get(provider)
        if client:
            return client

        # Fallback to any available client
        for name, c in self._llm_clients.items():
            log.warning(f"Falling back to {name} LLM (preferred {provider} unavailable)")
            return c

        return None

    # ═════════════════════════════════════════════════════════════
    # Task submission
    # ═════════════════════════════════════════════════════════════

    def submit_task(self, task: AgentTask) -> str:
        """Submit a task to the priority queue.

        Args:
            task: AgentTask to execute.

        Returns:
            The task_id.
        """
        if self._state.agents_paused:
            log.warning(f"Agents paused, task {task.task_id} queued but paused")

        # Priority queue item: (priority, timestamp, task)
        self._task_queue.put_nowait(
            (task.priority.value, time.monotonic(), task)
        )

        self._event_bus.task_submitted.emit(task.task_id, task.task_type.value)
        log.debug(
            f"Task submitted: {task.task_id} type={task.task_type.value} "
            f"priority={task.priority.name}"
        )

        return task.task_id

    # ═════════════════════════════════════════════════════════════
    # Task routing
    # ═════════════════════════════════════════════════════════════

    def _find_agent_for_task(self, task_type: TaskType) -> Optional[BaseAgent]:
        """Find a registered agent that handles the given task type.

        Args:
            task_type: The task type.

        Returns:
            A matching agent, or None.
        """
        # Check target_agent first
        for name, agent in self._agents.items():
            if agent.can_handle(task_type):
                # Check if agent is enabled
                if not self._state.agents_enabled.get(name, True):
                    continue
                return agent
        return None

    # ═════════════════════════════════════════════════════════════
    # QThread run loop
    # ═════════════════════════════════════════════════════════════

    def run(self) -> None:
        """Main thread loop — process tasks from the priority queue."""
        self._running = True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self._state.agents_running = True
        self._event_bus.agent_started.emit("orchestrator")
        self.orchestrator_started.emit()
        log.info("Orchestrator started")

        try:
            self._loop.run_until_complete(self._process_loop())
        except Exception as exc:
            log.error(f"Orchestrator error: {exc}")
        finally:
            self._loop.close()
            self._state.agents_running = False
            self._event_bus.agent_stopped.emit("orchestrator")
            self.orchestrator_stopped.emit()
            log.info("Orchestrator stopped")

    async def _process_loop(self) -> None:
        """Async loop that drains the task queue."""
        while self._running:
            try:
                # Wait for a task with timeout (allows checking _running)
                try:
                    priority, ts, task = await asyncio.wait_for(
                        self._task_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Skip if agents are paused
                if self._state.agents_paused:
                    # Re-queue the task
                    self._task_queue.put_nowait((priority, ts, task))
                    await asyncio.sleep(1.0)
                    continue

                await self._execute_task(task)

            except Exception as exc:
                log.error(f"Process loop error: {exc}")
                await asyncio.sleep(0.5)

    async def _execute_task(self, task: AgentTask) -> None:
        """Route and execute a single task.

        Args:
            task: The task to execute.
        """
        agent = self._find_agent_for_task(task.task_type)
        if not agent:
            log.warning(f"No agent for task type {task.task_type.value}")
            self._event_bus.task_failed.emit(
                task.task_id, f"No agent for {task.task_type.value}"
            )
            return

        self._event_bus.task_started.emit(task.task_id, task.task_type.value)
        self._event_bus.agent_log.emit(
            agent.agent_name, "INFO",
            f"Executing {task.task_type.value} (id={task.task_id})"
        )

        # Inject LLM client if agent supports it
        llm = self.get_active_llm()
        if llm and hasattr(agent, "set_llm"):
            agent.set_llm(llm)

        try:
            result: AgentResult = await agent.execute(task)

            if result.success:
                self._event_bus.task_completed.emit(task.task_id, result.data)
                log.info(
                    f"Task {task.task_id} completed by {agent.agent_name} "
                    f"in {result.duration_ms}ms"
                )
            else:
                self._event_bus.task_failed.emit(task.task_id, result.error)
                log.warning(
                    f"Task {task.task_id} failed: {result.error}"
                )

            # Log to DB
            await insert_agent_log({
                "task_id": task.task_id,
                "agent_name": agent.agent_name,
                "task_type": task.task_type.value,
                "input_summary": str(task.payload)[:500],
                "output_summary": str(result.data)[:500],
                "llm_provider": llm.provider if llm else None,
                "tokens_used": result.tokens_used,
                "cost_inr": result.cost_inr,
                "duration_ms": result.duration_ms,
                "success": 1 if result.success else 0,
                "error_msg": result.error if not result.success else None,
            })

        except Exception as exc:
            log.error(f"Task {task.task_id} exception: {exc}")
            self._event_bus.task_failed.emit(task.task_id, str(exc))

    # ═════════════════════════════════════════════════════════════
    # Control
    # ═════════════════════════════════════════════════════════════

    def stop(self) -> None:
        """Signal the orchestrator to stop."""
        self._running = False
        log.info("Orchestrator stop requested")

    def pause(self) -> None:
        """Pause task processing."""
        self._state.agents_paused = True
        self._event_bus.agent_log.emit(
            "orchestrator", "WARNING", "Agents PAUSED"
        )
        log.info("Orchestrator paused")

    def resume(self) -> None:
        """Resume task processing."""
        self._state.agents_paused = False
        self._event_bus.agent_log.emit(
            "orchestrator", "INFO", "Agents RESUMED"
        )
        log.info("Orchestrator resumed")

    @property
    def is_running(self) -> bool:
        """Return True if the orchestrator is active."""
        return self._running and self.isRunning()

    @property
    def queue_size(self) -> int:
        """Return the number of pending tasks."""
        return self._task_queue.qsize()


__all__ = ["AgentOrchestrator"]
