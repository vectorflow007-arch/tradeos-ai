"""
TradeOS India — Application entry point.

Initializes PySide6 app, applies theme, checks first-run state,
wires up all screens into the main window, and starts the event loop.
"""

import asyncio
import sys
import os

# Ensure tradeOS_india is on the path when run as `python main.py`
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import QApplication

from config.settings import get_settings, PROJECT_ROOT
from core.event_bus import EventBus
from core.state_store import AppState, state_exists
from ui.main_window import MainWindow
from ui.theme import apply_theme
from utils.logger import get_logger

log = get_logger("main")


class TradeOSApp:
    """Application controller — owns the QApplication and MainWindow."""

    def __init__(self) -> None:
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setApplicationName("TradeOS India")
        self._app.setApplicationVersion(get_settings().app_version)

        # Singletons (must be created after QApplication)
        self._state = AppState.get_instance()
        self._event_bus = EventBus.get_instance()
        self._settings = get_settings()

        # Apply theme
        apply_theme(self._state.theme)

        # Main window
        self._window = MainWindow()

        # Wire screens
        self._wire_screens()

        # Connect lifecycle signals
        self._event_bus.wizard_completed.connect(self._on_wizard_completed)
        self._event_bus.theme_changed.connect(self._on_theme_changed)

        log.info(f"TradeOS India v{self._settings.app_version} initialized")
        log.info(f"Mode: {self._state.mode} | Broker: {self._state.broker_name} "
                 f"| LLM: {self._state.llm_primary}")

    def _wire_screens(self) -> None:
        """Replace placeholder editor pages with real screen widgets."""
        from ui.screens.dashboard import DashboardScreen
        from ui.screens.strategy_builder import StrategyBuilderScreen
        from ui.screens.backtest_screen import BacktestScreen
        from ui.screens.agent_monitor import AgentMonitorScreen

        # Tab 0: Live Monitor (Dashboard)
        self._dashboard = DashboardScreen()
        self._window.replace_editor_page(0, self._dashboard)

        # Tab 1: Strategy Builder
        self._strategy_builder = StrategyBuilderScreen()
        self._window.replace_editor_page(1, self._strategy_builder)

        # Tab 2: Backtest
        self._backtest = BacktestScreen()
        self._window.replace_editor_page(2, self._backtest)

        # Tab 3: Agent Log
        self._agent_monitor = AgentMonitorScreen()
        self._window.replace_editor_page(3, self._agent_monitor)

        # Tab 4: Terminal stays as placeholder (built-in bottom panel terminal)

        log.info("All screens wired into main window")

    def _check_first_run(self) -> None:
        """If no state file exists, show the setup wizard as a dialog."""
        if not state_exists():
            log.info("First run detected - showing setup wizard")
            self._show_wizard()
        else:
            log.info("Existing config found - skipping wizard")

    def _show_wizard(self) -> None:
        """Show the setup wizard in a dialog window."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QDialog, QVBoxLayout

        from ui.screens.setup_wizard import SetupWizardScreen

        dialog = QDialog(self._window)
        dialog.setWindowTitle("TradeOS India - Setup")
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMaximizeButtonHint)
        dialog.resize(900, 650)
        dialog.setMinimumSize(800, 600)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        wizard = SetupWizardScreen()
        wizard.wizard_completed.connect(lambda cfg: dialog.accept())
        layout.addWidget(wizard)

        dialog.exec()

    @Slot(dict)
    def _on_wizard_completed(self, config: dict) -> None:
        """Handle wizard completion — start services."""
        log.info("Wizard completed, ready to start trading services")

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        log.info(f"Theme changed to: {theme}")

    def run(self) -> int:
        """Show the main window and enter the Qt event loop.

        Returns:
            Exit code.
        """
        self._window.restore_geometry_from_state()
        self._window.show()

        # Check first run after window is shown (slight delay for UI to settle)
        QTimer.singleShot(200, self._check_first_run)

        log.info("Application started")
        return self._app.exec()


def main() -> None:
    """Entry point."""
    log.info("=" * 60)
    log.info("TradeOS India starting...")
    log.info("=" * 60)

    try:
        app = TradeOSApp()
        exit_code = app.run()
    except Exception as e:
        log.exception(f"Fatal error: {e}")
        exit_code = 1

    log.info(f"Application exited with code {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
