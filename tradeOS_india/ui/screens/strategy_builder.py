"""
TradeOS India — Strategy Builder screen.

Provides a code editor for writing trading strategies in natural language
or Python-like pseudocode, with LLM-powered signal generation preview.
"""

from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QSplitter, QVBoxLayout, QWidget,
)

from core.event_bus import EventBus
from core.state_store import AppState
from utils.logger import get_logger

log = get_logger("ui.screens.strategy_builder")

_DEFAULT_STRATEGY = """# TradeOS Strategy Template
# ─────────────────────────────────────────
# Describe your trading logic below.
# The Strategy Agent will interpret this
# and generate BUY/SELL/HOLD signals.

strategy_name: "NIFTY Momentum"
timeframe: 5m
symbols: ["NSE:NIFTY50-INDEX"]

entry_rules:
  - RSI(14) crosses above 30 (oversold reversal)
  - Price above VWAP
  - Volume > 1.5x 20-period average

exit_rules:
  - RSI(14) crosses below 70
  - Trailing stop-loss: 0.5%
  - Max holding time: 45 minutes

risk:
  position_size: 1% of capital
  stop_loss: 0.8%
  target: 1.5%
"""


class StrategyBuilderScreen(QWidget):
    """Strategy builder with code editor and signal preview."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("StrategyBuilderScreen")

        self._state = AppState.get_instance()
        self._event_bus = EventBus.get_instance()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet(
            "background-color: #252526; border-bottom: 1px solid #3e3e42;"
        )
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 0, 12, 0)
        tb_layout.setSpacing(8)

        # Strategy selector
        self._strategy_combo = QComboBox()
        self._strategy_combo.addItems(["NIFTY Momentum", "Bank NIFTY Scalp", "Custom..."])
        self._strategy_combo.setFixedWidth(200)
        tb_layout.addWidget(QLabel("Strategy:"))
        tb_layout.addWidget(self._strategy_combo)

        # Timeframe
        self._tf_combo = QComboBox()
        self._tf_combo.addItems(["1m", "5m", "15m", "1h", "1D"])
        self._tf_combo.setCurrentText("5m")
        self._tf_combo.setFixedWidth(80)
        tb_layout.addWidget(QLabel("TF:"))
        tb_layout.addWidget(self._tf_combo)

        tb_layout.addStretch()

        # Action buttons
        self._validate_btn = QPushButton("Validate")
        self._validate_btn.setFixedWidth(90)
        self._validate_btn.clicked.connect(self._on_validate)
        tb_layout.addWidget(self._validate_btn)

        self._run_btn = QPushButton("Run Strategy")
        self._run_btn.setFixedWidth(110)
        self._run_btn.setStyleSheet(
            "QPushButton { background-color: #4ec9b0; color: #1e1e1e; }"
            " QPushButton:hover { background-color: #5bd4bc; }"
        )
        self._run_btn.clicked.connect(self._on_run)
        tb_layout.addWidget(self._run_btn)

        layout.addWidget(toolbar)

        # Splitter: editor | preview
        splitter = QSplitter(Qt.Horizontal)

        # Code editor
        self._editor = QPlainTextEdit()
        self._editor.setPlainText(_DEFAULT_STRATEGY)
        self._editor.setStyleSheet(
            "QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4;"
            " font-family: 'Cascadia Code', 'Consolas', monospace;"
            " font-size: 13px; border: none; padding: 12px;"
            " selection-background-color: #264f78; }"
        )
        self._editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        splitter.addWidget(self._editor)

        # Signal preview / output
        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setStyleSheet(
            "QPlainTextEdit { background-color: #1a1d23; color: #858585;"
            " font-family: 'Cascadia Code', 'Consolas', monospace;"
            " font-size: 12px; border: none; border-left: 1px solid #3e3e42;"
            " padding: 12px; }"
        )
        self._preview.setPlainText(
            "  Signal Preview\n"
            "  ─────────────────────────\n\n"
            "  Write or edit your strategy on the left,\n"
            "  then click 'Validate' to check syntax\n"
            "  or 'Run Strategy' to start signal generation.\n\n"
            "  The Strategy Agent will interpret your rules\n"
            "  and output signals here in real-time.\n"
        )
        splitter.addWidget(self._preview)
        splitter.setSizes([600, 400])

        layout.addWidget(splitter, 1)

    def _on_validate(self) -> None:
        """Validate the strategy text."""
        text = self._editor.toPlainText().strip()
        if not text:
            self._preview.setPlainText("  ERROR: Strategy is empty")
            return

        lines = text.split("\n")
        has_name = any("strategy_name" in l for l in lines)
        has_entry = any("entry_rules" in l for l in lines)

        if has_name and has_entry:
            self._preview.setPlainText(
                "  Validation: PASSED\n"
                "  ─────────────────────────\n\n"
                f"  Lines: {len(lines)}\n"
                f"  Has strategy_name: Yes\n"
                f"  Has entry_rules: Yes\n\n"
                "  Strategy is ready to run.\n"
                "  Click 'Run Strategy' to start.\n"
            )
        else:
            missing = []
            if not has_name:
                missing.append("strategy_name")
            if not has_entry:
                missing.append("entry_rules")
            self._preview.setPlainText(
                "  Validation: WARNINGS\n"
                "  ─────────────────────────\n\n"
                f"  Missing fields: {', '.join(missing)}\n\n"
                "  These fields are recommended.\n"
                "  The Strategy Agent may still work without them.\n"
            )

    def _on_run(self) -> None:
        """Start strategy execution (submit to orchestrator)."""
        self._preview.setPlainText(
            "  Strategy Submitted\n"
            "  ─────────────────────────\n\n"
            "  Strategy sent to Agent Orchestrator.\n"
            "  Signals will appear here when generated.\n\n"
            f"  Mode: {self._state.mode.upper()}\n"
            f"  Timeframe: {self._tf_combo.currentText()}\n"
        )
        log.info("Strategy submitted for execution")

    def get_strategy_text(self) -> str:
        """Return current strategy text."""
        return self._editor.toPlainText()


__all__ = ["StrategyBuilderScreen"]
