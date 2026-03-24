"""
TradeOS India — Backtest screen.

Allows users to configure and run backtests on their strategies,
view equity curves, trade logs, and performance metrics.
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QPlainTextEdit, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.event_bus import EventBus
from core.state_store import AppState
from utils.logger import get_logger

log = get_logger("ui.screens.backtest")


class BacktestScreen(QWidget):
    """Backtest configuration and results screen."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("BacktestScreen")

        self._state = AppState.get_instance()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar ──────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet(
            "background-color: #252526; border-bottom: 1px solid #3e3e42;"
        )
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(12, 0, 12, 0)
        tb.setSpacing(8)

        # Symbol
        self._symbol_combo = QComboBox()
        self._symbol_combo.addItems([
            "NSE:NIFTY50-INDEX", "NSE:BANKNIFTY-INDEX",
            "NSE:RELIANCE-EQ", "NSE:TCS-EQ", "NSE:HDFCBANK-EQ",
        ])
        self._symbol_combo.setFixedWidth(200)
        tb.addWidget(QLabel("Symbol:"))
        tb.addWidget(self._symbol_combo)

        # Timeframe
        self._tf_combo = QComboBox()
        self._tf_combo.addItems(["1m", "5m", "15m", "1h", "1D"])
        self._tf_combo.setCurrentText("5m")
        self._tf_combo.setFixedWidth(80)
        tb.addWidget(QLabel("TF:"))
        tb.addWidget(self._tf_combo)

        tb.addStretch()

        # Run button
        self._run_btn = QPushButton("Run Backtest")
        self._run_btn.setFixedWidth(120)
        self._run_btn.setStyleSheet(
            "QPushButton { background-color: #c586c0; color: #fff; }"
            " QPushButton:hover { background-color: #d59dd5; }"
        )
        self._run_btn.clicked.connect(self._on_run)
        tb.addWidget(self._run_btn)

        layout.addWidget(toolbar)

        # ── Splitter: metrics/chart | trade log ──────────────
        splitter = QSplitter(Qt.Vertical)

        # Top: metrics grid + placeholder chart
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(16, 12, 16, 8)
        top_layout.setSpacing(10)

        # Metrics cards
        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(10)

        self._metric_cards = {}
        metrics = [
            ("total_return", "Total Return", "--"),
            ("win_rate", "Win Rate", "--"),
            ("sharpe", "Sharpe Ratio", "--"),
            ("max_dd", "Max Drawdown", "--"),
            ("total_trades", "Total Trades", "--"),
            ("profit_factor", "Profit Factor", "--"),
        ]

        for i, (key, title, default) in enumerate(metrics):
            card = self._make_metric_card(title, default)
            metrics_grid.addWidget(card, i // 3, i % 3)
            self._metric_cards[key] = card

        top_layout.addLayout(metrics_grid)

        # Chart placeholder
        chart_area = QPlainTextEdit()
        chart_area.setReadOnly(True)
        chart_area.setStyleSheet(
            "QPlainTextEdit { background-color: #1a1d23; color: #858585;"
            " font-family: 'Consolas', monospace; font-size: 12px;"
            " border: 1px solid #3e3e42; border-radius: 4px; padding: 12px; }"
        )
        chart_area.setPlainText(
            "\n    Equity Curve\n"
            "    ─────────────────────────────────────\n\n"
            "    Configure backtest parameters above\n"
            "    and click 'Run Backtest' to see results.\n\n"
            "    The Research Agent will analyze the results\n"
            "    and provide insights via Monte Carlo simulation.\n"
        )
        top_layout.addWidget(chart_area, 1)
        splitter.addWidget(top)

        # Bottom: trade log table
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(16, 8, 16, 12)

        header = QLabel("TRADE LOG")
        header.setStyleSheet(
            "color: #858585; font-size: 11px; font-weight: 600;"
            " letter-spacing: 0.5px; padding-bottom: 4px;"
        )
        bottom_layout.addWidget(header)

        self._trade_table = QTableWidget(0, 7)
        self._trade_table.setHorizontalHeaderLabels([
            "Time", "Symbol", "Side", "Qty", "Entry", "Exit", "P&L",
        ])
        self._trade_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._trade_table.setAlternatingRowColors(True)
        self._trade_table.setStyleSheet(
            "QTableWidget { background-color: #1e1e1e; alternate-background-color: #252526;"
            " border: 1px solid #3e3e42; border-radius: 4px; }"
        )
        self._trade_table.verticalHeader().setVisible(False)
        self._trade_table.setEditTriggers(QTableWidget.NoEditTriggers)
        bottom_layout.addWidget(self._trade_table)

        splitter.addWidget(bottom)
        splitter.setSizes([500, 250])

        layout.addWidget(splitter, 1)

    def _make_metric_card(self, title: str, value: str) -> QFrame:
        """Create a dark metric card."""
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #252526; border: 1px solid #3e3e42;"
            " border-radius: 6px; padding: 12px; }"
        )
        cl = QVBoxLayout(card)
        cl.setSpacing(4)

        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet(
            "color: #858585; font-size: 10px; font-weight: 600;"
            " letter-spacing: 0.5px; background: transparent;"
        )
        val_lbl = QLabel(value)
        val_lbl.setObjectName("metric_value")
        val_lbl.setStyleSheet(
            "color: #e0e0e0; font-size: 18px; font-weight: 600; background: transparent;"
        )

        cl.addWidget(title_lbl)
        cl.addWidget(val_lbl)
        return card

    def _on_run(self) -> None:
        """Run backtest (placeholder — would submit to Research Agent)."""
        symbol = self._symbol_combo.currentText()
        tf = self._tf_combo.currentText()
        log.info(f"Backtest requested: {symbol} @ {tf}")

        # Update metrics with placeholder data
        placeholders = {
            "total_return": "+12.4%",
            "win_rate": "58.3%",
            "sharpe": "1.42",
            "max_dd": "-4.8%",
            "total_trades": "127",
            "profit_factor": "1.68",
        }
        for key, val in placeholders.items():
            card = self._metric_cards[key]
            val_label = card.findChild(QLabel, "metric_value")
            if val_label:
                color = "#4ec9b0" if not val.startswith("-") else "#f44747"
                if key in ("win_rate", "sharpe", "profit_factor", "total_trades"):
                    color = "#e0e0e0"
                val_label.setText(val)
                val_label.setStyleSheet(
                    f"color: {color}; font-size: 18px; font-weight: 600; background: transparent;"
                )


__all__ = ["BacktestScreen"]
