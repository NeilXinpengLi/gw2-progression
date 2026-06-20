"""Tests for holdings normalization, valuation engine, and price service."""

from unittest.mock import AsyncMock, patch

import pytest

from gw2_progression.models import ItemHolding
from gw2_progression.services.holdings_service import (
    extract_bank_holdings,
    extract_character_holdings,
    extract_material_holdings,
    extract_shared_inventory_holdings,
    extract_tradingpost_holdings,
    extract_wallet_holdings,
)
from gw2_progression.services.price_service import _get_cached_price, _set_cached_price
from gw2_progression.services.valuation_service import (
    apply_prices,
    compute_breakdown,
    compute_summary,
    compute_top_items,
)

# ─── Holdings Normalization Tests ───


class TestHoldingsNormalization:
    def test_wallet_gold_only(self):
        wallet = [{"id": 1, "value": 123456}]
        result = extract_wallet_holdings(wallet)
        assert len(result) == 1
        assert result[0].item_id == 1
        assert result[0].count == 123456
        assert result[0].location_type == "wallet"

    def test_wallet_ignores_non_gold(self):
        wallet = [{"id": 1, "value": 50000}, {"id": 2, "value": 100}]
        result = extract_wallet_holdings(wallet)
        assert len(result) == 1
        assert result[0].item_id == 1

    def test_wallet_empty(self):
        assert extract_wallet_holdings([]) == []
        assert extract_wallet_holdings(None) == []

    def test_materials_extraction(self):
        mats = [
            {"id": 19976, "count": 250, "category": 5},
            {"id": 19720, "count": 750, "category": 7},
        ]
        result = extract_material_holdings(mats)
        assert len(result) == 2
        assert result[0].item_id == 19976
        assert result[0].count == 250
        assert result[0].location_type == "material_storage"
        assert result[0].location_ref == "5"

    def test_materials_skips_zero_count(self):
        mats = [{"id": 19976, "count": 0, "category": 5}]
        result = extract_material_holdings(mats)
        assert len(result) == 0

    def test_bank_extraction(self):
        bank = [
            {"id": 123, "count": 5, "binding": None},
            None,
            {"id": 456, "count": 1, "binding": "AccountBound"},
        ]
        result = extract_bank_holdings(bank)
        assert len(result) == 2
        assert result[0].item_id == 123
        assert result[0].count == 5
        assert result[0].tradable is True
        assert result[0].binding_status is None
        assert result[1].item_id == 456
        assert result[1].tradable is False
        assert result[1].binding_status == "AccountBound"

    def test_character_holdings(self):
        chars = [
            {
                "name": "MyChar",
                "bags": [
                    {
                        "inventory": [
                            {"id": 789, "count": 2, "binding": None},
                            None,
                        ],
                    },
                ],
            },
        ]
        result = extract_character_holdings(chars)
        assert len(result) == 1
        assert result[0].item_id == 789
        assert result[0].count == 2
        assert result[0].location_type == "character"
        assert "MyChar" in result[0].location_ref

    def test_shared_inventory(self):
        shared = [
            {"id": 111, "count": 1, "binding": None},
            None,
            {"id": 222, "count": 10, "binding": "Soulbound"},
        ]
        result = extract_shared_inventory_holdings(shared)
        assert len(result) == 2
        assert result[1].item_id == 222
        assert result[1].tradable is False

    def test_tradingpost_holdings(self):
        buys = [{"item_id": 555, "quantity": 5, "price": 10000}]
        sells = [{"item_id": 666, "quantity": 3, "price": 20000}]
        result = extract_tradingpost_holdings(buys, sells)
        assert len(result) == 2
        tp_buy = [h for h in result if h.location_ref == "buy_order"][0]
        tp_sell = [h for h in result if h.location_ref == "sell_order"][0]
        assert tp_buy.item_id == 555
        assert tp_buy.value_buy == 5 * 10000
        assert tp_sell.item_id == 666
        assert tp_sell.value_sell == 3 * 20000

    def test_single_item_aggregation(self):
        """Multiple holdings of same item across locations are NOT merged."""
        mats = [{"id": 19976, "count": 100, "category": 5}]
        bank = [{"id": 19976, "count": 50, "binding": None}]
        m = extract_material_holdings(mats)
        b = extract_bank_holdings(bank)
        assert len(m) == 1
        assert len(b) == 1
        assert m[0].item_id == b[0].item_id


# ─── Price Cache Tests ───


