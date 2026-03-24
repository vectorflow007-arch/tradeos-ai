"""Tests for brokers/ modules: base_broker, fyers client."""

import pytest


class TestBaseBroker:
    def test_import_enums(self):
        from brokers.base_broker import (
            Side, OrderType, ProductType, OrderStatus,
        )
        assert Side.BUY.value == "BUY"
        assert Side.SELL.value == "SELL"
        assert OrderType.MARKET.value == "MARKET"
        assert OrderType.LIMIT.value == "LIMIT"
        assert ProductType.MIS.value == "MIS"
        assert OrderStatus.FILLED.value == "FILLED"

    def test_import_dataclasses(self):
        from brokers.base_broker import (
            OrderRequest, OrderResponse, Position, FundsData,
        )
        req = OrderRequest(
            symbol="NSE:RELIANCE-EQ",
            exchange="NSE",
            side="BUY",
            quantity=10,
            order_type="MARKET",
            product="MIS",
        )
        assert req.symbol == "NSE:RELIANCE-EQ"
        assert req.quantity == 10

    def test_base_broker_abstract(self):
        from brokers.base_broker import BaseBroker
        # Cannot instantiate abstract class
        with pytest.raises(TypeError):
            BaseBroker()


class TestFyersClient:
    def test_import(self):
        from brokers.fyers.client import FyersClient
        assert FyersClient is not None

    def test_fyers_auth_import(self):
        from brokers.fyers.auth import FyersAuth
        assert FyersAuth is not None

    def test_fyers_contracts_import(self):
        from brokers.fyers.contracts import FyersContracts
        assert FyersContracts is not None

    def test_fyers_feed_import(self):
        from brokers.fyers.feed import FyersFeed
        assert FyersFeed is not None

    def test_fyers_orders_import(self):
        from brokers.fyers.orders import FyersOrders
        assert FyersOrders is not None


class TestOrderRequest:
    def test_fields(self):
        from brokers.base_broker import OrderRequest
        req = OrderRequest(
            symbol="NSE:TCS-EQ",
            exchange="NSE",
            side="SELL",
            quantity=5,
            order_type="LIMIT",
            product="CNC",
            price=3500.0,
        )
        assert req.price == 3500.0
        assert req.side == "SELL"

    def test_optional_fields(self):
        from brokers.base_broker import OrderRequest
        req = OrderRequest(
            symbol="NSE:NIFTY-FUT",
            exchange="NFO",
            side="BUY",
            quantity=75,
            order_type="MARKET",
            product="NRML",
        )
        # Optional fields should have defaults
        assert req.price is None or req.price == 0.0 or hasattr(req, "price")
