"""Tests for utils/ modules: logger, keychain, date_utils."""

import pytest
from datetime import datetime


class TestLogger:
    def test_get_logger(self):
        from utils.logger import get_logger
        log = get_logger("test_module")
        assert log is not None

    def test_log_dir_exists(self):
        from utils.logger import LOG_DIR
        assert LOG_DIR.exists()


class TestKeychain:
    def test_set_and_get_secret(self):
        from utils.keychain import set_secret, get_secret, delete_secret
        ok = set_secret("_test_key_tradeos", "test_value_123")
        assert ok is True
        val = get_secret("_test_key_tradeos")
        assert val == "test_value_123"
        delete_secret("_test_key_tradeos")

    def test_get_nonexistent(self):
        from utils.keychain import get_secret
        val = get_secret("_nonexistent_key_xyz_999")
        assert val is None

    def test_has_secret(self):
        from utils.keychain import has_secret, set_secret, delete_secret
        set_secret("_test_has_key", "val")
        assert has_secret("_test_has_key") is True
        delete_secret("_test_has_key")


class TestDateUtils:
    def test_now_ist(self):
        from utils.date_utils import now_ist, IST
        dt = now_ist()
        assert dt.tzinfo is not None
        assert str(dt.tzinfo) == str(IST)

    def test_today_ist(self):
        from utils.date_utils import today_ist
        result = today_ist()
        assert len(result) == 10  # YYYY-MM-DD
        assert result[4] == "-"

    def test_ist_timestamp(self):
        from utils.date_utils import ist_timestamp
        ts = ist_timestamp()
        assert len(ts) == 19  # YYYY-MM-DD HH:MM:SS

    def test_ist_time_str(self):
        from utils.date_utils import ist_time_str
        t = ist_time_str()
        assert len(t) == 8  # HH:MM:SS

    def test_is_market_open_returns_bool(self):
        from utils.date_utils import is_market_open
        result = is_market_open()
        assert isinstance(result, bool)

    def test_is_market_open_mcx(self):
        from utils.date_utils import is_market_open
        result = is_market_open("MCX")
        assert isinstance(result, bool)

    def test_is_pre_open_returns_bool(self):
        from utils.date_utils import is_pre_open
        assert isinstance(is_pre_open(), bool)

    def test_is_market_hours_returns_bool(self):
        from utils.date_utils import is_market_hours
        assert isinstance(is_market_hours(), bool)

    def test_parse_datetime(self):
        from utils.date_utils import parse_datetime, IST
        dt = parse_datetime("2024-01-15 10:30:00")
        assert dt.tzinfo is not None
        assert dt.hour == 10

    def test_trading_day(self):
        from utils.date_utils import trading_day
        result = trading_day()
        assert len(result) == 10
        dt = datetime.strptime(result, "%Y-%m-%d")
        assert dt.weekday() < 5  # Not weekend

    def test_seconds_to_market_open(self):
        from utils.date_utils import seconds_to_market_open
        result = seconds_to_market_open()
        assert result is None or isinstance(result, int)

    def test_format_date(self):
        from utils.date_utils import format_date, now_ist
        result = format_date(now_ist())
        assert len(result) == 10
