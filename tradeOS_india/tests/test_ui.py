"""Tests for ui/ modules: theme, main_window, screens."""

import pytest


class TestTheme:
    def test_dark_qss(self):
        from ui.theme import DARK_QSS
        assert len(DARK_QSS) > 1000
        assert "#1e1e1e" in DARK_QSS  # dark bg

    def test_light_qss(self):
        from ui.theme import LIGHT_QSS
        assert len(LIGHT_QSS) > 1000
        assert "#ffffff" in LIGHT_QSS  # light bg

    def test_colors(self):
        from ui.theme import COLORS_DARK, COLORS_LIGHT
        assert COLORS_DARK["accent"] == "#007acc"
        assert COLORS_LIGHT["accent"] == "#007acc"
        assert COLORS_DARK["bg_primary"] == "#1e1e1e"
        assert COLORS_LIGHT["bg_primary"] == "#ffffff"

    def test_apply_theme(self, qapp):
        from ui.theme import apply_theme
        apply_theme("dark")
        apply_theme("light")
        apply_theme("dark")

    def test_get_color(self):
        from ui.theme import get_color
        assert get_color("accent") == "#007acc"
        assert get_color("accent", "light") == "#007acc"
        assert get_color("bg_primary", "dark") == "#1e1e1e"


class TestMainWindow:
    def test_creation(self, qapp):
        from ui.main_window import MainWindow
        w = MainWindow()
        assert w.windowTitle() == "TradeOS India"
        w.close()
        w.deleteLater()

    def test_title_bar(self, qapp):
        from ui.main_window import TitleBar, MainWindow
        w = MainWindow()
        assert w._title_bar is not None
        w.close()
        w.deleteLater()

    def test_activity_bar(self, qapp):
        from ui.main_window import ActivityBar
        ab = ActivityBar()
        assert ab.active_index == 0
        ab.deleteLater()

    def test_sidebar(self, qapp):
        from ui.main_window import Sidebar
        sb = Sidebar()
        sb.set_panel(0)
        sb.set_panel(3)
        sb.deleteLater()

    def test_status_bar(self, qapp):
        from ui.main_window import StatusBar
        sb = StatusBar()
        sb.set_status("ok")
        sb.set_status("warning")
        sb.set_status("error")
        sb.deleteLater()

    def test_toggle_sidebar(self, qapp):
        from ui.main_window import MainWindow
        w = MainWindow()
        w.toggle_sidebar()
        w.toggle_sidebar()
        w.close()
        w.deleteLater()

    def test_toggle_bottom_panel(self, qapp):
        from ui.main_window import MainWindow
        w = MainWindow()
        w.toggle_bottom_panel()
        w.toggle_bottom_panel()
        w.close()
        w.deleteLater()

    def test_set_theme(self, qapp):
        from ui.main_window import MainWindow
        w = MainWindow()
        w.set_theme("light")
        w.set_theme("dark")
        w.close()
        w.deleteLater()

    def test_replace_editor_page(self, qapp):
        from ui.main_window import MainWindow
        from PySide6.QtWidgets import QLabel
        w = MainWindow()
        label = QLabel("Test")
        w.replace_editor_page(4, label)  # Replace Terminal tab
        w.close()
        w.deleteLater()


class TestScreens:
    def test_strategy_builder(self, qapp):
        from ui.screens.strategy_builder import StrategyBuilderScreen
        s = StrategyBuilderScreen()
        assert "strategy_name" in s.get_strategy_text()
        s.deleteLater()

    def test_backtest_screen(self, qapp):
        from ui.screens.backtest_screen import BacktestScreen
        s = BacktestScreen()
        assert s.objectName() == "BacktestScreen"
        s.deleteLater()

    def test_agent_monitor(self, qapp):
        from ui.screens.agent_monitor import AgentMonitorScreen
        s = AgentMonitorScreen()
        s.update_agent_status("strategy", "RUNNING")
        s.deleteLater()

    def test_risk_monitor(self, qapp):
        from ui.screens.risk_monitor import RiskMonitorScreen
        s = RiskMonitorScreen()
        s.update_daily_pnl(-2000.0, 5000.0)
        s.set_circuit_breaker(True)
        s.set_circuit_breaker(False)
        s.deleteLater()

    def test_risk_gauge(self, qapp):
        from ui.screens.risk_monitor import RiskGauge
        g = RiskGauge()
        g.set_value(0.5, "50%")
        assert g._value == 0.5
        g.set_value(2.0)  # Should clamp to 1.0
        assert g._value == 1.0
        g.deleteLater()

    def test_setup_wizard_bridge(self, qapp):
        from ui.screens.setup_wizard import WizardBridge
        b = WizardBridge()
        assert b is not None
        b.deleteLater()

    def test_monitor_bridge(self, qapp):
        from ui.screens.dashboard import MonitorBridge
        b = MonitorBridge()
        b.pause_agents()
        b.kill_switch()
        b.deleteLater()

    def test_screen_exports(self):
        from ui.screens import (
            SetupWizardScreen, WizardBridge,
            DashboardScreen, MonitorBridge,
            StrategyBuilderScreen, BacktestScreen,
            AgentMonitorScreen, RiskMonitorScreen,
        )
        assert len([
            SetupWizardScreen, WizardBridge,
            DashboardScreen, MonitorBridge,
            StrategyBuilderScreen, BacktestScreen,
            AgentMonitorScreen, RiskMonitorScreen,
        ]) == 8


class TestMainApp:
    def test_tradeos_app(self, qapp):
        from main import TradeOSApp
        app = TradeOSApp()
        assert app._window is not None
        assert app._dashboard is not None
        app._window.close()
        app._window.deleteLater()
