"""Tests for config/ modules: settings, constants."""

import pytest


class TestSettings:
    def test_get_settings_singleton(self):
        from config.settings import get_settings
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_settings_defaults(self):
        from config.settings import get_settings
        s = get_settings()
        assert s.app_name == "TradeOS India"
        assert s.mode == "paper"
        assert s.broker == "fyers"
        assert s.daily_loss_limit == 5000.0
        assert s.theme in ("dark", "light")

    def test_project_root(self):
        from config.settings import PROJECT_ROOT
        assert PROJECT_ROOT.exists()
        assert (PROJECT_ROOT / "config").is_dir()

    def test_paths_exist_or_creatable(self):
        from config.settings import get_settings
        from pathlib import Path
        s = get_settings()
        # These are defaults, the parent dirs should exist
        assert Path(s.db_path).parent.name == "storage"
        assert Path(s.state_path).parent.name == "config"


class TestConstants:
    def test_exchanges(self):
        from config.constants import ALL_EXCHANGES
        assert "NSE" in ALL_EXCHANGES
        assert "BSE" in ALL_EXCHANGES
        assert "NFO" in ALL_EXCHANGES
        assert "MCX" in ALL_EXCHANGES
        assert len(ALL_EXCHANGES) == 5

    def test_timeframes(self):
        from config.constants import ALL_TIMEFRAMES, TIMEFRAME_SECONDS
        assert "1m" in ALL_TIMEFRAMES
        assert "5m" in ALL_TIMEFRAMES
        assert "1D" in ALL_TIMEFRAMES
        assert TIMEFRAME_SECONDS["1m"] == 60
        assert TIMEFRAME_SECONDS["1h"] == 3600

    def test_fyers_maps(self):
        from config.constants import (
            FYERS_SIDE_MAP, FYERS_ORDER_TYPE_MAP, FYERS_PRODUCT_MAP,
        )
        assert FYERS_SIDE_MAP["BUY"] == 1
        assert FYERS_SIDE_MAP["SELL"] == -1
        assert FYERS_ORDER_TYPE_MAP["MARKET"] == 2
        assert FYERS_PRODUCT_MAP["MIS"] == "INTRADAY"

    def test_llm_constants(self):
        from config.constants import LLM_MODELS, LLM_COST_PER_1K_INR
        assert "claude" in LLM_MODELS
        assert "openai" in LLM_MODELS
        assert "groq" in LLM_MODELS
        assert LLM_COST_PER_1K_INR["groq"] < LLM_COST_PER_1K_INR["claude"]

    def test_agent_names(self):
        from config.constants import ALL_AGENTS
        assert len(ALL_AGENTS) == 4
        assert "strategy" in ALL_AGENTS
        assert "risk" in ALL_AGENTS

    def test_risk_defaults(self):
        from config.constants import (
            DEFAULT_DAILY_LOSS_LIMIT, DEFAULT_MAX_POSITIONS,
        )
        assert DEFAULT_DAILY_LOSS_LIMIT == 5000.0
        assert DEFAULT_MAX_POSITIONS == 5

    def test_exchange_segment_map(self):
        from config.constants import EXCHANGE_SEGMENT_MAP
        assert EXCHANGE_SEGMENT_MAP["NSE"] == "equity"
        assert EXCHANGE_SEGMENT_MAP["NFO"] == "options"
        assert EXCHANGE_SEGMENT_MAP["MCX"] == "commodity"
