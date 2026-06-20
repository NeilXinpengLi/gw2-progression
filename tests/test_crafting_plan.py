"""Tests for the enhanced crafting plan service."""

from unittest.mock import AsyncMock, patch

import pytest

from gw2_progression.models import CraftingPlanLine, CraftingPlanResult


class TestCraftingPlanModels:
    def test_plan_line_defaults(self):
        line = CraftingPlanLine(item_id=19976, required_count=10)
        assert line.missing_count == 0
        assert line.source == "missing"

    def test_plan_result_defaults(self):
        plan = CraftingPlanResult(target_item_id=19976, target_count=1)
        assert plan.total_market_buy_cost == 0
        assert plan.craft_vs_buy_delta == 0
        assert plan.lines == []

    def test_plan_with_owned_materials(self):
        line = CraftingPlanLine(
            item_id=19720,
            required_count=100,
            owned_count=30,
            used_owned_count=30,
            missing_count=70,
            unit_buy_price=3000,
            missing_buy_cost=210000,
            source="missing",
        )
        plan = CraftingPlanResult(
            target_item_id=19976,
            target_count=1,
            total_market_buy_cost=210000,
            owned_material_value_used=90000,
            missing_material_cost=210000,
            direct_buy_price=500000,
            craft_vs_buy_delta=210000 - 500000,
            lines=[line],
        )
        assert plan.craft_vs_buy_delta == -290000
        assert len(plan.lines) == 1
        assert plan.lines[0].item_id == 19720


@pytest.mark.asyncio
class TestCreatePlan:
    async def test_create_plan_basic(self):
        from gw2_progression.services.crafting_plan_service import create_plan

        with (
            patch("gw2_progression.services.crafting_plan_service.fetch_prices", AsyncMock(return_value={})),
            patch("gw2_progression.services.crafting_plan_service.calculate", AsyncMock()) as mock_calc,
        ):
            mock_calc.return_value.shopping_list = []
            mock_calc.return_value.missing_items = []
            mock_calc.return_value.total_buy_cost = 0
            mock_calc.return_value.total_craft_cost = 0
            mock_calc.return_value.owned_used = 0

            plan = await create_plan("fake-key", 19976, 1, True)

        assert plan.target_item_id == 19976
        assert plan.target_count == 1
        assert isinstance(plan.plan_id, str)
        assert len(plan.plan_id) > 0

    async def test_create_plan_with_owned(self):
        from gw2_progression.services.crafting_plan_service import create_plan

        with (
            patch("gw2_progression.services.crafting_plan_service.fetch_prices", AsyncMock(return_value={})),
            patch("gw2_progression.services.crafting_plan_service.calculate", AsyncMock()) as mock_calc,
        ):
            mock_calc.return_value.shopping_list = [
                {"item_id": 19720, "count": 100, "owned": 30, "missing": 70, "unit_price": 3000, "total": 210000, "needed": 100},
            ]
            mock_calc.return_value.missing_items = []
            mock_calc.return_value.total_buy_cost = 210000
            mock_calc.return_value.total_craft_cost = 210000
            mock_calc.return_value.owned_used = 30

            plan = await create_plan("fake-key", 19976, 1, True)

        assert len(plan.lines) == 1
        assert plan.lines[0].item_id == 19720
        assert plan.lines[0].missing_count == 70
        assert plan.missing_material_cost > 0
