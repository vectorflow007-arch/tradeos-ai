"""
TradeOS India — Main window: single QWebEngineView shell.

Frameless window with a slim native title bar (for drag + window controls)
and a full-page HTML UI loaded from shell.html via QWebEngineView.
"""

import json
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QPoint, Qt, QUrl, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QVBoxLayout, QWidget,
)

from core.event_bus import EventBus
from core.state_store import AppState
from ui.theme import apply_theme
from utils.logger import get_logger

log = get_logger("ui.main_window")


# ═════════════════════════════════════════════════════════════════
# Title Bar (minimal — drag + window controls only)
# ═════════════════════════════════════════════════════════════════

class TitleBar(QWidget):
    """Slim frameless title bar: logo + app name + minimize / maximize / close."""

    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(38)
        self._parent = parent
        self._drag_pos: Optional[QPoint] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        # Logo badge
        logo = QLabel("T")
        logo.setObjectName("titlebar_logo")
        logo.setFixedSize(24, 24)
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        # App title
        title = QLabel("TradeOS India")
        title.setObjectName("titlebar_title")
        layout.addWidget(title)

        # Subtle separator dot
        dot = QLabel("\u2022")
        dot.setObjectName("titlebar_dot")
        layout.addWidget(dot)

        # Version / subtitle
        subtitle = QLabel("v1.0")
        subtitle.setObjectName("titlebar_version")
        layout.addWidget(subtitle)

        layout.addStretch()

        # Window control buttons — inline styles override global QSS
        btn_base = (
            "QPushButton {{ background: transparent; border: none;"
            " border-radius: 0px; padding: 0px; color: {icon};"
            " font-family: 'Segoe MDL2 Assets', 'Segoe UI Symbol', sans-serif;"
            " font-size: 10px; font-weight: normal; }}"
            " QPushButton:hover {{ background: {hover}; color: {hover_fg}; }}"
            " QPushButton:pressed {{ background: {pressed}; color: {hover_fg}; }}"
        )
        btn_defs = [
            ("\uE921", "btn_min", self._parent.showMinimized, False),   # minimize
            ("\uE922", "btn_max", self._toggle_maximize, False),        # maximize
            ("\uE8BB", "btn_close", self._parent.close, True),          # close
        ]
        for text, obj_name, slot, is_close in btn_defs:
            btn = QPushButton(text)
            btn.setObjectName(obj_name)
            btn.setFixedSize(46, 38)
            btn.setStyleSheet(btn_base.format(
                icon="#999999",
                hover="#e81123" if is_close else "#3e3e3e",
                hover_fg="#ffffff",
                pressed="#f1707a" if is_close else "#555555",
            ))
            btn.clicked.connect(slot)
            layout.addWidget(btn)

    def _toggle_maximize(self) -> None:
        if self._parent.isMaximized():
            self._parent.showNormal()
        else:
            self._parent.showMaximized()

    # ─── Drag to move ─────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self._parent.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self._parent.move(
                event.globalPosition().toPoint() - self._drag_pos
            )

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event) -> None:
        self._toggle_maximize()


# ═════════════════════════════════════════════════════════════════
# Shell Bridge (Python ↔ JS via QWebChannel)
# ═════════════════════════════════════════════════════════════════

class ShellBridge(QObject):
    """QWebChannel bridge between shell.html and Python backend."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._state = AppState.get_instance()
        self._event_bus = EventBus.get_instance()
        self._view: Optional[QWebEngineView] = None

    def set_view(self, view: QWebEngineView) -> None:
        self._view = view

    @Slot()
    def open_settings(self) -> None:
        """Called from JS when settings icon is clicked."""
        window = self.parent()
        if hasattr(window, "toggle_settings"):
            window.toggle_settings()

    @Slot(result=str)
    def get_state(self) -> str:
        """Return current app state as JSON for JS consumption."""
        return json.dumps({
            "mode": self._state.mode,
            "broker_name": self._state.broker_name,
            "broker_connected": self._state.broker_connected,
            "llm_primary": self._state.llm_primary,
            "active_markets": self._state.active_markets,
            "daily_loss_limit": self._state.daily_loss_limit,
            "risk_per_trade_pct": self._state.risk_per_trade_pct,
            "max_positions": self._state.max_positions,
            "agents_enabled": self._state.agents_enabled,
            "theme": self._state.theme,
            "sidebar_visible": self._state.sidebar_visible,
            "bottom_panel_visible": self._state.bottom_panel_visible,
            "tokens_used_today": self._state.tokens_used_today,
            "cost_inr_today": self._state.cost_inr_today,
        })

    @Slot(str)
    def log_action(self, action: str) -> None:
        """Log a UI action from JS."""
        log.info(f"UI action: {action}")

    def push_to_js(self, fn_call: str) -> None:
        """Execute a JavaScript function in the shell page."""
        if self._view:
            self._view.page().runJavaScript(fn_call)


# ═════════════════════════════════════════════════════════════════
# Settings Bridge (Python ↔ JS for settings wizard)
# ═════════════════════════════════════════════════════════════════

class SettingsBridge(QObject):
    """QWebChannel bridge for the settings wizard HTML page."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._state = AppState.get_instance()
        self._event_bus = EventBus.get_instance()
        self._view: Optional[QWebEngineView] = None

    def set_view(self, view: QWebEngineView) -> None:
        self._view = view

    @Slot()
    def requestState(self) -> None:
        """Push current state into the settings page."""
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
        if self._view:
            self._view.page().runJavaScript(f"loadState('{state_json}')")

    @Slot(str)
    def saveSettings(self, settings_json: str) -> None:
        """Save settings from the wizard page."""
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
        self._state.tokens_used_today = 0
        self._state.cost_inr_today = 0.0
        self._state.save()
        log.info("Token counter reset from settings")


