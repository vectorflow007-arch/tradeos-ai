"""
TradeOS India — Centralized Qt signal event bus.

All inter-module communication goes through this singleton QObject.
Every signal used in the app is defined here — no ad-hoc signals elsewhere.
"""

from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """Singleton event bus carrying all application-wide Qt signals."""

    # ── Market data ──────────────────────────────────────────────
    tick_received = Signal(str, dict)             # symbol, tick_data
    candle_closed = Signal(str, str, dict)        # symbol, timeframe, candle
    market_opened = Signal(str)                   # segment name
    market_closed = Signal(str)                   # segment name

    # ── Broker ───────────────────────────────────────────────────
    broker_connected = Signal(str)                # broker name
    broker_disconnected = Signal(str)             # broker name
    broker_error = Signal(str, str)               # broker, error_msg
    funds_updated = Signal(dict)                  # funds dict

    # ── Orders ───────────────────────────────────────────────────
    order_placed = Signal(dict)                   # order dict
    order_filled = Signal(dict)                   # order dict
    order_rejected = Signal(dict, str)            # order, reason
    order_cancelled = Signal(str)                 # order_id
    positions_updated = Signal(list)              # list of position dicts

    # ── Agents ───────────────────────────────────────────────────
    agent_started = Signal(str)                   # agent_name
    agent_stopped = Signal(str)                   # agent_name
    agent_log = Signal(str, str, str)             # agent_name, level, message
    task_submitted = Signal(str, str)             # task_id, task_type
    task_started = Signal(str, str)               # task_id, task_type
    task_completed = Signal(str, dict)            # task_id, result
    task_failed = Signal(str, str)                # task_id, error

    # ── LLM ──────────────────────────────────────────────────────
    llm_request = Signal(str, str, str)           # agent, provider, prompt_preview
    llm_response = Signal(str, str, dict)         # agent, provider, response_meta
    llm_stream_chunk = Signal(str, str)           # agent, chunk_text
    tokens_updated = Signal(int, float)           # total_tokens, cost_inr

    # ── Risk ─────────────────────────────────────────────────────
    daily_loss_updated = Signal(float, float)     # used, limit
    circuit_breaker_triggered = Signal(float)     # loss_pct
    kill_switch_triggered = Signal()
    risk_warning = Signal(str)                    # warning message
    risk_event = Signal(str, dict)                # event_type, data

    # ── UI ───────────────────────────────────────────────────────
    screen_changed = Signal(str)                  # screen name
    theme_changed = Signal(str)                   # theme name
    wizard_completed = Signal(dict)               # full config dict
    notification = Signal(str, str)               # title, message

    @classmethod
    def get_instance(cls) -> "EventBus":
        """Convenience classmethod — same as get_event_bus()."""
        return get_event_bus()


# ─── Singleton ───────────────────────────────────────────────────
_event_bus_instance: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the singleton EventBus instance.

    Creates the instance on first call.
    Must be called after QApplication is created.
    """
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance


__all__ = ["EventBus", "get_event_bus"]
