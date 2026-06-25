"""Tests for Goal-Driven Engine and Plan Iteration Engine."""


import pytest

from gw2_progression.models import GoalType, ParsedGoal, PlanAction, ProgressionPlan
from gw2_progression.services.goal_driven_engine import _score_action, revise_plan
from gw2_progression.services.plan_iteration_engine import apply_revision, classify_revision


class TestGoalDrivenEngine:

    def test_score_action_balanced(self):
        score = _score_action("SELL_ITEM", gold_gain=100000, time_cost_minutes=60, strategy="balanced")
        assert score != 0.0

    def test_score_action_gold_first(self):
        gold_score = _score_action("SELL_ITEM", gold_gain=100000, time_cost_minutes=60, strategy="gold_first")
        balanced_score = _score_action("SELL_ITEM", gold_gain=100000, time_cost_minutes=60, strategy="balanced")
        assert gold_score > balanced_score

    def test_score_action_cheapest(self):
        cheap_score = _score_action("BUY_ITEM", gold_gain=0, time_cost_minutes=60, strategy="cheapest")
        assert cheap_score is not None

    def test_generate_insight_legendary(self):
        from gw2_progression.services.goal_driven_engine import _generate_insight
        parsed = ParsedGoal(raw_text="Finish Bolt", goal_type=GoalType.FINISH_LEGENDARY, target_item_name="Bolt")
        state = {"wallet_gold": 500000}
        insight = _generate_insight(state, parsed, [], 67.0)
        assert "67%" in insight
        assert "Bolt" in insight

    def test_estimate_completion(self):
        from gw2_progression.services.goal_driven_engine import _estimate_completion
        parsed = ParsedGoal(raw_text="Finish Bolt", goal_type=GoalType.FINISH_LEGENDARY, target_item_id=46765)
        state = {"wallet_gold": 600000, "lvl80_count": 5}
        pct = _estimate_completion(state, parsed)
        assert pct > 0

    def test_estimate_completion_gold(self):
        from gw2_progression.services.goal_driven_engine import _estimate_completion
        parsed = ParsedGoal(raw_text="Make gold", goal_type=GoalType.MAKE_GOLD)
        state = {"wallet_gold": 50000}
        pct = _estimate_completion(state, parsed)
        assert pct > 0


class TestPlanIterationEngine:

    def test_classify_revision_strategy(self):
        types = classify_revision("Make it cheaper")
        assert "change_strategy" in types

    def test_classify_revision_cost(self):
        types = classify_revision("Too expensive, save gold")
        assert "reduce_cost" in types

    def test_classify_revision_exclusion(self):
        types = classify_revision("No WvW please")
        assert "exclude_activity" in types

    def test_classify_revision_time(self):
        types = classify_revision("I only have 2 hours")
        assert "change_time_budget" in types

    @pytest.mark.asyncio
    async def test_apply_revision_strategy_change(self):
        actions = [
            PlanAction(action_id="a1", plan_id="p1", action_type="SELL_ITEM", title="Sell items", reason="test", priority=1, status="pending"),
            PlanAction(action_id="a2", plan_id="p1", action_type="FARM_ACTIVITY", title="Farm gold", reason="test", priority=2, status="pending"),
        ]
        plan = ProgressionPlan(plan_id="p1", account_name="Test.1234", actions=actions, estimated_days=7)

        revised_plan, revision = await apply_revision(plan, "Make it cheaper")
        assert revision.previous_strategy == "balanced"
        assert revision.new_strategy == "cheapest"
        assert len(revision.delta_summary) > 0

    @pytest.mark.asyncio
    async def test_apply_revision_exclusion(self):
        actions = [
            PlanAction(action_id="a1", plan_id="p1", action_type="FARM_ACTIVITY", title="WvW farming", reason="Earn skirmish tickets", priority=1, status="pending"),
            PlanAction(action_id="a2", plan_id="p1", action_type="FARM_ACTIVITY", title="Fractal dailies", reason="T4 fractal gold", priority=2, status="pending"),
            PlanAction(action_id="a3", plan_id="p1", action_type="SELL_ITEM", title="Sell items", reason="test", priority=3, status="pending"),
        ]
        plan = ProgressionPlan(plan_id="p1", account_name="Test.1234", actions=actions, estimated_days=7)

        revised_plan, revision = await apply_revision(plan, "No WvW")
        assert len(revised_plan.actions) == 2
        assert not any("wvw" in a.title.lower() for a in revised_plan.actions)

    @pytest.mark.asyncio
    async def test_revise_plan_integration(self):
        actions = [
            PlanAction(action_id="a1", plan_id="p1", action_type="SELL_ITEM", title="Sell items", reason="test", reward_gold=100000, time_cost_minutes=30, priority=1, status="pending"),
        ]
        plan = ProgressionPlan(plan_id="p1", account_name="Test.1234", actions=actions, estimated_days=7)
        updated, delta_summary, changed = await revise_plan(plan, "Make it cheaper")
        assert updated.strategy == "cheapest"
        assert len(delta_summary) > 0


@pytest.mark.asyncio
class TestGoalInterpreterIntegration:

    async def test_full_flow(self):
        from gw2_progression.services.goal_interpreter import interpret_goal
        parsed = await interpret_goal("I want to finish Bolt in the cheapest way")
        assert parsed.goal_type == GoalType.FINISH_LEGENDARY
        assert parsed.target_item_id == 46765
        assert parsed.strategy == "cheapest"
        assert parsed.confidence > 0.6
