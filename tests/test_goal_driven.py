"""Tests for Goal-Driven Engine and Plan Iteration Engine."""


import json
from unittest.mock import AsyncMock, patch

import pytest

from gw2_progression.api.routes.goal_driven import _load_plan, _plan_store, _save_plan
from gw2_progression.models import GoalType, ParsedGoal, PlanAction, ProgressionPlan
from gw2_progression.services.goal_driven_engine import _score_action, generate_plan_from_goal, revise_plan
from gw2_progression.services.plan_iteration_engine import apply_revision, classify_revision


class _FakeRow:
    def __init__(self, **kw):
        self._data = kw

    def __getitem__(self, key):
        return self._data[key]

    def keys(self):
        return self._data.keys()


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

    @pytest.mark.asyncio
    async def test_generated_actions_include_confidence_metadata(self, monkeypatch):
        async def fake_extract_account_state(api_key: str) -> dict:
            return {
                "account_name": "Test.1234",
                "wallet_gold": 50000,
                "characters": [{"name": "Hero", "level": 80}],
                "lvl80_count": 1,
                "materials": [],
                "bank": [],
                "wallet_currencies": [],
                "contents": None,
            }

        monkeypatch.setattr("gw2_progression.services.goal_driven_engine._extract_account_state", fake_extract_account_state)

        parsed = ParsedGoal(
            raw_text="Make me gold this week",
            goal_type=GoalType.MAKE_GOLD,
            strategy="gold_first",
            confidence=0.84,
        )

        plan = await generate_plan_from_goal("fake-key", parsed)

        assert plan.actions
        assert all(action.plan_id == plan.plan_id for action in plan.actions)
        assert all(action.confidence > 0 for action in plan.actions)
        assert all(action.data_sources for action in plan.actions)
        assert all(action.risk_reason for action in plan.actions)
        assert any("gw2_commerce_prices" in action.data_sources for action in plan.actions if action.action_type == "BUY_ITEM")


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
    async def test_save_plan_persists_action_confidence_metadata(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.close = AsyncMock()
        action = PlanAction(
            action_id="a1",
            plan_id="p1",
            action_type="SELL_ITEM",
            title="Sell items",
            reason="test",
            confidence=0.72,
            data_sources=["gw2_account_materials", "gw2_commerce_prices"],
            risk_reason="Market execution may vary.",
        )
        plan = ProgressionPlan(plan_id="p1", account_name="Test.1234", actions=[action], estimated_days=1)

        with patch("gw2_progression.database.get_db", AsyncMock(return_value=db)):
            await _save_plan(plan)

        action_insert = db.execute.call_args_list[1].args
        assert "confidence, data_sources, risk_reason" in action_insert[0]
        assert action_insert[1][-3:] == (
            0.72,
            json.dumps(["gw2_account_materials", "gw2_commerce_prices"]),
            "Market execution may vary.",
        )

    @pytest.mark.asyncio
    async def test_load_plan_restores_action_confidence_metadata(self):
        _plan_store.clear()
        plan_cursor = AsyncMock()
        plan_cursor.fetchone = AsyncMock(
            return_value=_FakeRow(
                plan_id="p1",
                goal_id="",
                account_name="Test.1234",
                strategy="balanced",
                total_cost_copper=0,
                estimated_days=1,
                completion_percent=10.0,
                status="active",
                insight="test",
                created_at="now",
            ),
        )
        actions_cursor = AsyncMock()
        actions_cursor.fetchall = AsyncMock(
            return_value=[
                _FakeRow(
                    action_id="a1",
                    plan_id="p1",
                    action_type="SELL_ITEM",
                    title="Sell items",
                    reason="test",
                    reward_gold=0,
                    cost_gold=0,
                    time_cost_minutes=0,
                    score=0.0,
                    priority=1,
                    status="pending",
                    tab="value",
                    item_id=0,
                    day_index=0,
                    confidence=0.72,
                    data_sources='["gw2_account_materials", "gw2_commerce_prices"]',
                    risk_reason="Market execution may vary.",
                ),
            ],
        )
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[plan_cursor, actions_cursor])
        db.close = AsyncMock()

        with patch("gw2_progression.database.get_db", AsyncMock(return_value=db)):
            plan = await _load_plan("p1")

        assert plan is not None
        assert plan.actions[0].confidence == 0.72
        assert plan.actions[0].data_sources == ["gw2_account_materials", "gw2_commerce_prices"]
        assert plan.actions[0].risk_reason == "Market execution may vary."


@pytest.mark.asyncio
class TestGoalInterpreterIntegration:

    async def test_full_flow(self):
        from gw2_progression.services.goal_interpreter import interpret_goal
        parsed = await interpret_goal("I want to finish Bolt in the cheapest way")
        assert parsed.goal_type == GoalType.FINISH_LEGENDARY
        assert parsed.target_item_id == 46765
        assert parsed.strategy == "cheapest"
        assert parsed.confidence > 0.6
