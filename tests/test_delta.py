"""Tests for the snapshot delta engine."""

from unittest.mock import AsyncMock, patch

import pytest

from gw2_progression.models import ItemHolding
from gw2_progression.services.delta_service import _build_item_key, _holdings_map, compare_snapshots


class TestHoldingsMap:
    def test_build_key(self):
        h = ItemHolding(item_id=19976, count=10, location_type="material_storage")
        key = _build_item_key(h)
        assert key == (19976, "material_storage")

    def test_holdings_map_basic(self):
        holdings = [
            ItemHolding(item_id=1, count=100, location_type="wallet", value_buy=100),
            ItemHolding(item_id=19976, count=10, location_type="material_storage", value_buy=200000),
        ]
        m = _holdings_map(holdings)
        assert len(m) == 2
        assert m[(1, "wallet")].count == 100


@pytest.mark.asyncio
class TestSnapshotDelta:
    async def test_snapshot_delta_total(self):
        from_raw = [
            ItemHolding(
                item_id=19976, count=100, location_type="material_storage", price_buy=20000, price_sell=21600, value_buy=2_000_000, value_sell=2_160_000, valuation_status="priced", tradable=True
            ),
            ItemHolding(item_id=1, count=50000, location_type="wallet", price_buy=1, price_sell=1, value_buy=50000, value_sell=50000, valuation_status="priced", tradable=True),
        ]
        to_raw = [
            ItemHolding(
                item_id=19976, count=150, location_type="material_storage", price_buy=22000, price_sell=24000, value_buy=3_300_000, value_sell=3_600_000, valuation_status="priced", tradable=True
            ),
            ItemHolding(item_id=1, count=45000, location_type="wallet", price_buy=1, price_sell=1, value_buy=45000, value_sell=45000, valuation_status="priced", tradable=True),
        ]

        with (
            patch("gw2_progression.services.delta_service.get_db", AsyncMock()),
            patch("gw2_progression.services.delta_service._load_snapshot_holdings", AsyncMock(side_effect=[from_raw, to_raw])),
        ):
            delta = await compare_snapshots("Player.1234", 1, 2)

        assert delta.total_delta_buy != 0
        assert len(delta.top_gainers) > 0 or len(delta.top_decliners) > 0

    async def test_item_delta_quantity_change(self):
        from_raw = [ItemHolding(item_id=19976, count=100, location_type="material_storage", price_buy=20000, value_buy=2_000_000, valuation_status="priced")]
        to_raw = [ItemHolding(item_id=19976, count=150, location_type="material_storage", price_buy=20000, value_buy=3_000_000, valuation_status="priced")]

        with (
            patch("gw2_progression.services.delta_service.get_db", AsyncMock()),
            patch("gw2_progression.services.delta_service._load_snapshot_holdings", AsyncMock(side_effect=[from_raw, to_raw])),
        ):
            delta = await compare_snapshots("Player.1234", 1, 2)

        assert len(delta.top_gainers) >= 1
        g = delta.top_gainers[0]
        assert g.primary_cause == "quantity_change"
        assert g.count_delta == 50
        assert g.value_delta == 1_000_000

    async def test_item_delta_price_change(self):
        from_raw = [ItemHolding(item_id=19976, count=100, location_type="material_storage", price_buy=20000, value_buy=2_000_000, valuation_status="priced")]
        to_raw = [ItemHolding(item_id=19976, count=100, location_type="material_storage", price_buy=25000, value_buy=2_500_000, valuation_status="priced")]

        with (
            patch("gw2_progression.services.delta_service.get_db", AsyncMock()),
            patch("gw2_progression.services.delta_service._load_snapshot_holdings", AsyncMock(side_effect=[from_raw, to_raw])),
        ):
            delta = await compare_snapshots("Player.1234", 1, 2)

        assert len(delta.top_gainers) >= 1
        g = delta.top_gainers[0]
        assert g.primary_cause == "price_change"
        assert g.price_delta == 5000
        assert g.value_delta == 500_000

    async def test_new_item_delta(self):
        from_raw: list[ItemHolding] = []
        to_raw = [ItemHolding(item_id=19976, count=10, location_type="material_storage", price_buy=20000, value_buy=200_000, valuation_status="priced")]

        with (
            patch("gw2_progression.services.delta_service.get_db", AsyncMock()),
            patch("gw2_progression.services.delta_service._load_snapshot_holdings", AsyncMock(side_effect=[from_raw, to_raw])),
        ):
            delta = await compare_snapshots("Player.1234", 1, 2)

        assert len(delta.top_gainers) >= 1
        assert delta.top_gainers[0].primary_cause == "new_item"

    async def test_removed_item_delta(self):
        from_raw = [ItemHolding(item_id=19976, count=10, location_type="material_storage", price_buy=20000, value_buy=200_000, valuation_status="priced")]
        to_raw: list[ItemHolding] = []

        with (
            patch("gw2_progression.services.delta_service.get_db", AsyncMock()),
            patch("gw2_progression.services.delta_service._load_snapshot_holdings", AsyncMock(side_effect=[from_raw, to_raw])),
        ):
            delta = await compare_snapshots("Player.1234", 1, 2)

        assert len(delta.top_decliners) >= 1
        assert delta.top_decliners[0].primary_cause == "removed_item"
        assert delta.top_decliners[0].value_delta < 0

    async def test_delta_location_breakdown(self):
        from_raw = [
            ItemHolding(item_id=1, count=100000, location_type="wallet", value_buy=100000, valuation_status="priced"),
            ItemHolding(item_id=19976, count=50, location_type="material_storage", value_buy=1_000_000, valuation_status="priced"),
        ]
        to_raw = [
            ItemHolding(item_id=1, count=80000, location_type="wallet", value_buy=80000, valuation_status="priced"),
            ItemHolding(item_id=19976, count=60, location_type="material_storage", value_buy=1_200_000, valuation_status="priced"),
        ]

        with (
            patch("gw2_progression.services.delta_service.get_db", AsyncMock()),
            patch("gw2_progression.services.delta_service._load_snapshot_holdings", AsyncMock(side_effect=[from_raw, to_raw])),
        ):
            delta = await compare_snapshots("Player.1234", 1, 2)

        assert delta.wallet_delta == -20000
        assert delta.material_delta == 200_000
