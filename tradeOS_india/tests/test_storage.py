"""Tests for storage/ modules: db, cache."""

import asyncio
import tempfile
import pytest
from pathlib import Path


class TestDatabase:
    def test_import(self):
        from storage.db import init_db, insert_trade, get_trades
        assert init_db is not None

    def test_init_db(self):
        from storage.db import init_db, close_db
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(init_db())
            loop.run_until_complete(close_db())
        finally:
            loop.close()

    def test_settings_crud(self):
        from storage.db import init_db, close_db, get_setting, set_setting
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(init_db())
            loop.run_until_complete(set_setting("test_key", "test_value"))
            val = loop.run_until_complete(get_setting("test_key"))
            assert val == "test_value"
            loop.run_until_complete(close_db())
        finally:
            loop.close()

    def test_watchlist(self):
        from storage.db import (
            init_db, close_db, add_to_watchlist,
            get_watchlist, remove_from_watchlist,
        )
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(init_db())
            loop.run_until_complete(
                add_to_watchlist("NSE:RELIANCE-EQ", "NSE")
            )
            wl = loop.run_until_complete(get_watchlist())
            assert any(w["symbol"] == "NSE:RELIANCE-EQ" for w in wl)
            loop.run_until_complete(
                remove_from_watchlist("NSE:RELIANCE-EQ", "NSE")
            )
            loop.run_until_complete(close_db())
        finally:
            loop.close()


class TestCache:
    def test_import(self):
        from storage.cache import (
            save_contracts, load_contracts, is_contracts_stale,
            save_candles, load_candles, clear_cache,
        )
        assert save_contracts is not None

    def test_contracts_roundtrip(self):
        import polars as pl
        from storage.cache import save_contracts, load_contracts

        df = pl.DataFrame({
            "symbol": ["NSE:RELIANCE-EQ", "NSE:TCS-EQ"],
            "name": ["Reliance", "TCS"],
        })
        save_contracts("NSE_CM", df)
        loaded = load_contracts("NSE_CM")
        assert loaded is not None
        assert len(loaded) == 2

    def test_is_contracts_stale(self):
        from storage.cache import is_contracts_stale
        # A segment we haven't cached should be stale
        result = is_contracts_stale("NONEXISTENT_SEGMENT")
        assert result is True

    def test_candles_roundtrip(self):
        import polars as pl
        from storage.cache import save_candles, load_candles

        df = pl.DataFrame({
            "timestamp": [1700000000, 1700000060],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1000, 2000],
        })
        save_candles("NSE:TEST-EQ", "1m", df)
        loaded = load_candles("NSE:TEST-EQ", "1m")
        assert loaded is not None
        assert len(loaded) == 2
