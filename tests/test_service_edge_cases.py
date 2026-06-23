"""Targeted tests for price_service quality scoring."""

from gw2_progression.services.price_service import compute_price_quality


class TestPriceQuality:
    def test_reliable(self):
        quality = compute_price_quality(buy_price=10000, sell_price=11000, buy_qty=5000, sell_qty=3000)
        assert quality["quality_status"] == "reliable"
        assert quality["liquidity_score"] == "high"

    def test_wide_spread(self):
        quality = compute_price_quality(buy_price=5000, sell_price=10000, buy_qty=1000, sell_qty=500)
        assert quality["quality_status"] == "wide_spread"

    def test_low_liquidity_takes_precedence(self):
        quality = compute_price_quality(buy_price=1000, sell_price=5000, buy_qty=100, sell_qty=50)
        assert quality["quality_status"] == "low_liquidity"
        assert quality["liquidity_score"] == "low"

    def test_illiquid(self):
        quality = compute_price_quality(buy_price=0, sell_price=11000, buy_qty=0, sell_qty=0)
        assert quality["liquidity_score"] == "illiquid"

    def test_missing_buy(self):
        quality = compute_price_quality(buy_price=0, sell_price=11000, buy_qty=0, sell_qty=100)
        assert quality["quality_status"] == "missing_buy"

    def test_missing_sell(self):
        quality = compute_price_quality(buy_price=10000, sell_price=0, buy_qty=100, sell_qty=0)
        assert quality["quality_status"] == "missing_sell"
