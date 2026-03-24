"""
TradeOS India — Main window: VS Code-inspired shell.

Fully frameless. Custom title bar with menus. Activity bar, sidebar,
tab bar, editor area, bottom panel, status bar, and settings panel.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QPoint, QPropertyAnimation, QSize, Qt, QTimer, QUrl, Signal, Slot,
)
from PySide6.QtGui import (
    QAction, QColor, QFont, QIcon, QPainter, QPen, QPixmap,
)
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMenu,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QSpinBox, QSplitter, QStackedWidget, QTabWidget,
    QVBoxLayout, QWidget,
)

from core.event_bus import EventBus
from core.state_store import AppState
from ui.theme import (
    COLORS_DARK, COLORS_LIGHT, DARK_QSS, LIGHT_QSS, apply_theme,
    get_color,
)
from utils.date_utils import ist_time_str
from utils.logger import get_logger

log = get_logger("ui.main_window")

# ═════════════════════════════════════════════════════════════════
# Icon helpers (QPainter-drawn, no image files needed)
# ═════════════════════════════════════════════════════════════════

def _make_icon(draw_func, size: int = 24, color: str = "#858585") -> QIcon:
    """Create a QIcon by painting onto a QPixmap.

    Args:
        draw_func: Callable(QPainter, int, QColor) that draws the icon.
        size: Icon size in pixels.
        color: Hex color string.

    Returns:
        QIcon.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    draw_func(painter, size, QColor(color))
    painter.end()
    return QIcon(pixmap)


def _draw_dashboard(p: QPainter, s: int, c: QColor) -> None:
    pen = QPen(c, 1.5)
    p.setPen(pen)
    m = 5
    mid = s // 2
    p.drawRect(m, m, mid - m - 1, mid - m - 1)
    p.drawRect(mid + 1, m, s - mid - m - 1, mid - m - 1)
    p.drawRect(m, mid + 1, mid - m - 1, s - mid - m - 1)
    p.drawRect(mid + 1, mid + 1, s - mid - m - 1, s - mid - m - 1)


def _draw_strategy(p: QPainter, s: int, c: QColor) -> None:
    pen = QPen(c, 1.5)
    p.setPen(pen)
    m = 6
    p.drawLine(m, s - m, m + 3, m + 4)
    p.drawLine(m + 3, m + 4, m + 6, m + 8)
    p.drawLine(m + 6, m + 8, m + 9, m + 2)
    p.drawLine(m + 9, m + 2, s - m, m + 6)


def _draw_backtest(p: QPainter, s: int, c: QColor) -> None:
    pen = QPen(c, 1.5)
    p.setPen(pen)
    m = 6
    # Chart axes
    p.drawLine(m, m, m, s - m)
    p.drawLine(m, s - m, s - m, s - m)
    # Bars
    for i, h in enumerate([6, 10, 8, 12, 9]):
        x = m + 2 + i * 3
        p.drawLine(x, s - m, x, s - m - h)


def _draw_agents(p: QPainter, s: int, c: QColor) -> None:
    pen = QPen(c, 1.5)
    p.setPen(pen)
    mid = s // 2
    p.drawEllipse(mid - 4, 4, 8, 8)
    p.drawLine(mid, 12, mid, 16)
    p.drawLine(mid - 5, 16, mid + 5, 16)
    p.drawLine(mid - 5, 16, mid - 5, s - 5)
    p.drawLine(mid + 5, 16, mid + 5, s - 5)


def _draw_risk(p: QPainter, s: int, c: QColor) -> None:
    pen = QPen(c, 1.5)
    p.setPen(pen)
    mid = s // 2
    p.drawLine(mid, 5, mid - 6, s - 6)
    p.drawLine(mid, 5, mid + 6, s - 6)
    p.drawLine(mid - 6, s - 6, mid + 6, s - 6)
    p.drawLine(mid, 10, mid, s - 10)
    p.drawPoint(mid, s - 8)


def _draw_market(p: QPainter, s: int, c: QColor) -> None:
    pen = QPen(c, 1.5)
    p.setPen(pen)
    m = 6
    points = [(m, s - m - 2), (m + 3, m + 6), (m + 7, m + 10),
              (m + 10, m + 3), (s - m, m + 7)]
    for i in range(len(points) - 1):
        p.drawLine(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])


