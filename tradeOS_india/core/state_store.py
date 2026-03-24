"""
TradeOS India — Application state store.

Pydantic model persisted to config/app_state.json on every mutation.
Loaded on startup with defaults merged for any missing keys.
Exposed as a thread-safe singleton via AppState.get_instance().
"""

import json
import threading
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from config.settings import get_settings
from utils.logger import get_logger

log = get_logger("core.state_store")


class AppState(BaseModel):
    """Full application state — persisted to JSON on every mutation."""

    # ── Trading mode ─────────────────────────────────────────────
    mode: Literal["paper", "live"] = "paper"

    # ── Market selection ─────────────────────────────────────────
    active_markets: list[str] = Field(default_factory=lambda: ["NSE", "NFO"])
    subscribed_symbols: list[str] = Field(default_factory=list)

    # ── Broker ───────────────────────────────────────────────────
    broker_name: str = "fyers"
    broker_connected: bool = False
    broker_last_connected: str = ""

    # ── LLM ──────────────────────────────────────────────────────
    llm_primary: Literal["claude", "openai", "groq"] = "claude"
    llm_overnight: Literal["groq", "openai"] = "groq"
    llm_connected: bool = False

    # ── Agents ───────────────────────────────────────────────────
    agents_running: bool = False
    agents_paused: bool = False
    agents_enabled: dict[str, bool] = Field(
        default_factory=lambda: {
            "strategy": True,
            "risk": True,
            "execution": True,
            "research": True,
        }
    )

    # ── Risk settings ────────────────────────────────────────────
    daily_loss_limit: float = 5000.0
    daily_loss_used: float = 0.0
    risk_per_trade_pct: float = 1.0
    max_positions: int = 5
    max_sl_pct: float = 2.0
    circuit_breaker_pct: float = 80.0

    # ── Live stats (session only, not persisted) ─────────────────
    open_positions: list[dict[str, Any]] = Field(default_factory=list)
    todays_trades: list[dict[str, Any]] = Field(default_factory=list)
    session_pnl: float = 0.0
    funds: dict[str, Any] = Field(default_factory=dict)

    # ── Tokens ───────────────────────────────────────────────────
    tokens_used_today: int = 0
    cost_inr_today: float = 0.0

    # ── UI preferences ───────────────────────────────────────────
    theme: Literal["dark", "light"] = "dark"
    sidebar_visible: bool = True
    bottom_panel_visible: bool = True
    active_screen: str = "dashboard"
    window_geometry: str = ""

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def get_instance(cls) -> "AppState":
        """Convenience classmethod — same as get_app_state()."""
        return get_app_state()

    def save(self) -> None:
        """Persist current state to disk."""
        _persist(self)


# Fields excluded from persistence (session-only)
SESSION_ONLY_FIELDS: set[str] = {
    "open_positions",
    "todays_trades",
    "session_pnl",
    "funds",
    "tokens_used_today",
    "cost_inr_today",
    "broker_connected",
    "llm_connected",
    "agents_running",
    "agents_paused",
    "daily_loss_used",
}

# ─── Singleton management ───────────────────────────────────────
_instance: AppState | None = None
_lock = threading.Lock()


def _state_path() -> Path:
    """Return the path to the persisted state JSON file."""
    return Path(get_settings().state_path)


def _persist(state: AppState) -> None:
    """Write state to JSON, excluding session-only fields."""
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = state.model_dump()
    for field in SESSION_ONLY_FIELDS:
        data.pop(field, None)
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        log.error(f"Failed to persist state: {exc}")


def load_state() -> AppState:
    """Load state from JSON, merging with defaults for missing keys.

    Returns:
        AppState instance with persisted + default values.
    """
    path = _state_path()
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            state = AppState(**raw)
            log.info(f"State loaded from {path}")
            return state
        except Exception as exc:
            log.warning(f"Failed to load state, using defaults: {exc}")
    return AppState()


def get_app_state() -> AppState:
    """Return the singleton AppState instance.

    Thread-safe. Loads from disk on first call.
    """
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = load_state()
    return _instance


def update_state(**kwargs: Any) -> AppState:
    """Update state fields and persist to disk.

    Args:
        **kwargs: Field names and their new values.

    Returns:
        The updated AppState instance.
    """
    state = get_app_state()
    changed = False
    for key, value in kwargs.items():
        if hasattr(state, key):
            setattr(state, key, value)
            changed = True
        else:
            log.warning(f"Unknown state field: {key}")
    if changed:
        _persist(state)
    return state


def reset_state() -> AppState:
    """Reset state to defaults and persist."""
    global _instance
    with _lock:
        _instance = AppState()
        _persist(_instance)
    log.info("State reset to defaults")
    return _instance


def state_exists() -> bool:
    """Check if a persisted state file exists (used for first-run detection)."""
    return _state_path().exists()


__all__ = [
    "AppState",
    "get_app_state",
    "update_state",
    "reset_state",
    "load_state",
    "state_exists",
]