class TestPriceCache:
    def test_cache_set_and_get(self):
        from gw2_progression.models import PriceData

        pd = PriceData(item_id=42, buy_unit_price=100, sell_unit_price=200)
        _set_cached_price(pd)
        cached = _get_cached_price(42)
        assert cached is not None
        assert cached.buy_unit_price == 100
        assert cached.sell_unit_price == 200

    def test_cache_miss(self):
        assert _get_cached_price(999999) is None


# ─── Valuation Engine Tests ───


class TestValuationEngine:
    def _make_holdings(self, overrides=None):
        holdings = [
            ItemHolding(item_id=1, count=50000, location_type="wallet", valuation_status="pending"),
            ItemHolding(item_id=19976, count=250, location_type="material_storage", location_ref="5", valuation_status="pending"),
            ItemHolding(item_id=19720, count=100, location_type="material_storage", location_ref="7", valuation_status="pending"),
            ItemHolding(item_id=12345, count=5, location_type="bank", valuation_status="pending"),
            ItemHolding(
                item_id=99999,
                count=1,
                location_type="bank",  # noqa: E501
                binding_status="AccountBound",
                tradable=False,
                valuation_status="pending",
            ),
        ]
        if overrides:
            for k, v in overrides.items():
                setattr(holdings[0], k, v)
        return holdings

    def test_apply_prices_materials_and_wallet(self):
        holdings = self._make_holdings()
        prices = {
            19976: (20000, 21600),
            19720: (3000, 3500),
            12345: (50000, 55000),
        }
        enriched, warnings = apply_prices(holdings, prices)

        wallet = [h for h in enriched if h.location_type == "wallet"][0]
        assert wallet.valuation_status == "priced"
        assert wallet.value_buy == 50000
        assert wallet.value_sell == 50000

        mystic = [h for h in enriched if h.item_id == 19976][0]
        assert mystic.valuation_status == "priced"
        assert mystic.value_buy == 250 * 20000
        assert mystic.value_sell == 250 * 21600

        bound = [h for h in enriched if h.item_id == 99999][0]
        assert bound.valuation_status == "account_bound"
        assert bound.value_buy == 0

    def test_unpriced_item_handling(self):
        holdings = [
            ItemHolding(item_id=1, count=100, location_type="wallet", valuation_status="pending"),
            ItemHolding(item_id=77777, count=10, location_type="material_storage", valuation_status="pending"),
        ]
        prices = {}  # no prices fetched
        enriched, warnings = apply_prices(holdings, prices)
        unpriced = [h for h in enriched if h.valuation_status == "unpriced"]
        assert len(unpriced) == 1
        assert unpriced[0].item_id == 77777
        assert any(w.warning_type == "unpriced" for w in warnings)

    def test_compute_summary(self):
        holdings = [
            ItemHolding(item_id=1, count=10000, location_type="wallet", valuation_status="priced", value_buy=10000, value_sell=10000),
            ItemHolding(item_id=19976, count=250, location_type="material_storage", valuation_status="priced", value_buy=5_000_000, value_sell=5_400_000),
            ItemHolding(item_id=19720, count=100, location_type="bank", valuation_status="priced", value_buy=300_000, value_sell=350_000),
            ItemHolding(item_id=99999, count=1, location_type="material_storage", binding_status="AccountBound", valuation_status="account_bound", value_buy=0, value_sell=0),
            ItemHolding(item_id=88888, count=5, location_type="bank", valuation_status="unpriced", value_buy=0, value_sell=0),
        ]
        summary = compute_summary(holdings)
        assert summary.wallet_value == 10000
        assert summary.material_value_buy == 5_000_000
        assert summary.total_value_buy == 5_310_000
        assert summary.total_value_sell == 5_760_000
        assert summary.net_sell_value == int(5_760_000 * 0.85)
        assert summary.priced_item_count == 3
        assert summary.unpriced_item_count == 1
        assert summary.account_bound_count == 1

    def test_compute_breakdown(self):
        holdings = self._make_holdings()
        prices = {19976: (20000, 21600), 19720: (3000, 3500), 12345: (50000, 55000)}
        enriched, _ = apply_prices(holdings, prices)
        summary = compute_summary(enriched)
        breakdown = compute_breakdown(summary, enriched)

        assert len(breakdown.by_location) > 0
        total_pct = sum(b.percentage for b in breakdown.by_location if b.value_buy > 0)
        assert abs(total_pct - 100.0) < 0.1 or total_pct == 0  # rounding tolerance

        statuses = {s.status: s for s in breakdown.by_status}
        assert "priced" in statuses
        assert "unpriced" in statuses
        assert "account_bound" in statuses

    def test_top_items(self):
        holdings = [
            ItemHolding(item_id=1, count=10000, location_type="wallet", valuation_status="priced", value_buy=10000, value_sell=10000),
            ItemHolding(item_id=19976, count=250, location_type="material_storage", valuation_status="priced", value_buy=5_000_000, value_sell=5_400_000),
            ItemHolding(item_id=19720, count=100, location_type="bank", valuation_status="priced", value_buy=300_000, value_sell=350_000),
        ]
        top = compute_top_items(holdings, limit=5)
        assert len(top) == 2  # wallet excluded
        assert top[0].item_id == 19976
        assert top[0].value_buy == 5_000_000

    def test_top_items_limit(self):
        holdings = [
            ItemHolding(item_id=1, count=100, location_type="wallet", valuation_status="priced", value_buy=100, value_sell=100),
            ItemHolding(item_id=10, count=10, location_type="bank", valuation_status="priced", value_buy=1000, value_sell=1100),
            ItemHolding(item_id=20, count=10, location_type="bank", valuation_status="priced", value_buy=2000, value_sell=2200),
        ]
        top = compute_top_items(holdings, limit=1)
        assert len(top) == 1

    def test_zero_prices_handled(self):
        """Items with zero for both buy and sell price should be unpriced."""
        holdings = [
            ItemHolding(item_id=1, count=100, location_type="wallet", valuation_status="pending"),
            ItemHolding(item_id=77777, count=10, location_type="material_storage", valuation_status="pending"),
        ]
        prices = {77777: (0, 0)}
        enriched, warnings = apply_prices(holdings, prices)
        unpriced = [h for h in enriched if h.valuation_status == "unpriced"]
        assert len(unpriced) == 1
        assert any(w.warning_type == "no_price" for w in warnings)


