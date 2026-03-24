"""
TradeOS India — Abstract base agent and shared dataclasses.

All agents inherit BaseAgent and implement execute(). AgentTask and
AgentResult provide a uniform task/result envelope for the orchestrator.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from utils.date_utils import ist_timestamp


# ═════════════════════════════════════════════════════════════════
# Enums
# ═════════════════════════════════════════════════════════════════

class TaskType(str, Enum):
    """All supported agent task types."""
    GENERATE_SIGNAL = "GENERATE_SIGNAL"
    VALIDATE_RISK = "VALIDATE_RISK"
    PLACE_ORDER = "PLACE_ORDER"
    MONITOR_ORDER = "MONITOR_ORDER"
    ANALYZE_SLIPPAGE = "ANALYZE_SLIPPAGE"
    RUN_BACKTEST = "RUN_BACKTEST"
    ANALYZE_BACKTEST = "ANALYZE_BACKTEST"
    RESEARCH = "RESEARCH"


class TaskPriority(int, Enum):
    """Task priority levels (lower number = higher priority)."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class AgentStatus(str, Enum):
    """Agent lifecycle status."""
    IDLE = "idle"
    RUNNING = "running"
    THINKING = "thinking"
    ERROR = "error"
    STOPPED = "stopped"


# ═════════════════════════════════════════════════════════════════
# Dataclasses
# ═════════════════════════════════════════════════════════════════

@dataclass
class AgentTask:
    """A unit of work submitted to the agent orchestrator."""

    task_type: TaskType
    payload: dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=ist_timestamp)
    source_agent: str = ""
    target_agent: str = ""
    timeout_s: float = 30.0


@dataclass
class AgentResult:
    """Result returned by an agent after executing a task."""

    task_id: str
    task_type: TaskType
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    agent_name: str = ""
    duration_ms: int = 0
    tokens_used: int = 0
    cost_inr: float = 0.0
    created_at: str = field(default_factory=ist_timestamp)


# ═════════════════════════════════════════════════════════════════
# Abstract base agent
# ═════════════════════════════════════════════════════════════════

class BaseAgent(ABC):
    """Abstract base class for all autonomous agents.

    Subclasses must implement:
      - agent_name property
      - handled_task_types property
      - execute(task) async method
    """

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Return the agent identifier (e.g. 'strategy', 'risk')."""
        ...

    @property
    @abstractmethod
    def handled_task_types(self) -> list[TaskType]:
        """Return the list of TaskTypes this agent can handle."""
        ...

    @abstractmethod
    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute a task and return the result.

        Args:
            task: The AgentTask to process.

        Returns:
            AgentResult with success/failure and data.
        """
        ...

    def can_handle(self, task_type: TaskType) -> bool:
        """Check if this agent handles a given task type.

        Args:
            task_type: The task type to check.

        Returns:
            True if this agent handles the task type.
        """
        return task_type in self.handled_task_types


__all__ = [
    "TaskType",
    "TaskPriority",
    "AgentStatus",
    "AgentTask",
    "AgentResult",
    "BaseAgent",
]
