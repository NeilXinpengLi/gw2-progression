"""Tests for the crafting/recipe service."""

import pytest

from gw2_progression.models import CraftIngredient, CraftingResponse
from gw2_progression.services.recipe_service import _build_owned_map, _compute_craft_cost, _expand_ingredient


class TestOwnedMap:
    def test_build_owned_map_empty(self):
        result = _build_owned_map([], [], [], [])
        assert result == {}

    def test_build_owned_map_materials_only(self):
        mats = [{"id": 19976, "count": 250, "category": 5}]
        result = _build_owned_map(mats, [], [], [])
        assert result == {19976: 250}

    def test_build_owned_map_sums_across_sources(self):
        mats = [{"id": 19976, "count": 100, "category": 5}]
        bank = [{"id": 19976, "count": 50, "binding": None}]
        result = _build_owned_map(mats, bank, [], [])
        assert result == {19976: 150}


@pytest.mark.asyncio
class TestExpandIngredient:
    async def test_simple_base_ingredient(self):
        # depth >= MAX_RECIPE_DEPTH skips HTTP call
        ing = await _expand_ingredient(19720, 100, {}, {}, 3)
        assert ing.item_id == 19720
        assert ing.count == 100
        assert ing.owned == 0
        assert ing.missing == 100
        assert not ing.sub_tree

    async def test_owned_deduction(self):
        owned_map = {19720: 30}
        ing = await _expand_ingredient(19720, 100, owned_map, {}, 3)
        assert ing.owned == 30
        assert ing.missing == 70

    async def test_fully_owned(self):
        owned_map = {19720: 200}
        ing = await _expand_ingredient(19720, 100, owned_map, {}, 3)
        assert ing.owned == 100
        assert ing.missing == 0

    async def test_with_price(self):
        prices = {19720: (3000, 3500)}
        ing = await _expand_ingredient(19720, 10, {}, prices, 3)
        assert ing.buy_unit_price == 3500
        assert ing.total_buy_cost == 10 * 3500


class TestComputeCraftCost:
    async def test_simple_leaf(self):
        ing = CraftIngredient(item_id=1, count=10, missing=5, buy_unit_price=100, total_buy_cost=500)
        cost = await _compute_craft_cost(ing)
        assert cost == 500

    async def test_with_subtree(self):
        leaf1 = CraftIngredient(item_id=10, count=5, missing=5, buy_unit_price=200, total_buy_cost=1000)
        leaf2 = CraftIngredient(item_id=20, count=3, missing=3, buy_unit_price=300, total_buy_cost=900)
        parent = CraftIngredient(item_id=1, count=1, missing=1, sub_tree=[leaf1, leaf2])
        cost = await _compute_craft_cost(parent)
        assert cost == 1000 + 900


class TestCraftingResponse:
    def test_response_model(self):
        resp = CraftingResponse(target_item_id=1, target_count=1)
        assert resp.target_item_id == 1
        assert resp.total_buy_cost == 0

    def test_response_with_items(self):
        resp = CraftingResponse(
            target_item_id=19976,
            target_count=10,
            total_buy_cost=200000,
            missing_items=[{"item_id": 19720, "name": "Test", "missing": 5}],
            shopping_list=[{"item_id": 19720, "count": 5}],
        )
        assert len(resp.missing_items) == 1
        assert resp.missing_items[0]["item_id"] == 19720