# ─── Valuation Route Tests ───


class TestValuationRoute:
    TOKENINFO = {"name": "TestKey", "id": "abc", "permissions": ["account", "inventories", "wallet", "tradingpost", "characters"]}
    ACCOUNT = {
        "name": "Player.1234",
        "world": 1001,
        "created": "2022-01-01T00:00:00Z",
        "age": 3600,
        "fractal_level": 10,
        "daily_ap": 100,
        "monthly_ap": 0,
        "wvw_rank": 1,
        "guilds": [],
    }

    @pytest.mark.asyncio
    async def test_value_analyze_endpoint_integration(self):
        """Test the full value/analyze pipeline with mocked GW2 API."""
        from gw2_progression.services.snapshot_service import run_full_analysis

        BASE = "gw2_progression.analyzer"
        stubs = {
            "fetch_account": self.ACCOUNT,
            "fetch_characters": [],
            "fetch_wallet": [{"id": 1, "value": 123456}],
            "fetch_bank": [{"id": 19976, "count": 10, "binding": None}],
            "fetch_materials": [{"id": 19720, "count": 100, "category": 7}],
            "fetch_inventory": [None],
            "fetch_achievements": [],
            "fetch_masteries": [],
            "fetch_mastery_points": {},
            "fetch_builds": [],
            "fetch_guilds": [],
            "fetch_pvp_stats": {},
            "fetch_pvp_games": [],
            "fetch_pvp_standings": [],
            "fetch_tradingpost_current_buys": [],
            "fetch_tradingpost_current_sells": [],
            "fetch_unlocked_skins": [],
            "fetch_unlocked_dyes": [],
            "fetch_unlocked_minis": [],
            "fetch_unlocked_finishers": [],
            "fetch_wvw_stats": {},
        }

        from contextlib import ExitStack

        stack = ExitStack()
        stack.enter_context(patch(f"{BASE}.fetch_tokeninfo", AsyncMock(return_value=self.TOKENINFO)))
        for fn, val in stubs.items():
            mock = val if isinstance(val, AsyncMock) else AsyncMock(return_value=val)
            stack.enter_context(patch(f"{BASE}.{fn}", mock))

        mock_prices = {
            19976: type("PriceData", (), {"buy_unit_price": 20000, "sell_unit_price": 21600, "buy_quantity": 5000, "sell_quantity": 3000})(),
            19720: type("PriceData", (), {"buy_unit_price": 3000, "sell_unit_price": 3500, "buy_quantity": 2000, "sell_quantity": 1500})(),
        }
        with (
            patch("gw2_progression.services.snapshot_service.fetch_prices", AsyncMock(return_value=mock_prices)),
            patch("gw2_progression.services.snapshot_service.get_db", AsyncMock()),
        ):
            with stack:
                result = await run_full_analysis("fake-key-12345678")

        assert result.summary.total_value_buy > 0
        assert result.summary.wallet_value == 123456
        assert result.summary.priced_item_count >= 2
        assert len(result.top_items) > 0
        assert len(result.breakdown.by_location) > 0
