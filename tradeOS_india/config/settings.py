"""
TradeOS India — Application settings using Pydantic BaseSettings.

Reads from environment variables and .env files (if present).
All configurable parameters are centralized here.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─── Project root directory ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AppSettings(BaseSettings):
    """Global application settings loaded from env vars / .env file."""

    model_config = SettingsConfigDict(
        env_prefix="TRADEOS_",
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App identity ─────────────────────────────────────────────
    app_name: str = "TradeOS India"
    app_version: str = "1.0.0"
    debug: bool = False

    # ── Trading mode ─────────────────────────────────────────────
    mode: Literal["paper", "live"] = "paper"

    # ── Broker ───────────────────────────────────────────────────
    broker: str = "fyers"
    fyers_redirect_uri: str = "http://127.0.0.1:8182/callback"
    fyers_callback_port: int = 8182

    # ── LLM ──────────────────────────────────────────────────────
    llm_primary: Literal["claude", "openai", "groq"] = "claude"
    llm_overnight: Literal["claude", "openai", "groq"] = "groq"
    llm_max_retries: int = 3
    llm_retry_base_delay: float = 1.0

    # ── Risk defaults ────────────────────────────────────────────
    daily_loss_limit: float = 5000.0
    risk_per_trade_pct: float = 1.0
    max_positions: int = 5
    max_sl_pct: float = 2.0
    circuit_breaker_pct: float = 80.0

    # ── Paths ────────────────────────────────────────────────────
    db_path: str = Field(
        default_factory=lambda: str(PROJECT_ROOT / "storage" / "tradeos.db")
    )
    state_path: str = Field(
        default_factory=lambda: str(PROJECT_ROOT / "config" / "app_state.json")
    )
    log_dir: str = Field(
        default_factory=lambda: str(PROJECT_ROOT / "logs")
    )
    contracts_cache_dir: str = Field(
        default_factory=lambda: str(PROJECT_ROOT / "storage" / "contracts")
    )
    candles_cache_dir: str = Field(
        default_factory=lambda: str(PROJECT_ROOT / "storage" / "candles")
    )

    # ── UI ───────────────────────────────────────────────────────
    theme: Literal["dark", "light"] = "dark"
    window_width: int = 1400
    window_height: int = 900

    # ── Feed ─────────────────────────────────────────────────────
    feed_reconnect_max_delay: int = 30
    order_poll_interval_sec: int = 2
    order_poll_timeout_sec: int = 60


# ─── Singleton instance ─────────────────────────────────────────
_settings_instance: AppSettings | None = None


def get_settings() -> AppSettings:
    """Return the singleton AppSettings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = AppSettings()
    return _settings_instance


__all__ = ["AppSettings", "get_settings", "PROJECT_ROOT"]
