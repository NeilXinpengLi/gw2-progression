import pytest

from gw2_progression import database
from gw2_progression.models import GoalType, ParsedGoal, PlanAction, ProgressionPlan
from gw2_progression.ontology import OntologyKernel
from gw2_progression.services.ai_lab_adapter import enhance_plan_with_ai_lab


@pytest.mark.asyncio
async def test_ai_lab_adapter_enhances_plan_without_reordering_actions(tmp_path, monkeypatch):
    db_path = tmp_path / "ai-lab-adapter.db"
    monkeypatch.setattr(database, "_TEST_DB_URL", str(db_path))
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
    assert assessment.validation["rule_engine_v2"]["rule_count"] == 1
    assert assessment.validation["lifecycle"]
    assert assessment.simulation["affordable_with_wallet"] is False
    assert assessment.simulation["lifecycle"]["trajectory_length"] >= 1
    assert "rule_engine_v2:validation_adapter" in assessment.evidence_sources
    assert "lifecycle:simulation_adapter" in assessment.evidence_sources
    assert assessment.ontology_evidence["persisted"] is True
    assert assessment.ontology_evidence["evidence_id"] == "plan-assessment:p1"
    assert "ontology_runtime:plan_assessment_evidence" in assessment.evidence_sources

    restored = OntologyKernel(tenant_id="goal-plan:Player.1234", load_persisted=True)
    snapshot = restored.snapshot()
    assert "plan-assessment:p1" in snapshot["state"]["entities"]
    assert restored.replay_persisted()["deterministic"] is True
