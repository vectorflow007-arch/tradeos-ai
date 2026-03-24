"""
TradeOS India — Application constants.

Exchange codes, market segments, timeframes, and other fixed values.
"""

from typing import Final

# ─── Application identity ────────────────────────────────────────
APP_NAME: Final[str] = "TradeOS India"
APP_VERSION: Final[str] = "1.0.0"
APP_AUTHOR: Final[str] = "TradeOS"

# ─── Exchange codes ──────────────────────────────────────────────
EXCHANGE_NSE: Final[str] = "NSE"
EXCHANGE_BSE: Final[str] = "BSE"
EXCHANGE_NFO: Final[str] = "NFO"
EXCHANGE_MCX: Final[str] = "MCX"
EXCHANGE_CDS: Final[str] = "CDS"

ALL_EXCHANGES: Final[list[str]] = [
    EXCHANGE_NSE,
    EXCHANGE_BSE,
    EXCHANGE_NFO,
    EXCHANGE_MCX,
    EXCHANGE_CDS,
]

# ─── Market segments ────────────────────────────────────────────
SEGMENT_EQUITY: Final[str] = "equity"
SEGMENT_FUTURES: Final[str] = "futures"
SEGMENT_OPTIONS: Final[str] = "options"
SEGMENT_COMMODITY: Final[str] = "commodity"
SEGMENT_CURRENCY: Final[str] = "currency"

EXCHANGE_SEGMENT_MAP: Final[dict[str, str]] = {
    "NSE": SEGMENT_EQUITY,
    "BSE": SEGMENT_EQUITY,
    "NFO": SEGMENT_OPTIONS,
    "MCX": SEGMENT_COMMODITY,
    "CDS": SEGMENT_CURRENCY,
}

# ─── Timeframes ──────────────────────────────────────────────────
TIMEFRAME_1M: Final[str] = "1m"
TIMEFRAME_5M: Final[str] = "5m"
TIMEFRAME_15M: Final[str] = "15m"
TIMEFRAME_1H: Final[str] = "1h"
TIMEFRAME_1D: Final[str] = "1D"

ALL_TIMEFRAMES: Final[list[str]] = [
    TIMEFRAME_1M,
    TIMEFRAME_5M,
    TIMEFRAME_15M,
    TIMEFRAME_1H,
    TIMEFRAME_1D,
]

TIMEFRAME_SECONDS: Final[dict[str, int]] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "1D": 86400,
}

# ─── Order sides ─────────────────────────────────────────────────
SIDE_BUY: Final[str] = "BUY"
SIDE_SELL: Final[str] = "SELL"

# ─── Order types ─────────────────────────────────────────────────
ORDER_TYPE_MARKET: Final[str] = "MARKET"
ORDER_TYPE_LIMIT: Final[str] = "LIMIT"
ORDER_TYPE_SL: Final[str] = "SL"
ORDER_TYPE_SLM: Final[str] = "SLM"

# ─── Product types ───────────────────────────────────────────────
PRODUCT_CNC: Final[str] = "CNC"
PRODUCT_MIS: Final[str] = "MIS"
PRODUCT_NRML: Final[str] = "NRML"

# ─── Fyers field mappings ───────────────────────────────────────
FYERS_SIDE_MAP: Final[dict[str, int]] = {"BUY": 1, "SELL": -1}

FYERS_ORDER_TYPE_MAP: Final[dict[str, int]] = {
    "MARKET": 2,
    "LIMIT": 1,
    "SL": 3,
    "SLM": 4,
}

FYERS_PRODUCT_MAP: Final[dict[str, str]] = {
    "CNC": "CNC",
    "MIS": "INTRADAY",
    "NRML": "MARGIN",
}

# ─── Fyers master contract URLs ─────────────────────────────────
FYERS_CONTRACT_URLS: Final[dict[str, str]] = {
    "NSE_CM": "https://public.fyers.in/sym_details/NSE_CM.csv",
    "NSE_FO": "https://public.fyers.in/sym_details/NSE_FO.csv",
    "BSE_CM": "https://public.fyers.in/sym_details/BSE_CM.csv",
    "MCX_COM": "https://public.fyers.in/sym_details/MCX_COM.csv",
    "CDS_FO": "https://public.fyers.in/sym_details/CDS_FO.csv",
}