def _draw_settings(p: QPainter, s: int, c: QColor) -> None:
    pen = QPen(c, 1.5)
    p.setPen(pen)
    mid = s // 2
    p.drawEllipse(mid - 3, mid - 3, 6, 6)
    for angle in range(0, 360, 45):
        import math
        rad = math.radians(angle)
        x1 = mid + int(5 * math.cos(rad))
        y1 = mid + int(5 * math.sin(rad))
        x2 = mid + int(8 * math.cos(rad))
        y2 = mid + int(8 * math.sin(rad))
        p.drawLine(x1, y1, x2, y2)


# ═════════════════════════════════════════════════════════════════
# Title Bar
# ═════════════════════════════════════════════════════════════════

class TitleBar(QWidget):
    """Custom frameless title bar with menus and window controls."""

    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(32)
        self._parent = parent
        self._drag_pos: Optional[QPoint] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(0)

        # App icon + title
        icon_label = QLabel("  TradeOS India")
        icon_label.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #e0e0e0;"
            " background: transparent; padding-left: 4px;"
        )
        layout.addWidget(icon_label)

        layout.addSpacing(20)

        # Menu buttons
        for name, builder in [
            ("File", self._build_file_menu),
            ("Edit", self._build_edit_menu),
            ("View", self._build_view_menu),
            ("Terminal", self._build_terminal_menu),
            ("Help", self._build_help_menu),
        ]:
            btn = QPushButton(name)
            btn.setProperty("class", "menu-btn")
            btn.setStyleSheet(
                "background: transparent; border: none;"
                " color: #858585; padding: 0 10px;"
                " min-width: 0; max-width: 9999px; font-size: 12px;"
            )
            menu = builder()
            btn.setMenu(menu)
            layout.addWidget(btn)

        layout.addStretch()

        # Window controls
        for text, obj_name, slot in [
            ("\u2500", "btn_min", self._parent.showMinimized),
            ("\u25a1", "btn_max", self._toggle_maximize),
            ("\u2715", "btn_close", self._parent.close),
        ]:
            btn = QPushButton(text)
            btn.setObjectName(obj_name)
            btn.setFixedSize(46, 32)
            btn.setStyleSheet(
                "background: transparent; border: none;"
                " color: #cccccc; font-size: 10px;"
            )
            btn.clicked.connect(slot)
            layout.addWidget(btn)

    def _toggle_maximize(self) -> None:
        if self._parent.isMaximized():
            self._parent.showNormal()
        else:
            self._parent.showMaximized()

    # ─── Menus ────────────────────────────────────────────────

    def _build_file_menu(self) -> QMenu:
        m = QMenu(self)
        m.addAction("New Strategy")
        m.addAction("Open Strategy")
        m.addAction("Save Strategy")
        m.addSeparator()
        m.addAction("Import Pine Script")
        m.addAction("Export Strategy")
        m.addSeparator()
        settings_action = m.addAction("Settings")
        settings_action.triggered.connect(self._parent.toggle_settings)
        m.addSeparator()
        exit_action = m.addAction("Exit")
        exit_action.triggered.connect(self._parent.close)
        return m

    def _build_edit_menu(self) -> QMenu:
        m = QMenu(self)
        m.addAction("Undo")
        m.addAction("Redo")
        m.addSeparator()
        m.addAction("Copy")
        m.addAction("Paste")
        m.addSeparator()
        m.addAction("Find in Code")
        m.addSeparator()
        m.addAction("Preferences")
        return m

    def _build_view_menu(self) -> QMenu:
        m = QMenu(self)
        sidebar_action = m.addAction("Toggle Sidebar")
        sidebar_action.triggered.connect(self._parent.toggle_sidebar)
        panel_action = m.addAction("Toggle Panel")
        panel_action.triggered.connect(self._parent.toggle_bottom_panel)
        m.addAction("Toggle Status Bar")
        m.addSeparator()
        m.addAction("Zoom In  (Ctrl++)")
        m.addAction("Zoom Out (Ctrl+-)")
        m.addAction("Reset Zoom")
        m.addSeparator()
        dark_action = m.addAction("Dark Theme")
        dark_action.triggered.connect(lambda: self._parent.set_theme("dark"))
        light_action = m.addAction("Light Theme")
        light_action.triggered.connect(lambda: self._parent.set_theme("light"))
        return m

    def _build_terminal_menu(self) -> QMenu:
        m = QMenu(self)
        m.addAction("New Terminal")
        m.addAction("Clear Terminal")
        m.addSeparator()
        m.addAction("Run Strategy")
        m.addAction("Stop Strategy")
        m.addSeparator()
        m.addAction("Run Backtest")
        return m

    def _build_help_menu(self) -> QMenu:
        m = QMenu(self)
        m.addAction("Documentation")
        m.addAction("Keyboard Shortcuts")
        m.addSeparator()
        m.addAction("Fyers API Guide")
        m.addAction("Claude API Guide")
        m.addSeparator()
        m.addAction("About TradeOS India")
        m.addAction("Check for Updates")
        return m

    # ─── Drag to move ─────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self._parent.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self._parent.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event) -> None:
        self._toggle_maximize()


