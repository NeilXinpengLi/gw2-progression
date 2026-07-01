import pytest

from gw2_progression.models import GoalType, ParsedGoal, PlanAction, ProgressionPlan
from gw2_progression.services.ai_lab_adapter import enhance_plan_with_ai_lab


@pytest.mark.asyncio
async def test_ai_lab_adapter_enhances_plan_without_reordering_actions():
    parsed = ParsedGoal(
        raw_text="Craft Mystic Coin",
        goal_type=GoalType.CRAFT_ITEM,
        gold_budget_copper=100,
        confidence=0.9,
    )
    plan = ProgressionPlan(
        plan_id="p1",
        account_name="Player.1234",
        estimated_days=2,
        total_cost_copper=1000,
        insight="Craft the item.",
        actions=[
            PlanAction(
                action_id="a1",
                plan_id="p1",
                action_type="BUY_ITEM",
                title="Buy one material",
                cost_gold=1000,
                time_cost_minutes=15,
                priority=1,
                confidence=0.7,
                risk_reason="Market prices can move.",
            )
        ],
    )

    enhanced, assessment = await enhance_plan_with_ai_lab(plan, parsed, {"wallet_gold": 500})

    assert [action.action_id for action in enhanced.actions] == ["a1"]
    assert "ai_lab_adapter:v1" in enhanced.actions[0].data_sources
    assert "[AI Lab]" in enhanced.actions[0].risk_reason
    assert "AI Lab check" in enhanced.insight
    assert assessment.status == "enhanced"
    assert assessment.validation["warning_count"] >= 1
    assert assessment.simulation["affordable_with_wallet"] is False