# ─── Fyers OAuth ─────────────────────────────────────────────────
FYERS_REDIRECT_URI: Final[str] = "http://127.0.0.1:8182/callback"
FYERS_CALLBACK_PORT: Final[int] = 8182

# ─── LLM providers ──────────────────────────────────────────────
LLM_CLAUDE: Final[str] = "claude"
LLM_OPENAI: Final[str] = "openai"
LLM_GROQ: Final[str] = "groq"

LLM_MODELS: Final[dict[str, str]] = {
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "groq": "llama-3.1-70b-versatile",
}

LLM_COST_PER_1K_INR: Final[dict[str, float]] = {
    "claude": 0.9,
    "openai": 1.1,
    "groq": 0.05,
}

# ─── Keyring keys ───────────────────────────────────────────────
KEYRING_FYERS_TOKEN: Final[str] = "fyers_token"
KEYRING_FYERS_APP_ID: Final[str] = "fyers_app_id"
KEYRING_FYERS_SECRET: Final[str] = "fyers_secret"
KEYRING_CLAUDE_TOKEN: Final[str] = "tradeOS_claude_token"
KEYRING_OPENAI_KEY: Final[str] = "tradeOS_openai_key"
KEYRING_GROQ_KEY: Final[str] = "tradeOS_groq_key"

# ─── Agent names ─────────────────────────────────────────────────
AGENT_STRATEGY: Final[str] = "strategy"
AGENT_RISK: Final[str] = "risk"
AGENT_EXECUTION: Final[str] = "execution"
AGENT_RESEARCH: Final[str] = "research"

ALL_AGENTS: Final[list[str]] = [
    AGENT_STRATEGY,
    AGENT_RISK,
    AGENT_EXECUTION,
    AGENT_RESEARCH,
]

# ─── UI theme colors ────────────────────────────────────────────
COLOR_BG_DARK: Final[str] = "#1e1e1e"
COLOR_BG_TITLEBAR: Final[str] = "#1a1d23"
COLOR_ACCENT: Final[str] = "#007acc"
COLOR_WARNING: Final[str] = "#d7ba7d"
COLOR_ERROR: Final[str] = "#f44747"
COLOR_SUCCESS: Final[str] = "#4ec9b0"
COLOR_TEXT: Final[str] = "#cccccc"
COLOR_TEXT_DIM: Final[str] = "#808080"

# ─── UI dimensions ──────────────────────────────────────────────
TITLEBAR_HEIGHT: Final[int] = 32
ACTIVITY_BAR_WIDTH: Final[int] = 48
SIDEBAR_WIDTH: Final[int] = 280
STATUSBAR_HEIGHT: Final[int] = 22
TAB_HEIGHT: Final[int] = 35
BOTTOM_PANEL_HEIGHT: Final[int] = 200

# ─── Risk defaults ──────────────────────────────────────────────
DEFAULT_DAILY_LOSS_LIMIT: Final[float] = 5000.0
DEFAULT_RISK_PER_TRADE_PCT: Final[float] = 1.0
DEFAULT_MAX_POSITIONS: Final[int] = 5
DEFAULT_MAX_SL_PCT: Final[float] = 2.0
DEFAULT_CIRCUIT_BREAKER_PCT: Final[float] = 80.0

# ─── Trading modes ──────────────────────────────────────────────
MODE_PAPER: Final[str] = "paper"
MODE_LIVE: Final[str] = "live"


__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "ALL_EXCHANGES",
    "ALL_TIMEFRAMES",
    "TIMEFRAME_SECONDS",
    "FYERS_CONTRACT_URLS",
    "FYERS_REDIRECT_URI",
    "FYERS_CALLBACK_PORT",
    "FYERS_SIDE_MAP",
    "FYERS_ORDER_TYPE_MAP",
    "FYERS_PRODUCT_MAP",
    "LLM_MODELS",
    "LLM_COST_PER_1K_INR",
    "ALL_AGENTS",
    "MODE_PAPER",
    "MODE_LIVE",
]
