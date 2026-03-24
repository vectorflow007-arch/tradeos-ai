"""Tests for core/ modules: event_bus, state_store, worker."""

import pytest


class TestEventBus:
    def test_singleton(self, qapp):
        from core.event_bus import EventBus, get_event_bus
        eb1 = get_event_bus()
        eb2 = EventBus.get_instance()
        assert eb1 is eb2

    def test_signals_exist(self, event_bus):
        # Verify key signals exist
        assert hasattr(event_bus, "tick_received")
        assert hasattr(event_bus, "candle_closed")
        assert hasattr(event_bus, "order_placed")
        assert hasattr(event_bus, "order_filled")
        assert hasattr(event_bus, "agent_log")
        assert hasattr(event_bus, "wizard_completed")
        assert hasattr(event_bus, "kill_switch_triggered")
        assert hasattr(event_bus, "risk_event")
        assert hasattr(event_bus, "theme_changed")

    def test_signal_emit(self, event_bus):
        received = []
        event_bus.notification.connect(lambda t, m: received.append((t, m)))
        event_bus.notification.emit("Test", "Hello")
        assert len(received) == 1
        assert received[0] == ("Test", "Hello")


class TestAppState:
    def test_singleton(self, qapp):
        from core.state_store import AppState, get_app_state
        s1 = get_app_state()
        s2 = AppState.get_instance()
        assert s1 is s2

    def test_default_values(self, app_state):
        assert app_state.mode in ("paper", "live")
        assert isinstance(app_state.active_markets, list)
        assert isinstance(app_state.daily_loss_limit, float)
        assert isinstance(app_state.agents_enabled, dict)
        assert "strategy" in app_state.agents_enabled

    def test_save(self, app_state):
        old_theme = app_state.theme
        app_state.save()
        # Should not raise
        app_state.theme = old_theme

    def test_update_state(self, qapp):
        from core.state_store import update_state, get_app_state
        state = update_state(theme="dark")
        assert state.theme == "dark"

    def test_state_exists(self, qapp):
        from core.state_store import state_exists
        # After saving, file should exist
        result = state_exists()
        assert isinstance(result, bool)

    def test_session_only_fields(self, qapp):
        from core.state_store import SESSION_ONLY_FIELDS
        assert "open_positions" in SESSION_ONLY_FIELDS
        assert "session_pnl" in SESSION_ONLY_FIELDS
        assert "broker_connected" in SESSION_ONLY_FIELDS

    def test_agents_enabled_all_present(self, app_state):
        agents = app_state.agents_enabled
        for name in ["strategy", "risk", "execution", "research"]:
            assert name in agents
            assert isinstance(agents[name], bool)


class TestWorker:
    def test_import(self):
        from core.worker import BaseWorker
        assert BaseWorker is not None