# ═════════════════════════════════════════════════════════════════
# Main Window
# ═════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    """Frameless main window: native title bar + full HTML shell UI."""

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
        """Build the UI: title bar + QWebEngineView shell."""
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Native title bar (for drag + window controls)
        self._title_bar = TitleBar(self)
        root.addWidget(self._title_bar)

        # Shell bridge
        self._shell_bridge = ShellBridge(self)

        # Main HTML shell view
        self._shell_view = QWebEngineView()
        self._shell_bridge.set_view(self._shell_view)

        # QWebChannel for shell
        self._shell_channel = QWebChannel()
        self._shell_channel.registerObject("shellBridge", self._shell_bridge)
        self._shell_view.page().setWebChannel(self._shell_channel)

        # Load shell.html
        shell_path = Path(__file__).parent.parent / "assets" / "shell.html"
        self._shell_view.setUrl(QUrl.fromLocalFile(str(shell_path.resolve())))
        self._shell_view.loadFinished.connect(self._on_shell_loaded)

        root.addWidget(self._shell_view, 1)

        # Settings overlay (hidden by default)
        self._settings_view = QWebEngineView()
        self._settings_bridge = SettingsBridge(self)
        self._settings_bridge.set_view(self._settings_view)

        self._settings_channel = QWebChannel()
        self._settings_channel.registerObject("settings_bridge", self._settings_bridge)
        self._settings_view.page().setWebChannel(self._settings_channel)

        settings_path = Path(__file__).parent.parent / "assets" / "wizard" / "settings.html"
        self._settings_view.setUrl(QUrl.fromLocalFile(str(settings_path.resolve())))
        self._settings_view.loadFinished.connect(self._on_settings_loaded)
        self._settings_view.hide()

        root.addWidget(self._settings_view, 1)

    def _connect_signals(self) -> None:
        self._event_bus.screen_changed.connect(self._on_screen_changed)
        self._event_bus.notification.connect(self._on_notification)

    def _on_shell_loaded(self, ok: bool) -> None:
        if ok:
            # Inject QWebChannel JS then init bridge
            qwc_js = """
            (function() {
                var script = document.createElement('script');
                script.src = 'qrc:///qtwebchannel/qwebchannel.js';
                script.onload = function() { initBridge(); };
                document.head.appendChild(script);
            })();
            """
            self._shell_view.page().runJavaScript(qwc_js)
            log.info("Shell HTML loaded")

    def _on_settings_loaded(self, ok: bool) -> None:
        if ok:
            qwc_js = """
            (function() {
                var script = document.createElement('script');
                script.src = 'qrc:///qtwebchannel/qwebchannel.js';
                script.onload = function() { initBridge(); };
                document.head.appendChild(script);
            })();
            """
            self._settings_view.page().runJavaScript(qwc_js)
            log.info("Settings wizard HTML loaded")

    # ═════════════════════════════════════════════════════════════
    # Settings toggle
    # ═════════════════════════════════════════════════════════════

    def toggle_settings(self) -> None:
        """Toggle between shell view and settings view."""
        if self._settings_visible:
            self._settings_view.hide()
            self._shell_view.show()
            self._settings_visible = False
        else:
            self._settings_bridge.requestState()
            self._shell_view.hide()
            self._settings_view.show()
            self._settings_visible = True

    # ═════════════════════════════════════════════════════════════
    # Theme
    # ═════════════════════════════════════════════════════════════

    def set_theme(self, theme: str) -> None:
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
        geo = self.geometry()
        self._state.window_geometry = (
            f"{geo.x()},{geo.y()},{geo.width()},{geo.height()}"
        )
        self._state.save()
        log.info("MainWindow closed, state saved")
        event.accept()

    def restore_geometry_from_state(self) -> None:
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
        screen = QApplication.primaryScreen()
        if screen:
            center = screen.availableGeometry().center()
            geo = self.frameGeometry()
            geo.moveCenter(center)
            self.move(geo.topLeft())


__all__ = ["MainWindow", "TitleBar", "ShellBridge", "SettingsBridge"]
