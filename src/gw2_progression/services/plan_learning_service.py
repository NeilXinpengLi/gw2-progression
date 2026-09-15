"""Offline plan/action/outcome export for Expert AI candidate learning."""

from __future__ import annotations

from typing import Any

from gw2_progression.architecture_contracts import EvidenceEnvelope, PlanOutcomeEvent, anonymize_account, validate_evidence_envelope
from gw2_progression.expert_ai.training import build_training_example
from gw2_progression.models import ParsedGoal, ProgressionPlan


def export_plan_outcome_events(
    plan: ProgressionPlan,
    parsed: ParsedGoal,
    outcomes: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Export anonymized action events without mutating product plans."""
    action_outcomes = outcomes or {}
    account_hash = anonymize_account(plan.account_name)
    events: list[dict[str, Any]] = []
    for action in plan.actions:
        event = PlanOutcomeEvent(
            plan_id=plan.plan_id,
            action_id=action.action_id,
            action_type=action.action_type,
            account_hash=account_hash,
            goal_type=str(parsed.goal_type),
            confidence=float(action.confidence or 0),
            data_sources=list(action.data_sources),
            outcome=action_outcomes.get(action.action_id, {"success": False, "reward": 0, "status": "unobserved"}),
        )
        events.append(event.to_training_event())
    return events


def build_offline_candidate_dataset(
    plan: ProgressionPlan,
    parsed: ParsedGoal,
    outcomes: dict[str, dict[str, Any]] | None = None,
    assessment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert product plan events into Expert AI training candidates."""
    events = export_plan_outcome_events(plan, parsed, outcomes)
    examples = [
        build_training_example(
            state=event["state"],
            reasoning_chain=[{"from": "goal_driven_os", "relation": "proposed", "to": event["decision"]["action_id"]}],
            decision=event["decision"],
            label={
                "quality": "observed" if event["outcome"].get("status") != "unobserved" else "unobserved",
                "success": event["outcome"]["success"],
                "reward": event["outcome"]["reward"],
            },
        )
        for event in events
    ]
    evidence = EvidenceEnvelope(
        evidence_type="offline_plan_learning_dataset",
        producer="expert_ai:offline_plan_learning",
        subject_id=f"plan:{plan.plan_id}",
        payload={"event_count": len(events), "assessment": assessment or {}},
        source_refs=["goal_driven_os", "expert_ai:offline_training"],
    ).to_dict()
    return {
        "dataset_type": "plan_action_outcome",
        "schema_version": "plan_action_outcome_dataset.v1",
        "plan_id": plan.plan_id,
        "account_hash": anonymize_account(plan.account_name),
        "events": events,
        "examples": examples,
        "evidence": evidence,
        "promotion_gate": {
            "mode": "offline_only",
            "requires_arena_baseline": True,
            "requires_ontology_replay": True,
            "can_block_product_flow": False,
        },
    }


def evaluate_offline_promotion_gate(
    dataset: dict[str, Any],
    baseline_score: float,
    candidate_score: float,
    ontology_replay: dict[str, Any] | None = None,
    min_improvement: float = 0.03,
) -> dict[str, Any]:
    """Evaluate whether an offline candidate can be promoted into adapter testing."""
    replay = ontology_replay or {}
    evidence_check = validate_evidence_envelope(dataset.get("evidence", {}))
    improvement = float(candidate_score) - float(baseline_score)
    blockers: list[str] = []
    if dataset.get("promotion_gate", {}).get("mode") != "offline_only":
        blockers.append("promotion_gate:not_offline_only")
    if dataset.get("promotion_gate", {}).get("can_block_product_flow") is not False:
        blockers.append("promotion_gate:can_block_product_flow")
    if not evidence_check["valid"]:
        blockers.append("evidence:invalid_envelope")
    if improvement < min_improvement:
        blockers.append("arena:insufficient_improvement")
    if replay and replay.get("deterministic") is not True:
        blockers.append("ontology:replay_not_deterministic")
    return {
        "status": "candidate_ready" if not blockers else "blocked",
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "improvement": round(improvement, 6),
        "min_improvement": min_improvement,
        "blockers": blockers,
        "evidence": evidence_check,
        "ontology_replay": replay,
    }


def publish_offline_plan_events(dataset: dict[str, Any], stream: str = "training:events") -> dict[str, Any]:
    """Best-effort publish of offline training candidates; never blocks product flow."""
    from gw2_progression.trainer.publisher import publish_training_event

    published = 0
    for event in dataset.get("events", []):
        if publish_training_event(event, stream=stream):
            published += 1
    return {
        "attempted": len(dataset.get("events", [])),
        "published": published,
        "best_effort": True,
        "blocks_product_flow": False,
    }
