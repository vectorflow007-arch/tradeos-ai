"""Shared pytest fixtures for TradeOS India tests."""

import os
import sys

# Ensure tradeOS_india is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Provide a QApplication instance for the entire test session."""
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def app_state(qapp):
    """Provide a fresh AppState instance."""
    from core.state_store import AppState, get_app_state
    state = get_app_state()
    yield state


@pytest.fixture
def event_bus(qapp):
    """Provide the EventBus singleton."""
    from core.event_bus import EventBus
    return EventBus.get_instance()
