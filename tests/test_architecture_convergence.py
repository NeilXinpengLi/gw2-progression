from fastapi import FastAPI

from gw2_progression.api.governance import (
    API_ROUTE_GOVERNANCE,
    ApiCategory,
    governance_release_report,
    governance_snapshot_hash,
    include_governed_routers,
    production_exposure_violations,
)
from gw2_progression.api.main import ROUTER_BINDINGS
from gw2_progression.architecture_contracts import (
    data_source_governance_contract,
    data_source_governance_snapshot,
    decision_owner_contract,
    validate_evidence_envelope,
)
from gw2_progression.models import GoalType, ParsedGoal, PlanAction, ProgressionPlan
from gw2_progression.services.plan_learning_service import (
    build_offline_candidate_dataset,
    evaluate_offline_promotion_gate,
    export_plan_outcome_events,
    publish_offline_plan_events,
)


def test_production_exposure_report_flags_ai_lab_when_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ENABLE_EXPERIMENTAL_ROUTES", "true")
    monkeypatch.setenv("ENABLE_AI_LAB_ROUTES", "true")

    violations = production_exposure_violations()

    assert violations
    assert {row["category"] for row in violations} == {ApiCategory.AI_LAB.value}
    assert any(row["key"] == "expert_ai" for row in violations)


def test_governance_release_report_has_stable_hash(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ENABLE_EXPERIMENTAL_ROUTES", "false")
    monkeypatch.setenv("ENABLE_AI_LAB_ROUTES", "false")

    report = governance_release_report()

    assert report["snapshot_hash"] == governance_snapshot_hash(report["routes"])
    assert report["production_exposure_violations"] == []
    assert report["release_status"] == "pass"
    assert report["route_count"] == len(report["routes"])


def test_router_snapshot_can_be_used_as_deployment_gate(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ENABLE_EXPERIMENTAL_ROUTES", "false")
    monkeypatch.setenv("ENABLE_AI_LAB_ROUTES", "false")

    app = FastAPI()
    snapshot = include_governed_routers(app, ROUTER_BINDINGS)
    enabled_ai_lab = [row for row in snapshot if row["category"] == ApiCategory.AI_LAB.value and row["enabled"] == "true"]

    assert enabled_ai_lab == []
    assert governance_snapshot_hash(snapshot)


def test_decision_owner_contract_keeps_core_product_from_experimental_owners():
    contract = decision_owner_contract()

    assert contract["product_plan_owner"].endswith("goal_driven_engine.generate_plan_from_goal")
    assert contract["evidence_spine"] == "Ontology Runtime"
    assert "expert_ai" in API_ROUTE_GOVERNANCE
    assert set(contract["ai_lab_route_keys"]).issuperset({"expert_ai", "cognitive_os", "rule_v2", "lifecycle"})


def test_data_source_governance_contract_makes_data_mesh_authoritative():
    contract = data_source_governance_contract()
    snapshot = data_source_governance_snapshot()

    assert contract["source_identity_owner"] == "Data Mesh"
    assert contract["source_confidence_owner"] == "Data Mesh"
    assert contract["fetch_pipeline_owner"] == "Data Acquisition"
    assert contract["canonical_registry"].endswith("data_mesh.sources.registry.SourceRegistry")
    assert snapshot["mesh_source_count"] > 0
    assert snapshot["acquisition_source_count"] > 0


def test_plan_outcome_export_is_anonymized_and_offline_only():
    parsed = ParsedGoal(raw_text="Make gold", goal_type=GoalType.MAKE_GOLD, confidence=0.8)
    plan = ProgressionPlan(
        plan_id="plan-1",
        account_name="Visible.1234",
        actions=[
            PlanAction(
                action_id="a1",
                plan_id="plan-1",
                action_type="SELL_ITEM",
                title="Sell item",
                confidence=0.7,
                data_sources=["gw2_commerce_prices"],
            )
        ],
    )

    events = export_plan_outcome_events(plan, parsed, {"a1": {"success": True, "reward": 42}})
    dataset = build_offline_candidate_dataset(plan, parsed, {"a1": {"success": True, "reward": 42}})

    assert events[0]["decision"]["action_id"] == "a1"
    assert "Visible.1234" not in str(events)
    assert dataset["account_hash"]
    assert dataset["account_hash"] not in {"Visible.1234", ""}
    assert dataset["promotion_gate"]["mode"] == "offline_only"
    assert dataset["promotion_gate"]["can_block_product_flow"] is False
    assert dataset["evidence"]["schema_version"] == "evidence.v1"
    assert validate_evidence_envelope(dataset["evidence"])["valid"] is True


def test_offline_promotion_gate_requires_evidence_replay_and_improvement():
    parsed = ParsedGoal(raw_text="Make gold", goal_type=GoalType.MAKE_GOLD, confidence=0.8)
    plan = ProgressionPlan(
        plan_id="plan-2",
        account_name="Visible.1234",
        actions=[PlanAction(action_id="a1", plan_id="plan-2", action_type="SELL_ITEM", confidence=0.7)],
    )
    dataset = build_offline_candidate_dataset(plan, parsed, {"a1": {"success": True, "reward": 42, "status": "observed"}})

    blocked = evaluate_offline_promotion_gate(dataset, baseline_score=0.7, candidate_score=0.71, ontology_replay={"deterministic": True})
    ready = evaluate_offline_promotion_gate(dataset, baseline_score=0.7, candidate_score=0.78, ontology_replay={"deterministic": True})
    replay_blocked = evaluate_offline_promotion_gate(dataset, baseline_score=0.7, candidate_score=0.78, ontology_replay={"deterministic": False})

    assert blocked["status"] == "blocked"
    assert "arena:insufficient_improvement" in blocked["blockers"]
    assert ready["status"] == "candidate_ready"
    assert replay_blocked["status"] == "blocked"
    assert "ontology:replay_not_deterministic" in replay_blocked["blockers"]


def test_publish_offline_plan_events_is_best_effort(monkeypatch):
    parsed = ParsedGoal(raw_text="Make gold", goal_type=GoalType.MAKE_GOLD, confidence=0.8)
    plan = ProgressionPlan(
        plan_id="plan-3",
        account_name="Visible.1234",
        actions=[PlanAction(action_id="a1", plan_id="plan-3", action_type="SELL_ITEM", confidence=0.7)],
    )
    dataset = build_offline_candidate_dataset(plan, parsed)
    calls = []

    def fake_publish(event, stream="training:events"):
        calls.append((event, stream))
        return True

    monkeypatch.setattr("gw2_progression.trainer.publisher.publish_training_event", fake_publish)

    result = publish_offline_plan_events(dataset, stream="training:test")

    assert result == {"attempted": 1, "published": 1, "best_effort": True, "blocks_product_flow": False}
    assert calls[0][1] == "training:test"