# ═════════════════════════════════════════════════════════════════
# Activity Bar
# ═════════════════════════════════════════════════════════════════

class ActivityBar(QWidget):
    """Left icon bar — 6 screen icons + settings at bottom."""

    icon_clicked = Signal(int)

    # Screen definitions: (name, draw_func)
    SCREENS = [
        ("Dashboard", _draw_dashboard),
        ("Strategy", _draw_strategy),
        ("Backtest", _draw_backtest),
        ("Agents", _draw_agents),
        ("Risk", _draw_risk),
        ("Market Feed", _draw_market),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ActivityBar")
        self.setFixedWidth(48)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        self._buttons: list[QPushButton] = []
        self._active_index = 0

        for i, (name, draw_func) in enumerate(self.SCREENS):
            btn = QPushButton()
            btn.setIcon(_make_icon(draw_func, 24, "#858585"))
            btn.setIconSize(QSize(24, 24))
            btn.setFixedSize(48, 48)
            btn.setToolTip(name)
            btn.setCheckable(True)
            btn.setStyleSheet(
                "background: transparent; border: none;"
                " border-left: 2px solid transparent;"
            )
            btn.clicked.connect(lambda checked, idx=i: self._on_click(idx))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()

        # Settings button at bottom
        settings_btn = QPushButton()
        settings_btn.setIcon(_make_icon(_draw_settings, 24, "#858585"))
        settings_btn.setIconSize(QSize(24, 24))
        settings_btn.setFixedSize(48, 48)
        settings_btn.setToolTip("Settings")
        settings_btn.setStyleSheet(
            "background: transparent; border: none;"
            " border-left: 2px solid transparent;"
        )
        settings_btn.clicked.connect(lambda: self.icon_clicked.emit(-1))
        layout.addWidget(settings_btn)
        self._settings_btn = settings_btn

        self._update_active(0)

    def _on_click(self, index: int) -> None:
        self._update_active(index)
        self.icon_clicked.emit(index)

    def _update_active(self, index: int) -> None:
        self._active_index = index
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
            if i == index:
                btn.setStyleSheet(
                    "background: #37373d; border: none;"
                    " border-left: 2px solid #007acc;"
                )
                btn.setIcon(_make_icon(self.SCREENS[i][1], 24, "#e0e0e0"))
            else:
                btn.setStyleSheet(
                    "background: transparent; border: none;"
                    " border-left: 2px solid transparent;"
                )
                btn.setIcon(_make_icon(self.SCREENS[i][1], 24, "#858585"))
        # Reset settings button
        self._settings_btn.setStyleSheet(
            "background: transparent; border: none;"
            " border-left: 2px solid transparent;"
        )

    @property
    def active_index(self) -> int:
        return self._active_index


# ═════════════════════════════════════════════════════════════════
# Sidebar
# ═════════════════════════════════════════════════════════════════

class Sidebar(QWidget):
    """Collapsible sidebar with stacked panels per activity bar icon."""

    PANEL_NAMES = [
        "DASHBOARD", "STRATEGY", "BACKTEST", "AGENTS", "RISK", "MARKET FEED",
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setMinimumWidth(0)
        self.setMaximumWidth(280)
        self._expanded_width = 280

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QLabel("DASHBOARD")
        self._header.setObjectName("SidebarHeader")
        self._header.setStyleSheet(
            "color: #858585; font-size: 11px; font-weight: 600;"
            " padding: 10px 14px 6px; background: transparent;"
            " letter-spacing: 0.5px;"
        )
        layout.addWidget(self._header)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        # Create placeholder panels
        for name in self.PANEL_NAMES:
            panel = QWidget()
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(10, 6, 10, 6)
            info = QLabel(f"{name} panel content\nwill be populated\nby screen modules")
            info.setStyleSheet("color: #858585; font-size: 11px;")
            info.setWordWrap(True)
            panel_layout.addWidget(info)
            panel_layout.addStretch()
            self._stack.addWidget(panel)

    def set_panel(self, index: int) -> None:
        """Switch sidebar to show the panel for the given index.

        Args:
            index: Activity bar icon index.
        """
        if 0 <= index < len(self.PANEL_NAMES):
            self._stack.setCurrentIndex(index)
            self._header.setText(self.PANEL_NAMES[index])

    def replace_panel(self, index: int, widget: QWidget) -> None:
        """Replace a sidebar panel with a custom widget.

        Args:
            index: Panel index to replace.
            widget: Replacement QWidget.
        """
        if 0 <= index < self._stack.count():
            old = self._stack.widget(index)
            self._stack.removeWidget(old)
            old.deleteLater()
            self._stack.insertWidget(index, widget)


# ═════════════════════════════════════════════════════════════════
# Settings Bridge (Python <-> JS via QWebChannel)
# ═════════════════════════════════════════════════════════════════

from PySide6.QtCore import QObject as _QObject


class SettingsBridge(_QObject):
    """QWebChannel bridge for the settings wizard HTML page."""

    def __init__(self, parent: Optional[_QObject] = None) -> None:
        super().__init__(parent)
        self._state = AppState.get_instance()
        self._event_bus = EventBus.get_instance()

    @Slot()
    def requestState(self) -> None:
        """Called from JS to get current state. Pushes state into the page."""
        state_dict = {
            "mode": self._state.mode,
            "active_markets": self._state.active_markets,
            "daily_loss_limit": self._state.daily_loss_limit,
            "risk_per_trade_pct": self._state.risk_per_trade_pct,
            "max_positions": self._state.max_positions,
            "max_sl_pct": self._state.max_sl_pct,
            "circuit_breaker_pct": self._state.circuit_breaker_pct,
            "llm_primary": self._state.llm_primary,
            "llm_overnight": self._state.llm_overnight,
            "agents_enabled": self._state.agents_enabled,
            "theme": self._state.theme,
            "sidebar_visible": self._state.sidebar_visible,
            "bottom_panel_visible": self._state.bottom_panel_visible,
            "tokens_used_today": self._state.tokens_used_today,
            "cost_inr_today": self._state.cost_inr_today,
        }
        state_json = json.dumps(state_dict)
        # Inject state into the page
        if hasattr(self, "_view") and self._view:
            self._view.page().runJavaScript(f"loadState('{state_json}')")

    @Slot(str)
    def saveSettings(self, settings_json: str) -> None:
        """Called from JS when user clicks Save."""
        try:
            s = json.loads(settings_json)
            self._state.mode = s.get("mode", "paper")
            self._state.active_markets = s.get("active_markets", ["NSE", "NFO"])
            self._state.daily_loss_limit = float(s.get("daily_loss_limit", 5000))
            self._state.risk_per_trade_pct = float(s.get("risk_per_trade_pct", 1.0))
            self._state.max_positions = int(s.get("max_positions", 5))
            self._state.max_sl_pct = float(s.get("max_sl_pct", 2.0))
            self._state.circuit_breaker_pct = float(s.get("circuit_breaker_pct", 80))
            self._state.llm_primary = s.get("llm_primary", "claude")
            self._state.llm_overnight = s.get("llm_overnight", "groq")
            self._state.agents_enabled = s.get("agents_enabled", {
                "strategy": True, "risk": True,
                "execution": True, "research": True,
            })

            # Theme change
            new_theme = s.get("theme", "dark")
            if new_theme != self._state.theme:
                self._state.theme = new_theme
                apply_theme(new_theme)
                self._event_bus.theme_changed.emit(new_theme)
            else:
                self._state.theme = new_theme

            self._state.sidebar_visible = s.get("sidebar_visible", True)
            self._state.bottom_panel_visible = s.get("bottom_panel_visible", True)

            self._state.save()
            log.info("Settings saved from wizard panel")
        except Exception as e:
            log.error(f"Failed to save settings: {e}")

    @Slot()
    def resetTokens(self) -> None:
        """Called from JS to reset token counter."""
        self._state.tokens_used_today = 0
        self._state.cost_inr_today = 0.0
        self._state.save()
        log.info("Token counter reset from settings")

    def set_view(self, view: QWebEngineView) -> None:
        """Store reference to the web view for JS calls."""
        self._view = view


# ═════════════════════════════════════════════════════════════════
# Settings Panel (QWebEngineView-based wizard)
# ═════════════════════════════════════════════════════════════════

class SettingsPanel(QWidget):
    """4-step wizard-style settings panel using QWebEngineView."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Bridge
        self._bridge = SettingsBridge(self)

        # Web view
        self._view = QWebEngineView()
        self._bridge.set_view(self._view)

        # Channel
        self._channel = QWebChannel()
        self._channel.registerObject("settings_bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        # Load settings HTML
        html_path = Path(__file__).parent.parent / "assets" / "wizard" / "settings.html"
        self._view.setUrl(QUrl.fromLocalFile(str(html_path.resolve())))

        # Push state once page loads
        self._view.loadFinished.connect(self._on_load_finished)

        layout.addWidget(self._view)

    def _on_load_finished(self, ok: bool) -> None:
        """After HTML loads, inject qwebchannel.js and push state."""
        if ok:
            # Inject QWebChannel JS API then init bridge
            qwc_js = """
            (function() {
                var script = document.createElement('script');
                script.src = 'qrc:///qtwebchannel/qwebchannel.js';
                script.onload = function() { initBridge(); };
                document.head.appendChild(script);
            })();
            """
            self._view.page().runJavaScript(qwc_js)
            log.info("Settings wizard HTML loaded")

    def refresh_state(self) -> None:
        """Refresh the settings page with current state."""
        self._bridge.requestState()


# ═════════════════════════════════════════════════════════════════
# Status Bar
# ═════════════════════════════════════════════════════════════════

class StatusBar(QWidget):
    """Bottom status bar with mode, broker, clock, and market status."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusBar")
        self.setFixedHeight(22)
        self.setStyleSheet("background-color: #007acc;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._state = AppState.get_instance()

        # Left items
        self._mode_label = self._make_label(
            f"  {self._state.mode.upper()}"
        )
        layout.addWidget(self._mode_label)
        layout.addWidget(self._make_separator())

        self._broker_label = self._make_label(
            f"Fyers: {'Connected' if self._state.broker_connected else 'Disconnected'}"
        )
        layout.addWidget(self._broker_label)
        layout.addWidget(self._make_separator())

        self._errors_label = self._make_label("\u2715 0 errors")
        layout.addWidget(self._errors_label)
        layout.addWidget(self._make_separator())

        self._warnings_label = self._make_label("\u26a0 0 warnings")
        layout.addWidget(self._warnings_label)

        layout.addStretch()

        # Right items
        self._llm_label = self._make_label(
            self._state.llm_primary.capitalize()
        )
        layout.addWidget(self._llm_label)
        layout.addWidget(self._make_separator())

        self._clock_label = self._make_label(ist_time_str() + " IST")
        layout.addWidget(self._clock_label)
        layout.addWidget(self._make_separator())

        self._market_label = self._make_label("NSE Open")
        layout.addWidget(self._market_label)
        layout.addWidget(self._make_separator())

        self._python_label = self._make_label(
            f"Python {sys.version_info.major}.{sys.version_info.minor}  "
        )
        layout.addWidget(self._python_label)

        # Clock timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start(1000)

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #ffffff; font-size: 11px; padding: 0 8px;"
            " background: transparent;"
        )
        return lbl

    def _make_separator(self) -> QFrame:
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setFixedHeight(14)
        sep.setStyleSheet("background-color: rgba(255,255,255,0.3);")
        return sep

    def _update_clock(self) -> None:
        from utils.date_utils import is_market_open
        self._clock_label.setText(ist_time_str() + " IST")
        self._market_label.setText(
            "NSE Open" if is_market_open() else "NSE Closed"
        )

    def set_status(self, status: str = "ok") -> None:
        """Set the status bar color.

        Args:
            status: 'ok', 'warning', or 'error'.
        """
        colors = {
            "ok": "#007acc",
            "warning": "#d7ba7d",
            "error": "#f44747",
        }
        self.setStyleSheet(
            f"background-color: {colors.get(status, '#007acc')};"
        )


# ═════════════════════════════════════════════════════════════════
# Main Window
# ═════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    """VS Code-inspired main window shell.

    Frameless. Custom title bar, activity bar, sidebar, tab bar,
    editor area, bottom panel, and status bar.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMinimumSize(1200, 750)
        self.resize(1440, 900)
        self.setWindowTitle("TradeOS India")

        self._state = AppState.get_instance()
        self._event_bus = EventBus.get_instance()
        self._settings_visible = False

        self._build_ui()
        self._connect_signals()

        apply_theme(self._state.theme)
        log.info("MainWindow initialized")

    def _build_ui(self) -> None:
        """Assemble the full VS Code layout."""
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Title bar
        self._title_bar = TitleBar(self)
        root.addWidget(self._title_bar)

        # Body: activity bar + sidebar + editor + settings
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Activity bar
        self._activity_bar = ActivityBar()
        self._activity_bar.icon_clicked.connect(self._on_activity_icon)
        body.addWidget(self._activity_bar)

        # Sidebar
        self._sidebar = Sidebar()
        body.addWidget(self._sidebar)

        # Main vertical: tabs + editor + bottom panel
        main_v = QVBoxLayout()
        main_v.setContentsMargins(0, 0, 0, 0)
        main_v.setSpacing(0)

        # Tab bar
        self._tab_bar = QWidget()
        self._tab_bar.setObjectName("TabBar")
        self._tab_bar.setFixedHeight(35)
        tab_layout = QHBoxLayout(self._tab_bar)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        self._tab_buttons: list[QPushButton] = []
        tab_names = [
            "Live Monitor", "Strategy Builder", "Backtest",
            "Agent Log", "Terminal",
        ]
        for i, name in enumerate(tab_names):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setStyleSheet(
                "background: transparent; border: none;"
                " border-top: 2px solid transparent;"
                " color: #858585; padding: 0 16px;"
                " font-size: 12px;"
            )
            btn.clicked.connect(lambda checked, idx=i: self._on_tab_click(idx))
            tab_layout.addWidget(btn)
            self._tab_buttons.append(btn)

        tab_layout.addStretch()
        main_v.addWidget(self._tab_bar)

        # Editor area (stacked) + settings panel
        self._editor_stack = QStackedWidget()
        self._editor_stack.setObjectName("EditorArea")

        # Create placeholder editor pages
        self._editor_pages: list[QWidget] = []
        for name in tab_names:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            placeholder = QPlainTextEdit()
            placeholder.setReadOnly(True)
            placeholder.setPlainText(
                f"  {name}\n\n"
                f"  This screen will be populated by the screen module.\n"
                f"  Phase 9 will build the actual UI for each tab."
            )
            placeholder.setStyleSheet(
                "background-color: #1e1e1e; color: #858585;"
                " font-family: 'Cascadia Code', 'Consolas', monospace;"
                " font-size: 13px; border: none;"
            )
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.addWidget(placeholder)
            self._editor_stack.addWidget(page)
            self._editor_pages.append(page)

        # Settings panel (hidden by default, replaces editor when shown)
        self._settings_panel = SettingsPanel()
        self._editor_stack.addWidget(self._settings_panel)

        # Splitter: editor / bottom panel
        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.addWidget(self._editor_stack)

        # Bottom panel
        self._bottom_panel = QTabWidget()
        self._bottom_panel.setObjectName("BottomPanel")
        self._bottom_panel.setMinimumHeight(0)

        # Bottom panel tabs
        for name, style in [
            ("Terminal", "background:#0e0e0e; color:#4ec9b0;"),
            ("Problems", ""),
            ("Output", ""),
            ("Agent Feed", ""),
        ]:
            text_edit = QPlainTextEdit()
            text_edit.setReadOnly(True)
            if style:
                text_edit.setStyleSheet(style + " border: none; font-family: 'Consolas', monospace;")
            self._bottom_panel.addTab(text_edit, name)

        self._splitter.addWidget(self._bottom_panel)
        self._splitter.setSizes([600, 200])

        main_v.addWidget(self._splitter)
        body.addLayout(main_v, 1)

        root.addLayout(body, 1)

        # Status bar
        self._status_bar = StatusBar()
        root.addWidget(self._status_bar)

        # Set initial tab
        self._on_tab_click(0)

        # Apply sidebar visibility
        if not self._state.sidebar_visible:
            self._sidebar.setMaximumWidth(0)

        if not self._state.bottom_panel_visible:
            self._bottom_panel.setMaximumHeight(0)

    def _connect_signals(self) -> None:
        """Connect event bus signals to UI updates."""
        self._event_bus.screen_changed.connect(self._on_screen_changed)
        self._event_bus.notification.connect(self._on_notification)

    # ═════════════════════════════════════════════════════════════
    # Tab management
    # ═════════════════════════════════════════════════════════════

    def _on_tab_click(self, index: int) -> None:
        """Switch active editor tab."""
        self._settings_visible = False
        for i, btn in enumerate(self._tab_buttons):
            if i == index:
                btn.setChecked(True)
                btn.setStyleSheet(
                    "background: #1e1e1e; border: none;"
                    " border-top: 2px solid #007acc;"
                    " color: #e0e0e0; padding: 0 16px;"
                    " font-size: 12px;"
                )
            else:
                btn.setChecked(False)
                btn.setStyleSheet(
                    "background: transparent; border: none;"
                    " border-top: 2px solid transparent;"
                    " color: #858585; padding: 0 16px;"
                    " font-size: 12px;"
                )
        self._editor_stack.setCurrentIndex(index)

    def replace_editor_page(self, index: int, widget: QWidget) -> None:
        """Replace an editor tab's content with a custom widget.

        Args:
            index: Tab index (0-4).
            widget: Replacement widget.
        """
        if 0 <= index < len(self._editor_pages):
            old = self._editor_pages[index]
            self._editor_stack.removeWidget(old)
            old.deleteLater()
            self._editor_stack.insertWidget(index, widget)
            self._editor_pages[index] = widget

    # ═════════════════════════════════════════════════════════════
    # Activity bar
    # ═════════════════════════════════════════════════════════════

    def _on_activity_icon(self, index: int) -> None:
        """Handle activity bar icon click.

        Args:
            index: Icon index, or -1 for settings.
        """
        if index == -1:
            self.toggle_settings()
            return

        # If clicking same icon, toggle sidebar
        if (index == self._activity_bar.active_index
                and self._sidebar.maximumWidth() > 0):
            self.toggle_sidebar()
        else:
            # Ensure sidebar visible
            if self._sidebar.maximumWidth() == 0:
                self._animate_sidebar(280)
            self._sidebar.set_panel(index)

    # ═════════════════════════════════════════════════════════════
    # Sidebar collapse/expand
    # ═════════════════════════════════════════════════════════════

    def toggle_sidebar(self) -> None:
        """Toggle sidebar visibility with animation."""
        if self._sidebar.maximumWidth() > 0:
            self._animate_sidebar(0)
            self._state.sidebar_visible = False
        else:
            self._animate_sidebar(280)
            self._state.sidebar_visible = True
        self._state.save()

    def _animate_sidebar(self, target_width: int) -> None:
        """Animate sidebar width change.

        Args:
            target_width: Target width (0 to collapse, 280 to expand).
        """
        anim = QPropertyAnimation(self._sidebar, b"maximumWidth")
        anim.setDuration(200)
        anim.setStartValue(self._sidebar.maximumWidth())
        anim.setEndValue(target_width)
        anim.start()
        # Keep ref so it doesn't get garbage collected
        self._sidebar_anim = anim

    # ═════════════════════════════════════════════════════════════
    # Bottom panel
    # ═════════════════════════════════════════════════════════════

    def toggle_bottom_panel(self) -> None:
        """Toggle bottom panel visibility."""
        if self._bottom_panel.maximumHeight() == 0:
            self._bottom_panel.setMaximumHeight(16777215)
            self._splitter.setSizes([600, 200])
            self._state.bottom_panel_visible = True
        else:
            self._bottom_panel.setMaximumHeight(0)
            self._state.bottom_panel_visible = False
        self._state.save()

    # ═════════════════════════════════════════════════════════════
    # Settings panel
    # ═════════════════════════════════════════════════════════════

    def toggle_settings(self) -> None:
        """Toggle settings panel in the editor area."""
        if self._settings_visible:
            # Go back to last tab
            self._on_tab_click(0)
        else:
            # Refresh settings state before showing
            self._settings_panel.refresh_state()
            # Show settings (it's the last widget in the stack)
            settings_idx = self._editor_stack.count() - 1
            self._editor_stack.setCurrentIndex(settings_idx)
            self._settings_visible = True
            # Deselect all tabs
            for btn in self._tab_buttons:
                btn.setChecked(False)
                btn.setStyleSheet(
                    "background: transparent; border: none;"
                    " border-top: 2px solid transparent;"
                    " color: #858585; padding: 0 16px;"
                    " font-size: 12px;"
                )

    # ═════════════════════════════════════════════════════════════
    # Theme
    # ═════════════════════════════════════════════════════════════

    def set_theme(self, theme: str) -> None:
        """Apply a theme to the application.

        Args:
            theme: 'dark' or 'light'.
        """
        self._state.theme = theme
        self._state.save()
        apply_theme(theme)
        self._event_bus.theme_changed.emit(theme)

    # ═════════════════════════════════════════════════════════════
    # Signal handlers
    # ═════════════════════════════════════════════════════════════

    @Slot(str)
    def _on_screen_changed(self, screen: str) -> None:
        log.debug(f"Screen changed to: {screen}")

    @Slot(str, str)
    def _on_notification(self, title: str, message: str) -> None:
        log.info(f"Notification: {title} - {message}")

    # ═════════════════════════════════════════════════════════════
    # Window geometry save/restore
    # ═════════════════════════════════════════════════════════════

    def closeEvent(self, event) -> None:
        """Save state before closing."""
        geo = self.geometry()
        self._state.window_geometry = (
            f"{geo.x()},{geo.y()},{geo.width()},{geo.height()}"
        )
        self._state.save()
        log.info("MainWindow closed, state saved")
        event.accept()

    def restore_geometry_from_state(self) -> None:
        """Restore window geometry from saved state."""
        geo_str = self._state.window_geometry
        if geo_str:
            try:
                parts = geo_str.split(",")
                if len(parts) == 4:
                    x, y, w, h = [int(p) for p in parts]
                    self.setGeometry(x, y, w, h)
                    return
            except (ValueError, IndexError):
                pass
        # Center on screen
        screen = QApplication.primaryScreen()
        if screen:
            center = screen.availableGeometry().center()
            geo = self.frameGeometry()
            geo.moveCenter(center)
            self.move(geo.topLeft())


# ═════════════════════════════════════════════════════════════════
# Standalone test entry point
# ═════════════════════════════════════════════════════════════════

def main() -> None:
    """Launch MainWindow for standalone testing."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)

    window = MainWindow()
    window.restore_geometry_from_state()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    # Add project root to path
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()


__all__ = ["MainWindow", "TitleBar", "ActivityBar", "Sidebar", "StatusBar", "SettingsPanel", "SettingsBridge"]
