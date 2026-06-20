"""Tests for the item search service."""

from unittest.mock import AsyncMock, patch

import pytest

from gw2_progression.models import ItemHolding
from gw2_progression.services.item_search_service import get_filtered_items, get_item_detail


class TestItemDetail:
    @pytest.mark.asyncio
    async def test_item_detail_basic(self):
        with (
            patch("gw2_progression.services.item_search_service.get_db", AsyncMock()),
            patch(
                "gw2_progression.services.item_search_service.search_latest_holdings",
                AsyncMock(
                    return_value=[
                        ItemHolding(
                            item_id=19976,
                            count=100,
                            location_type="material_storage",
                            location_ref="5",
                            price_buy=20000,
                            price_sell=21600,
                            value_buy=2_000_000,
                            value_sell=2_160_000,
                            valuation_status="priced",
                            tradable=True,
                        ),
                        ItemHolding(
                            item_id=19976,
                            count=50,
                            location_type="bank",
                            location_ref="0",
                            price_buy=20000,
                            price_sell=21600,
                            value_buy=1_000_000,
                            value_sell=1_080_000,
                            valuation_status="priced",
                            tradable=True,
                        ),
                    ]
                ),
            ),
        ):
            detail = await get_item_detail("Player.1234", 19976)

        assert detail["item_id"] == 19976
        assert detail["total_count"] == 150
        assert detail["total_value_buy"] == 3_000_000
        assert "material_storage" in detail["locations"]
        assert "bank" in detail["locations"]

    @pytest.mark.asyncio
    async def test_item_detail_empty(self):
        with (
            patch("gw2_progression.services.item_search_service.get_db", AsyncMock()),
            patch("gw2_progression.services.item_search_service.search_latest_holdings", AsyncMock(return_value=[])),
        ):
            detail = await get_item_detail("Player.1234", 99999)
        assert detail["item_id"] == 99999
        assert detail["total_count"] == 0
        assert detail["valuation_status"] == "unknown"


class TestFilteredItems:
    @pytest.mark.asyncio
    async def test_high_value_filter(self):
        holdings = [
            ItemHolding(item_id=1, count=100, location_type="wallet", value_buy=100, valuation_status="priced"),
            ItemHolding(item_id=19976, count=250, location_type="material_storage", value_buy=5_000_000, valuation_status="priced"),
            ItemHolding(item_id=19720, count=100, location_type="bank", value_buy=300_000, valuation_status="priced"),
        ]
        with (
            patch("gw2_progression.services.item_search_service.get_db", AsyncMock()),
            patch("gw2_progression.services.item_search_service.search_latest_holdings", AsyncMock(return_value=holdings)),
        ):
            items = await get_filtered_items("Player.1234", "high_value", limit=5)
        # Should be sorted by value_buy descending
        assert len(items) == 3
        assert items[0].item_id == 19976

    @pytest.mark.asyncio
    async def test_unpriced_filter(self):
        with (
            patch("gw2_progression.services.item_search_service.get_db", AsyncMock()),
            patch(
                "gw2_progression.services.item_search_service.search_latest_holdings",
                AsyncMock(
                    return_value=[
                        ItemHolding(item_id=77777, count=5, location_type="bank", valuation_status="unpriced"),
                    ]
                ),
            ),
        ):
            items = await get_filtered_items("Player.1234", "unpriced", limit=10)
        assert len(items) == 1
        assert items[0].valuation_status == "unpriced"

    @pytest.mark.asyncio
    async def test_account_bound_filter(self):
        with (
            patch("gw2_progression.services.item_search_service.get_db", AsyncMock()),
            patch(
                "gw2_progression.services.item_search_service.search_latest_holdings",
                AsyncMock(
                    return_value=[
                        ItemHolding(item_id=99999, count=1, location_type="bank", valuation_status="account_bound", binding_status="AccountBound"),
                    ]
                ),
            ),
        ):
            items = await get_filtered_items("Player.1234", "account_bound", limit=10)
        assert len(items) == 1
        assert items[0].valuation_status == "account_bound"
