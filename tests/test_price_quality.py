"""Tests for price quality and liquidity scoring."""

import pytest

from gw2_progression.services.price_service import compute_price_quality


class TestPriceQuality:
    def test_reliable_price(self):
        result = compute_price_quality(buy_price=10000, sell_price=11000, buy_qty=10000, sell_qty=8000)
        assert result["quality_status"] == "reliable"
        assert result["liquidity_score"] == "high"
        assert result["spread"] == 1000
        assert result["spread_ratio"] == pytest.approx(0.0909, 0.01)

    def test_medium_liquidity(self):
        result = compute_price_quality(buy_price=500, sell_price=600, buy_qty=300, sell_qty=400)
        assert result["liquidity_score"] == "medium"
        assert result["quality_status"] == "reliable"

    def test_low_liquidity(self):
        result = compute_price_quality(buy_price=10000, sell_price=11000, buy_qty=10, sell_qty=5)
        assert result["liquidity_score"] == "low"
        assert result["quality_status"] == "low_liquidity"

    def test_illiquid(self):
        result = compute_price_quality(buy_price=10000, sell_price=11000, buy_qty=0, sell_qty=0)
        assert result["liquidity_score"] == "illiquid"
        assert result["quality_status"] == "illiquid"

    def test_missing_buy_price(self):
        result = compute_price_quality(buy_price=0, sell_price=11000, buy_qty=100, sell_qty=200)
        assert result["quality_status"] == "missing_buy"
        assert result["spread"] == 11000

    def test_missing_sell_price(self):
        result = compute_price_quality(buy_price=10000, sell_price=0, buy_qty=100, sell_qty=200)
        assert result["quality_status"] == "missing_sell"

    def test_wide_spread(self):
        result = compute_price_quality(buy_price=5000, sell_price=10000, buy_qty=10000, sell_qty=8000)
        assert result["quality_status"] == "wide_spread"
        assert result["spread_ratio"] == 0.5

    def test_zero_prices_no_volume(self):
        result = compute_price_quality(buy_price=0, sell_price=0, buy_qty=0, sell_qty=0)
        assert result["liquidity_score"] == "illiquid"
        assert result["quality_status"] == "illiquid"
