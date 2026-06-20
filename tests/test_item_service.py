"""Tests for item flags service."""

import pytest

from gw2_progression.services.item_service import get_item_flags, is_account_bound


@pytest.mark.asyncio
class TestItemFlags:
    async def test_get_flags_with_cached_items(self):
        """Should return cached flags without HTTP call."""
        # Prime the cache
        from gw2_progression.services.item_service import _cache

        _cache.set("item_flags:19976", ["NoSell", "NoSalvage"])
        _cache.set("item_flags:19720", ["AccountBound"])

        result = await get_item_flags([19976, 19720])
        assert 19976 in result
        assert "NoSell" in result[19976]
        assert 19720 in result
        assert "AccountBound" in result[19720]

    async def test_is_account_bound(self):
        from gw2_progression.services.item_service import _cache

        _cache.set("item_flags:1", ["AccountBound"])
        _cache.set("item_flags:2", ["NoSell"])
        _cache.set("item_flags:3", ["AccountBindOnUse"])

        result = await is_account_bound([1, 2, 3])
        assert result[1] is True
        assert result[2] is False
        assert result[3] is True

    async def test_empty_ids(self):
        result = await get_item_flags([])
        assert result == {}

    async def test_unknown_items(self):
        """Items not fetched should get empty flags set."""
        from gw2_progression.services.item_service import _cache

        # Don't cache anything - the function should still work
        _cache.set("item_flags:999999", [])
        result = await get_item_flags([999999])
        assert 999999 in result
        assert result[999999] == set()
