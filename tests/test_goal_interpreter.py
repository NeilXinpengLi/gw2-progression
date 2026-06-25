"""Tests for the Goal Interpreter module."""

import pytest

from gw2_progression.models import GoalType
from gw2_progression.services.goal_interpreter import generate_alternatives, interpret_goal


@pytest.mark.asyncio
class TestGoalInterpreter:

    async def test_interpret_empty(self):
        result = await interpret_goal("")
        assert result.confidence == 0.0

    async def test_interpret_finish_legendary(self):
        result = await interpret_goal("I want to finish Bolt")
        assert result.goal_type == GoalType.FINISH_LEGENDARY
        assert result.target_item_id == 46765
        assert result.target_item_name == "Bolt"
        assert result.confidence > 0.5

    async def test_interpret_make_gold(self):
        result = await interpret_goal("I want to make gold this week")
        assert result.goal_type == GoalType.MAKE_GOLD

    async def test_interpret_prepare_build(self):
        result = await interpret_goal("I need a fractal-ready build")
        assert result.goal_type == GoalType.PREPARE_BUILD
        assert result.game_mode == "fractal"

    async def test_interpret_weekly_plan(self):
        result = await interpret_goal("Plan my week")
        assert result.goal_type == GoalType.WEEKLY_PLAN

    async def test_interpret_cheapest_strategy(self):
        result = await interpret_goal("Finish Bolt cheaply")
        assert result.strategy == "cheapest"

    async def test_interpret_time_budget(self):
        result = await interpret_goal("I only have 1 hour a day")
        assert result.time_budget_minutes == 60

    async def test_interpret_inventory(self):
        result = await interpret_goal("I want to clean my inventory")
        assert result.goal_type == GoalType.OPTIMIZE_INVENTORY

    async def test_interpret_twilight(self):
        result = await interpret_goal("I want to make Twilight")
        assert result.target_item_id == 30684
        assert "Twilight" in result.target_item_name

    async def test_interpret_exclusions(self):
        result = await interpret_goal("Make gold, no WvW")
        assert result.goal_type == GoalType.MAKE_GOLD

    async def test_generate_alternatives(self):
        parsed = await interpret_goal("I want to finish Bolt")
        alts = await generate_alternatives(parsed)
        assert len(alts) >= 3
        assert alts[0].strategy == "balanced"
        # Should have cheapest and fastest alternatives
        strategies = [a.strategy for a in alts]
        assert any(s == "cheapest" for s in strategies)
        assert any(s == "fastest" for s in strategies)
