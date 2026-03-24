"""
TradeOS India — Agent Monitor screen.

Real-time view of all 4 autonomous agents: status, task queue,
logs, LLM token usage, and performance metrics.
"""

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QPlainTextEdit, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core.event_bus import EventBus
from core.state_store import AppState
from utils.logger import get_logger

log = get_logger("ui.screens.agent_monitor")

_AGENTS = [
    ("Strategy", "#569cd6", "Generates BUY/SELL/HOLD signals via LLM"),
    ("Risk", "#dcdcaa", "Validates trades against risk rules"),
    ("Execution", "#4ec9b0", "Places and manages broker orders"),
    ("Research", "#c586c0", "Backtests and analyzes strategies"),
]


class AgentCard(QFrame):
    """Single agent status card."""

    def __init__(self, name: str, color: str, desc: str, parent=None) -> None:
        super().__init__(parent)
        self.agent_name = name
        self.setStyleSheet(
            f"QFrame {{ background-color: #252526; border: 1px solid #3e3e42;"
            f" border-radius: 6px; border-left: 3px solid {color}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # Header row
        header = QHBoxLayout()
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: 600;"
            " background: transparent;"
        )
        self._status_lbl = QLabel("IDLE")
        self._status_lbl.setStyleSheet(
            "color: #858585; font-size: 10px; font-weight: 600;"
            " background: #1e1e1e; padding: 2px 8px; border-radius: 3px;"
        )
        header.addWidget(name_lbl)
        header.addStretch()
        header.addWidget(self._status_lbl)
        layout.addLayout(header)

        # Description
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(
            "color: #858585; font-size: 11px; background: transparent;"
        )
        layout.addWidget(desc_lbl)

        # Metrics row
        metrics = QHBoxLayout()
        metrics.setSpacing(16)

        self._tasks_lbl = QLabel("Tasks: 0")
        self._tasks_lbl.setStyleSheet(
            "color: #9a9a9a; font-size: 11px; background: transparent;"
        )
        self._tokens_lbl = QLabel("Tokens: 0")
        self._tokens_lbl.setStyleSheet(
            "color: #9a9a9a; font-size: 11px; background: transparent;"
        )
        self._cost_lbl = QLabel("Cost: 0.00")
        self._cost_lbl.setStyleSheet(
            "color: #9a9a9a; font-size: 11px; background: transparent;"
        )

        metrics.addWidget(self._tasks_lbl)
        metrics.addWidget(self._tokens_lbl)
        metrics.addWidget(self._cost_lbl)
        metrics.addStretch()
        layout.addLayout(metrics)

    def set_status(self, status: str) -> None:
        colors = {
            "RUNNING": "#4ec9b0",
            "IDLE": "#858585",
            "ERROR": "#f44747",
            "PAUSED": "#dcdcaa",
        }
        c = colors.get(status.upper(), "#858585")
        self._status_lbl.setText(status.upper())
        self._status_lbl.setStyleSheet(
            f"color: {c}; font-size: 10px; font-weight: 600;"
            f" background: #1e1e1e; padding: 2px 8px; border-radius: 3px;"
        )

    def update_metrics(self, tasks: int, tokens: int, cost: float) -> None:
        self._tasks_lbl.setText(f"Tasks: {tasks}")
        self._tokens_lbl.setText(f"Tokens: {tokens:,}")
        self._cost_lbl.setText(f"Cost: \u20b9{cost:.2f}")


class AgentMonitorScreen(QWidget):
    """Agent monitor — shows all 4 agents, task queue, and live logs."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("AgentMonitorScreen")

        self._event_bus = EventBus.get_instance()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Splitter: top (cards + queue) | bottom (log) ─────
        splitter = QSplitter(Qt.Vertical)

        # Top section
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(16, 12, 16, 8)
        top_layout.setSpacing(12)

        # Agent cards grid
        cards_grid = QGridLayout()
        cards_grid.setSpacing(10)

        self._agent_cards = {}
        for i, (name, color, desc) in enumerate(_AGENTS):
            card = AgentCard(name, color, desc)
            cards_grid.addWidget(card, i // 2, i % 2)
            self._agent_cards[name.lower()] = card

        top_layout.addLayout(cards_grid)

        # Task queue table
        queue_header = QLabel("TASK QUEUE")
        queue_header.setStyleSheet(
            "color: #858585; font-size: 11px; font-weight: 600;"
            " letter-spacing: 0.5px; padding-top: 4px;"
        )
        top_layout.addWidget(queue_header)

        self._queue_table = QTableWidget(0, 5)
        self._queue_table.setHorizontalHeaderLabels([
            "Priority", "Task Type", "Agent", "Status", "Created",
        ])
        self._queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._queue_table.setAlternatingRowColors(True)
        self._queue_table.setMaximumHeight(160)
        self._queue_table.setStyleSheet(
            "QTableWidget { background-color: #1e1e1e;"
            " alternate-background-color: #252526;"
            " border: 1px solid #3e3e42; border-radius: 4px; }"
        )
        self._queue_table.verticalHeader().setVisible(False)
        self._queue_table.setEditTriggers(QTableWidget.NoEditTriggers)
        top_layout.addWidget(self._queue_table)

        splitter.addWidget(top)

        # Bottom: live agent log
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(16, 8, 16, 12)

        log_header = QLabel("AGENT LOG")
        log_header.setStyleSheet(
            "color: #858585; font-size: 11px; font-weight: 600;"
            " letter-spacing: 0.5px; padding-bottom: 4px;"
        )
        bottom_layout.addWidget(log_header)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(500)
        self._log_view.setStyleSheet(
            "QPlainTextEdit { background-color: #1a1d23; color: #d4d4d4;"
            " font-family: 'Cascadia Code', 'Consolas', monospace;"
            " font-size: 12px; border: 1px solid #3e3e42; border-radius: 4px;"
            " padding: 8px; }"
        )
        self._log_view.setPlainText(
            "[09:15:00] [ORCHESTRATOR] Agent system initialized\n"
            "[09:15:01] [STRATEGY] Waiting for market data...\n"
            "[09:15:01] [RISK] Daily limits loaded: max loss \u20b95,000\n"
            "[09:15:01] [EXECUTION] Paper mode active\n"
            "[09:15:02] [RESEARCH] Ready for backtest tasks\n"
        )
        bottom_layout.addWidget(self._log_view)

        splitter.addWidget(bottom)
        splitter.setSizes([400, 300])

        layout.addWidget(splitter, 1)

        # Connect event bus
        self._event_bus.agent_log.connect(self._on_agent_log)

    def _on_agent_log(self, agent: str, level: str, message: str) -> None:
        """Append agent log entry."""
        from utils.date_utils import ist_time_str
        time_str = ist_time_str()
        self._log_view.appendPlainText(
            f"[{time_str}] [{agent.upper()}] {message}"
        )

    def update_agent_status(self, agent: str, status: str) -> None:
        card = self._agent_cards.get(agent.lower())
        if card:
            card.set_status(status)


__all__ = ["AgentMonitorScreen"]
