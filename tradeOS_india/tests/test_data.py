"""Tests for data/ modules: market_state, candle_builder, feed_router."""

import pytest
import time


class TestMarketState:
    def test_singleton(self, qapp):
        from data.market_state import MarketState
        ms1 = MarketState.get_instance()
        ms2 = MarketState.get_instance()
        assert ms1 is ms2

    def test_update_tick(self, qapp):
        from data.market_state import MarketState
        ms = MarketState.get_instance()
        ms.update_tick("NSE:RELIANCE-EQ", {
            "ltp": 2450.50,
            "volume": 100,
            "timestamp": int(time.time()),
        })
        tick = ms.get_tick("NSE:RELIANCE-EQ")
        assert tick is not None
        assert tick["ltp"] == 2450.50

    def test_get_nonexistent_tick(self, qapp):
        from data.market_state import MarketState
        ms = MarketState.get_instance()
        tick = ms.get_tick("NONEXISTENT:SYMBOL")
        assert tick is None

    def test_candle_storage(self, qapp):
        import polars as pl
        from data.market_state import MarketState, CANDLE_SCHEMA
        ms = MarketState.get_instance()
        df = pl.DataFrame({
            "timestamp": [1700000000],
            "open": [100.0],
            "high": [102.0],
            "low": [99.0],
            "close": [101.0],
            "volume": [1000],
        })
        ms.update_candles("TEST:SYM", "1m", df)
        result = ms.get_candles("TEST:SYM", "1m")
        assert result is not None
        assert len(result) == 1


class TestCandleBuilder:
    def test_import(self):
        from data.candle_builder import CandleBuilder, TIMEFRAME_SECONDS
        assert CandleBuilder is not None
        assert TIMEFRAME_SECONDS["1m"] == 60

    def test_candle_accumulation(self, qapp):
        from data.candle_builder import CandleBuilder
        builder = CandleBuilder("NSE:TEST-EQ")

        base_ts = 1700000000  # some round timestamp
        # Align to 1m boundary
        base_ts = (base_ts // 60) * 60

        # Feed ticks within same 1m bucket using on_tick API
        builder.on_tick({"ltp": 100.0, "volume": 10, "timestamp": base_ts + 5})
        builder.on_tick({"ltp": 102.0, "volume": 20, "timestamp": base_ts + 15})
        builder.on_tick({"ltp": 99.0, "volume": 15, "timestamp": base_ts + 30})
        builder.on_tick({"ltp": 101.0, "volume": 25, "timestamp": base_ts + 55})

        # Tick in next bucket should close the first candle
        builder.on_tick({"ltp": 103.0, "volume": 30, "timestamp": base_ts + 65})

        # The 1m candle should have been emitted
        # (Check via MarketState or just verify no crash)

    def test_timeframe_seconds(self):
        from data.candle_builder import TIMEFRAME_SECONDS
        assert TIMEFRAME_SECONDS["5m"] == 300
        assert TIMEFRAME_SECONDS["15m"] == 900
        assert TIMEFRAME_SECONDS["1h"] == 3600
        assert TIMEFRAME_SECONDS["1D"] == 86400


class TestFeedRouter:
    def test_import(self):
        from data.feed_router import FeedRouter
        assert FeedRouter is not None

    def test_instantiation(self, qapp):
        from data.feed_router import FeedRouter
        fr = FeedRouter()
        assert fr is not None

    def test_subscribe(self, qapp):
        from data.feed_router import FeedRouter
        fr = FeedRouter()
        received = []

        def handler(symbol, data):
            received.append((symbol, data))

        fr.subscribe(handler)
        # Simulate a tick via internal method
        fr._on_tick("NSE:TEST-EQ", {"ltp": 100.0, "volume": 10, "timestamp": 1700000000})
        assert len(received) == 1
        assert received[0][0] == "NSE:TEST-EQ"
