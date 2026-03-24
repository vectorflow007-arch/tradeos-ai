"""
TradeOS India — Setup Wizard screen.

QWebEngineView wrapper that loads setup_wizard.html and bridges
wizard_done(config_json) back to Python via QWebChannel.
"""

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from core.event_bus import EventBus
from core.state_store import AppState
from utils.keychain import set_secret
from utils.logger import get_logger

log = get_logger("ui.screens.setup_wizard")


class WizardBridge(QObject):
    """Python side of the QWebChannel bridge for the setup wizard."""

    wizard_completed = Signal(dict)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._state = AppState.get_instance()
        self._event_bus = EventBus.get_instance()

    @Slot(str)
    def wizard_done(self, config_json: str) -> None:
        """Called from JS when user clicks Launch in the wizard."""
        try:
            cfg = json.loads(config_json)
            log.info("Wizard completed, applying config")

            # Trading mode
            self._state.mode = cfg.get("mode", "paper")

            # Markets
            self._state.active_markets = cfg.get("markets", ["NSE", "NFO"])

            # Daily loss
            self._state.daily_loss_limit = float(cfg.get("daily_loss_limit", 5000))

            # Broker
            self._state.broker_name = cfg.get("broker", "fyers")

            # Store broker creds in keyring (never in state)
            app_id = cfg.get("fyers_app_id", "")
            secret = cfg.get("fyers_secret", "")
            pin = cfg.get("fyers_pin", "")
            if app_id:
                set_secret("fyers_app_id", app_id)
            if secret:
                set_secret("fyers_secret", secret)
            if pin:
                set_secret("fyers_pin", pin)

            # LLM
            self._state.llm_primary = cfg.get("llm_primary", "claude")

            # Agents
            agents = cfg.get("agents", {})
            self._state.agents_enabled = {
                "strategy": agents.get("strategy", True),
                "risk": agents.get("risk", True),
                "execution": agents.get("execution", True),
                "research": agents.get("research", True),
            }

            self._state.save()

            # Emit signals
            self._event_bus.wizard_completed.emit(cfg)
            self.wizard_completed.emit(cfg)
            log.info(f"Config applied: {self._state.mode} mode, "
                     f"{len(self._state.active_markets)} markets")

        except Exception as e:
            log.error(f"Failed to process wizard config: {e}")

    @Slot(str)
    def test_connection(self, broker: str) -> None:
        """Simulate broker connection test from wizard."""
        log.info(f"Wizard: test connection for {broker}")

    @Slot()
    def pause_agents(self) -> None:
        """Stub for monitor bridge compatibility."""
        pass

    @Slot()
    def kill_switch(self) -> None:
        """Stub for monitor bridge compatibility."""
        pass


class SetupWizardScreen(QWidget):
    """Setup wizard screen — shown on first run or via menu."""

    wizard_completed = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SetupWizardScreen")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Bridge
        self._bridge = WizardBridge(self)
        self._bridge.wizard_completed.connect(self.wizard_completed.emit)

        # Web view
        self._view = QWebEngineView()

        # Channel
        self._channel = QWebChannel()
        self._channel.registerObject("pyBridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        # Load HTML
        html_path = Path(__file__).parent.parent.parent / "assets" / "wizard" / "setup_wizard.html"
        self._view.setUrl(QUrl.fromLocalFile(str(html_path.resolve())))
        self._view.loadFinished.connect(self._on_load_finished)

        layout.addWidget(self._view)

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
            log.info("Setup wizard HTML loaded")


__all__ = ["SetupWizardScreen", "WizardBridge"]
