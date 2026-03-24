"""
TradeOS India — Risk Monitor screen.

Displays real-time risk metrics: daily P&L, drawdown gauge,
position exposure, circuit breaker status, and risk event log.
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QSplitter, QVBoxLayout, QWidget,
)

from core.event_bus import EventBus
from core.state_store import AppState
from utils.logger import get_logger

log = get_logger("ui.screens.risk_monitor")


class RiskGauge(QWidget):
    """Simple arc gauge showing daily loss as percentage of limit."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(180, 180)
        self._value = 0.0  # 0.0 to 1.0
        self._label = "0%"

    def set_value(self, pct: float, label: str = "") -> None:
        self._value = max(0.0, min(1.0, pct))
        self._label = label or f"{int(pct * 100)}%"
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        size = min(w, h) - 20
        x = (w - size) // 2
        y = (h - size) // 2

        # Background arc
        pen = QPen(QColor("#3e3e42"), 12)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(x, y, size, size, 225 * 16, -270 * 16)

        # Value arc
        if self._value <= 0.5:
            color = QColor("#4ec9b0")  # green
        elif self._value <= 0.75:
            color = QColor("#dcdcaa")  # yellow
        else:
            color = QColor("#f44747")  # red

        pen = QPen(color, 12)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        span = int(-270 * self._value * 16)
        painter.drawArc(x, y, size, size, 225 * 16, span)

        # Center text
        painter.setPen(QColor("#e0e0e0"))
        font = painter.font()
        font.setPixelSize(28)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(x, y, size, size, Qt.AlignCenter, self._label)

        painter.end()


class RiskMetricCard(QFrame):
    """Single risk metric display card."""

    def __init__(self, title: str, value: str, color: str = "#e0e0e0", parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background-color: #252526; border: 1px solid #3e3e42;"
            " border-radius: 6px; padding: 12px; }"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self._title = QLabel(title.upper())
        self._title.setStyleSheet(
            "color: #858585; font-size: 10px; font-weight: 600;"
            " letter-spacing: 0.5px; background: transparent;"
        )

        self._value = QLabel(value)
        self._value.setObjectName("risk_value")
        self._value.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: 600;"
            " background: transparent;"
        )

        layout.addWidget(self._title)
        layout.addWidget(self._value)

    def set_value(self, value: str, color: str = "#e0e0e0") -> None:
        self._value.setText(value)
        self._value.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: 600;"
            " background: transparent;"
        )


class RiskMonitorScreen(QWidget):
    """Risk monitor — gauges, metrics, circuit breaker log."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("RiskMonitorScreen")

        self._state = AppState.get_instance()
        self._event_bus = EventBus.get_instance()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Vertical)

        # ── Top: gauge + metric cards ────────────────────────
        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(16, 12, 16, 8)
        top_layout.setSpacing(16)

        # Left: gauge
        gauge_container = QVBoxLayout()
        gauge_title = QLabel("DAILY LOSS USAGE")
        gauge_title.setStyleSheet(
            "color: #858585; font-size: 11px; font-weight: 600;"
            " letter-spacing: 0.5px;"
        )
        gauge_title.setAlignment(Qt.AlignCenter)
        gauge_container.addWidget(gauge_title)

        self._gauge = RiskGauge()
        self._gauge.set_value(0.32, "32%")
        gauge_container.addWidget(self._gauge)

        gauge_sub = QLabel("of daily limit used")
        gauge_sub.setStyleSheet("color: #858585; font-size: 11px;")
        gauge_sub.setAlignment(Qt.AlignCenter)
        gauge_container.addWidget(gauge_sub)

        top_layout.addLayout(gauge_container)

        # Right: metric cards grid
        cards = QGridLayout()
        cards.setSpacing(10)

        self._cards = {}
        metrics = [
            ("daily_pnl", "Daily P&L", "\u20b90.00", "#4ec9b0"),
            ("daily_limit", "Daily Limit", "\u20b95,000", "#e0e0e0"),
            ("open_positions", "Open Positions", "0 / 10", "#e0e0e0"),
            ("exposure", "Total Exposure", "\u20b90", "#e0e0e0"),
            ("max_drawdown", "Max Drawdown", "0.0%", "#e0e0e0"),
            ("circuit_breaker", "Circuit Breaker", "OFF", "#4ec9b0"),
        ]

        for i, (key, title, value, color) in enumerate(metrics):
            card = RiskMetricCard(title, value, color)
            cards.addWidget(card, i // 3, i % 3)
            self._cards[key] = card

        top_layout.addLayout(cards, 1)
        splitter.addWidget(top)

        # ── Bottom: risk event log ───────────────────────────
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(16, 8, 16, 12)

        log_header = QLabel("RISK EVENT LOG")
        log_header.setStyleSheet(
            "color: #858585; font-size: 11px; font-weight: 600;"
            " letter-spacing: 0.5px; padding-bottom: 4px;"
        )
        bottom_layout.addWidget(log_header)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(300)
        self._log_view.setStyleSheet(
            "QPlainTextEdit { background-color: #1a1d23; color: #d4d4d4;"
            " font-family: 'Cascadia Code', 'Consolas', monospace;"
            " font-size: 12px; border: 1px solid #3e3e42; border-radius: 4px;"
            " padding: 8px; }"
        )
        self._log_view.setPlainText(
            "[09:15:00] [RISK] System initialized\n"
            "[09:15:01] [RISK] Daily loss limit: \u20b95,000\n"
            "[09:15:01] [RISK] Max positions: 10\n"
            "[09:15:01] [RISK] Circuit breaker: OFF\n"
            "[09:15:02] [RISK] Monitoring active\n"
        )
        bottom_layout.addWidget(self._log_view)

        splitter.addWidget(bottom)
        splitter.setSizes([350, 300])

        layout.addWidget(splitter, 1)

        # Connect events
        self._event_bus.risk_event.connect(self._on_risk_event)

    def _on_risk_event(self, event_type: str, data: dict) -> None:
        from utils.date_utils import ist_time_str
        time_str = ist_time_str()
        self._log_view.appendPlainText(
            f"[{time_str}] [RISK] {event_type}: {data}"
        )

    def update_daily_pnl(self, pnl: float, limit: float) -> None:
        """Update gauge and P&L card."""
        pct = abs(pnl) / limit if limit > 0 else 0
        self._gauge.set_value(pct, f"{int(pct * 100)}%")

        color = "#4ec9b0" if pnl >= 0 else "#f44747"
        self._cards["daily_pnl"].set_value(f"\u20b9{pnl:,.2f}", color)

    def set_circuit_breaker(self, active: bool) -> None:
        if active:
            self._cards["circuit_breaker"].set_value("ACTIVE", "#f44747")
        else:
            self._cards["circuit_breaker"].set_value("OFF", "#4ec9b0")


__all__ = ["RiskMonitorScreen"]
