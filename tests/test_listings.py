"""Tests for TP order book analysis and arbitrage detection."""

from gw2_progression.services.listing_service import analyze_depth


class TestListingDepth:
    def test_basic_depth(self):
        listing = {
            "item_id": 19976,
            "best_buy": 20000,
            "best_buy_qty": 500,
            "best_sell": 21600,
            "best_sell_qty": 300,
            "buys": [{"unit_price": 20000, "quantity": 500}, {"unit_price": 19900, "quantity": 200}],
            "sells": [{"unit_price": 21600, "quantity": 300}, {"unit_price": 21700, "quantity": 150}],
        }
        depth = analyze_depth(listing)
        assert depth["best_buy"] == 20000
        assert depth["best_sell"] == 21600
        assert depth["spread"] == 1600
        assert depth["buy_depth_5"] == 500 + 200
        assert depth["sell_depth_5"] == 300 + 150
        assert depth["liquidity_score"] == "medium"
        assert depth["confidence"] > 0
        assert depth["data_sources"] == ["gw2_commerce_listings"]
        assert depth["risk_reason"]

        # Arbitrage: buy 21600, sell 20000, fees 21600*0.05 + 20000*0.10 = 1080+2000=3080
        # Net profit = 20000 - 21600 - 3080 = -4680
        assert depth["net_profit"] < 0
        assert depth["arbitrage_viable"] is False

    def test_arbitrage_opportunity(self):
        """When buy price is higher than sell price after fees."""
        listing = {
            "item_id": 12345,
            "best_buy": 12000,
            "best_sell": 10000,
            "best_buy_qty": 100,
            "best_sell_qty": 50,
            "buys": [{"unit_price": 12000, "quantity": 100}],
            "sells": [{"unit_price": 10000, "quantity": 50}],
        }
        depth = analyze_depth(listing)
        # Gross profit: 12000 - 10000 = 2000
        # Fees: 10000*0.05 + 12000*0.10 = 500 + 1200 = 1700
        # Net: 2000 - 1700 = 300
        assert depth["gross_profit"] == 2000
        assert depth["net_profit"] == 300
        assert depth["arbitrage_viable"] is True

    def test_no_listings(self):
        listing = {
            "item_id": 0,
            "best_buy": 0,
            "best_buy_qty": 0,
            "best_sell": 0,
            "best_sell_qty": 0,
            "buys": [],
            "sells": [],
        }
        depth = analyze_depth(listing)
        assert depth["best_buy"] == 0
        assert depth["net_profit"] == 0
        assert depth["arbitrage_viable"] is False
        assert depth["liquidity_score"] == "illiquid"
        assert depth["confidence"] == 0.20
        assert "No visible" in depth["liquidity_reason"]

    def test_buy_depth_vs_sell_depth(self):
        listing = {
            "item_id": 1,
            "best_buy": 100,
            "best_buy_qty": 10000,
            "best_sell": 110,
            "best_sell_qty": 50,
            "buys": [{"unit_price": 100, "quantity": 10000}],
            "sells": [{"unit_price": 110, "quantity": 50}],
        }
        depth = analyze_depth(listing)
        assert depth["buy_depth_all"] == 10000
        assert depth["sell_depth_5"] == 50
        assert depth["arbitrage_viable"] is False  # spread too small after fees
