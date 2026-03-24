"""
TradeOS India — Live Monitor / Dashboard screen.

QWebEngineView wrapper that loads monitor.html and bridges
real-time data from Python agents/broker to the HTML UI.
"""

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from core.event_bus import EventBus
from core.state_store import AppState
from utils.logger import get_logger

log = get_logger("ui.screens.dashboard")


class MonitorBridge(QObject):
    """Python side of the QWebChannel bridge for the live monitor."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._state = AppState.get_instance()
        self._event_bus = EventBus.get_instance()
        self._view = None

    def set_view(self, view: QWebEngineView) -> None:
        self._view = view

    @Slot()
    def pause_agents(self) -> None:
        """Toggle agent pause state."""
        self._state.agents_paused = not self._state.agents_paused
        log.info(f"Agents paused: {self._state.agents_paused}")

    @Slot()
    def kill_switch(self) -> None:
        """Trigger emergency kill switch."""
        self._state.agents_paused = True
        self._state.agents_running = False
        self._event_bus.kill_switch_triggered.emit()
        log.warning("KILL SWITCH activated from monitor")

    def push_tick(self, symbol: str, data: dict) -> None:
        """Push a tick update to the HTML UI."""
        if self._view:
            js = f"if(typeof onTickReceived==='function')onTickReceived('{symbol}',{json.dumps(data)});"
            self._view.page().runJavaScript(js)

    def push_agent_log(self, agent: str, level: str, message: str) -> None:
        """Push an agent log entry to the HTML UI."""
        if self._view:
            safe_msg = message.replace("'", "\\'").replace("\n", " ")
            js = f"if(typeof onAgentLog==='function')onAgentLog('{agent}','{level}','{safe_msg}');"
            self._view.page().runJavaScript(js)

    def push_order_filled(self, order_data: dict) -> None:
        """Push a filled order to the HTML UI."""
        if self._view:
            js = f"if(typeof onOrderFilled==='function')onOrderFilled({json.dumps(order_data)});"
            self._view.page().runJavaScript(js)


class DashboardScreen(QWidget):
    """Live trading monitor dashboard — loads monitor.html."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("DashboardScreen")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Bridge
        self._bridge = MonitorBridge(self)

        # Web view
        self._view = QWebEngineView()
        self._bridge.set_view(self._view)

        # Channel
        self._channel = QWebChannel()
        self._channel.registerObject("pyBridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        # Load HTML
        html_path = Path(__file__).parent.parent.parent / "assets" / "wizard" / "monitor.html"
        self._view.setUrl(QUrl.fromLocalFile(str(html_path.resolve())))
        self._view.loadFinished.connect(self._on_load_finished)

        layout.addWidget(self._view)

        # Connect event bus signals to push data to HTML
        self._event_bus = EventBus.get_instance()
        self._event_bus.tick_received.connect(self._on_tick)
        self._event_bus.agent_log.connect(self._on_agent_log)
        self._event_bus.order_filled.connect(self._on_order_filled)

    def _on_load_finished(self, ok: bool) -> None:
        if ok:
            qwc_js = """
            (function() {
                var script = document.createElement('script');
                script.src = 'qrc:///qtwebchannel/qwebchannel.js';
                script.onload = function() {
                    new QWebChannel(qt.webChannelTransport, function(channel) {
                        window.pyBridge = channel.objects.pyBridge;
                    });
                };
                document.head.appendChild(script);
            })();
            """
            self._view.page().runJavaScript(qwc_js)
            log.info("Monitor HTML loaded")

    def _on_tick(self, symbol: str, data: dict) -> None:
        self._bridge.push_tick(symbol, data)

    def _on_agent_log(self, agent: str, level: str, message: str) -> None:
        self._bridge.push_agent_log(agent, level, message)

    def _on_order_filled(self, order: dict) -> None:
        self._bridge.push_order_filled(order)


__all__ = ["DashboardScreen", "MonitorBridge"]
