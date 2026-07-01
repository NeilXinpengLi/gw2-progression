"""Internal AI Lab adapter for product-safe plan enhancement.

The adapter keeps experimental systems behind a small product-facing contract.
Phase 1 is deterministic and non-blocking: it validates and annotates existing
Goal-Driven plans instead of letting AI Lab modules own user decisions.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any

from gw2_progression.models import ParsedGoal, PlanAction, ProgressionPlan

logger = logging.getLogger("gw2.ai_lab_adapter")


@dataclass(frozen=True)
class AIPlanAssessment:
    """Evidence bundle produced by the internal AI Lab adapter."""

    status: str
    maturity: str
    validation: dict[str, Any] = field(default_factory=dict)
    simulation: dict[str, Any] = field(default_factory=dict)
    ontology_evidence: dict[str, Any] = field(default_factory=dict)
    evidence_sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "maturity": self.maturity,
            "validation": copy.deepcopy(self.validation),
            "simulation": copy.deepcopy(self.simulation),
            "ontology_evidence": copy.deepcopy(self.ontology_evidence),
            "evidence_sources": list(self.evidence_sources),
            "warnings": list(self.warnings),
        }


class AILabAdapter:
    """Product-safe facade over AI Lab, Rule, Lifecycle, and evidence layers."""

    SOURCE = "ai_lab_adapter:v1"

    def __init__(
        self,
        rule_adapter: "RuleValidationAdapter | None" = None,
        lifecycle_adapter: "LifecycleSimulationAdapter | None" = None,
        ontology_adapter: "OntologyEvidenceAdapter | None" = None,
    ) -> None:
        self.rule_adapter = rule_adapter or RuleValidationAdapter()
        self.lifecycle_adapter = lifecycle_adapter or LifecycleSimulationAdapter()
        self.ontology_adapter = ontology_adapter or OntologyEvidenceAdapter()

    async def enhance_plan(self, plan: ProgressionPlan, parsed: ParsedGoal, account_state: dict[str, Any]) -> tuple[ProgressionPlan, AIPlanAssessment]:
        """Annotate a plan with validation and simulation evidence.

        This phase intentionally does not reorder or replace actions. It only
        adds evidence, risk notes, and a compact insight suffix so the product
        path remains deterministic and easy to roll back.
        """
        validation = self._validate_plan(plan, parsed)
        simulation = self._simulate_plan(plan, account_state)
        rule_result = self.rule_adapter.validate(plan, parsed, account_state)
        lifecycle_result = self.lifecycle_adapter.simulate(plan, account_state)
        warnings = [
            *validation["warnings"],
            *rule_result.get("warnings", []),
            *lifecycle_result.get("warnings", []),
        ]
        evidence_sources = [
            self.SOURCE,
            "goal_driven_os:product_planning",
            "ontology_runtime:evidence_contract",
            rule_result.get("source", "rule_engine_v2:validation_adapter"),
            lifecycle_result.get("source", "lifecycle:simulation_adapter"),
        ]
        maturity = "L2-L3"
        status = "enhanced" if plan.actions else "observed"

        enhanced = plan.model_copy(deep=True)
        enhanced.actions = self._annotate_actions(enhanced.actions, warnings, simulation)
        enhanced.insight = self._append_insight(enhanced.insight, warnings, simulation)

        assessment = AIPlanAssessment(
            status=status,
            maturity=maturity,
            validation={
                "valid": validation["valid"] and rule_result.get("valid", True) and lifecycle_result.get("valid", True),
                "warning_count": len(warnings),
                "goal_type": str(parsed.goal_type),
                "heuristic": validation,
                "rule_engine_v2": rule_result,
                "lifecycle": lifecycle_result.get("validation", {}),
            },
            simulation={**simulation, "lifecycle": lifecycle_result.get("simulation", {})},
            evidence_sources=evidence_sources,
            warnings=warnings,
        )
        ontology_evidence = self.ontology_adapter.bind_plan_assessment(enhanced, parsed, assessment)
        if ontology_evidence.get("source"):
            assessment.evidence_sources.append(ontology_evidence["source"])
        if ontology_evidence.get("warnings"):
            assessment.warnings.extend(ontology_evidence["warnings"])
            assessment.validation["warning_count"] = len(assessment.warnings)
        assessment = AIPlanAssessment(
            status=assessment.status,
            maturity=assessment.maturity,
            validation=assessment.validation,
            simulation=assessment.simulation,
            ontology_evidence=ontology_evidence,
            evidence_sources=assessment.evidence_sources,
            warnings=assessment.warnings,
        )
        return enhanced, assessment

    def _validate_plan(self, plan: ProgressionPlan, parsed: ParsedGoal) -> dict[str, Any]:
        warnings: list[str] = []
        if not plan.actions:
            warnings.append("blocking:no_actions")
            return {"valid": False, "warnings": warnings}
        if plan.estimated_days > 30:
            warnings.append("long_horizon:plan_exceeds_30_days")
        if plan.total_cost_copper > 0 and parsed.gold_budget_copper > 0 and plan.total_cost_copper > parsed.gold_budget_copper:
            warnings.append("budget:plan_cost_exceeds_declared_budget")
        low_confidence = [action.action_id for action in plan.actions if 0 < action.confidence < 0.55]
        if low_confidence:
            warnings.append(f"confidence:{len(low_confidence)}_low_confidence_actions")
        if len(plan.actions) > 21:
            warnings.append("complexity:more_than_21_actions")
        return {"valid": not any(warning.startswith("blocking:") for warning in warnings), "warnings": warnings}

    def _simulate_plan(self, plan: ProgressionPlan, account_state: dict[str, Any]) -> dict[str, Any]:
        wallet = int(account_state.get("wallet_gold", 0) or 0)
        daily_costs = [0 for _ in range(7)]
        daily_minutes = [0 for _ in range(7)]
        for action in plan.actions:
            day = min(max(int(action.day_index or 0), 0), 6)
            daily_costs[day] += max(int(action.cost_gold or 0), 0)
            daily_minutes[day] += max(int(action.time_cost_minutes or 0), 0)
        total_cost = sum(daily_costs)
        return {
            "horizon_days": min(max(plan.estimated_days or 1, 1), 30),
            "seven_day_cost_copper": daily_costs,
            "seven_day_time_minutes": daily_minutes,
            "total_cost_copper": total_cost,
            "wallet_copper": wallet,
            "wallet_after_plan_copper": wallet - total_cost,
            "affordable_with_wallet": wallet >= total_cost,
            "highest_time_day_minutes": max(daily_minutes) if daily_minutes else 0,
        }

    def _annotate_actions(self, actions: list[PlanAction], warnings: list[str], simulation: dict[str, Any]) -> list[PlanAction]:
        annotated = []
        for action in actions:
            item = action.model_copy(deep=True)
            if self.SOURCE not in item.data_sources:
                item.data_sources.append(self.SOURCE)
            notes = []
            if not simulation.get("affordable_with_wallet", True) and item.cost_gold > 0:
                notes.append("AI Lab simulation flags wallet shortfall risk.")
                item.confidence = round(max(0.1, item.confidence * 0.9), 2) if item.confidence else item.confidence
            if warnings and not item.risk_reason.startswith("[AI Lab]"):
                notes.append(f"Validation warnings: {', '.join(warnings[:2])}.")
            if notes:
                suffix = " ".join(notes)
                item.risk_reason = f"{item.risk_reason} [AI Lab] {suffix}".strip()
            annotated.append(item)
        return annotated

    def _append_insight(self, insight: str, warnings: list[str], simulation: dict[str, Any]) -> str:
        affordability = "affordable" if simulation.get("affordable_with_wallet", True) else "wallet shortfall"
        suffix = f"AI Lab check: {affordability}, {len(warnings)} validation warning(s)."
        if suffix in insight:
            return insight
        return f"{insight} {suffix}".strip()


class RuleValidationAdapter:
    """Runs a bounded Rule Engine v2 simulation for plan validation evidence."""

    SOURCE = "rule_engine_v2:validation_adapter"

    def validate(self, plan: ProgressionPlan, parsed: ParsedGoal, account_state: dict[str, Any]) -> dict[str, Any]:
        try:
            from gw2_progression.rule_engine_v2.core.engine import RuleEngineV2

            rules = self._rules_from_plan(plan, parsed)
            engine = RuleEngineV2()
            engine.extract_rules(rules)
            simulation = engine.simulate_rules(steps=2)
            evaluation = engine.evaluate_rules()
            metrics = simulation.get("economy_metrics", {})
            warnings = self._warnings_from_metrics(metrics, plan, account_state)
            return {
                "source": self.SOURCE,
                "valid": not any(warning.startswith("rule:blocking") for warning in warnings),
                "rule_count": len(rules),
                "warnings": warnings,
                "economy_metrics": metrics,
                "evaluation_count": len(evaluation),
            }
        except Exception as exc:
            logger.debug("Rule Engine v2 adapter skipped: %s", exc)
            return {
                "source": self.SOURCE,
                "valid": True,
                "rule_count": 0,
                "warnings": [f"rule:adapter_unavailable:{exc}"],
                "economy_metrics": {},
                "evaluation_count": 0,
            }

    def _rules_from_plan(self, plan: ProgressionPlan, parsed: ParsedGoal) -> list[dict[str, Any]]:
        rules = []
        for action in plan.actions:
            price_impact = 0.0
            if action.action_type == "BUY_ITEM":
                price_impact = 0.01
            elif action.action_type == "SELL_ITEM":
                price_impact = -0.01
            rules.append({
                "id": f"plan:{plan.plan_id}:{action.action_id}",
                "type": "plan_action",
                "target": "market",
                "active": True,
                "action_type": action.action_type,
                "goal_type": str(parsed.goal_type),
                "priority": action.priority,
                "price_impact": price_impact,
                "cost_copper": max(int(action.cost_gold or 0), 0),
                "time_cost_minutes": max(int(action.time_cost_minutes or 0), 0),
            })
        return rules

    def _warnings_from_metrics(self, metrics: dict[str, Any], plan: ProgressionPlan, account_state: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        volatility = float(metrics.get("price_volatility", 0) or 0)
        if volatility > 0.05:
            warnings.append("rule:market_volatility_high")
        wallet = int(account_state.get("wallet_gold", 0) or 0)
        if plan.total_cost_copper > wallet > 0:
            warnings.append("rule:budget_wallet_shortfall")
        return warnings


class LifecycleSimulationAdapter:
    """Maps product plans into Lifecycle validation and trajectory evidence."""

    SOURCE = "lifecycle:simulation_adapter"

    def simulate(self, plan: ProgressionPlan, account_state: dict[str, Any]) -> dict[str, Any]:
        try:
            from gw2_progression.lifecycle.core.engine import LifecycleEngine

            state = self._state_from_plan(plan, account_state)
            actions = self._actions_from_plan(plan)
            engine = LifecycleEngine()
            validation = engine.validate_state(state)
            trajectory = engine.forward.simulate_with_actions(state, actions[:10])
            validation_summary = engine.evolver.validation_summary(trajectory[-1]) if trajectory else {}
            warnings = self._warnings_from_lifecycle(validation, validation_summary)
            return {
                "source": self.SOURCE,
                "valid": bool(validation.get("valid", True)) and int(validation_summary.get("invalid", 0) or 0) == 0,
                "warnings": warnings,
                "validation": validation,
                "simulation": {
                    "trajectory_length": len(trajectory),
                    "action_validation_summary": validation_summary,
                    "end_time": trajectory[-1].get("time", 0) if trajectory else 0,
                },
            }
        except Exception as exc:
            logger.debug("Lifecycle adapter skipped: %s", exc)
            return {
                "source": self.SOURCE,
                "valid": True,
                "warnings": [f"lifecycle:adapter_unavailable:{exc}"],
                "validation": {},
                "simulation": {},
            }

    def _state_from_plan(self, plan: ProgressionPlan, account_state: dict[str, Any]) -> dict[str, Any]:
        inventory: dict[str, int] = {}
        for material in account_state.get("materials", []) or []:
            item_id = str(material.get("id", ""))
            if item_id:
                inventory[item_id] = int(material.get("count", 0) or 0)
        return {
            "inventory": inventory,
            "market": self._market_from_plan(plan),
            "achievements": [],
            "time": 0,
        }

    def _market_from_plan(self, plan: ProgressionPlan) -> dict[str, dict[str, Any]]:
        market: dict[str, dict[str, Any]] = {}
        for action in plan.actions:
            if action.item_id > 0:
                market[str(action.item_id)] = {
                    "price": max(float(action.cost_gold or action.reward_gold or 1), 1.0),
                    "supply": 100,
                    "demand": 100,
                }
        return market

    def _actions_from_plan(self, plan: ProgressionPlan) -> list[dict[str, Any]]:
        mapped = []
        for action in plan.actions:
            item_id = str(action.item_id or action.action_id)
            if action.action_type == "CRAFT_ITEM":
                mapped.append({"type": "craft", "item_id": item_id, "quantity": 1, "recipe_sourced": False})
            elif action.action_type == "BUY_ITEM":
                mapped.append({"type": "trade", "item_id": item_id, "quantity": 1, "price": max(action.cost_gold, 1)})
            elif action.action_type == "COMPLETE_ACHIEVEMENT":
                mapped.append({"type": "achievement", "item_id": item_id})
            else:
                mapped.append({"type": "farm", "item_id": item_id, "quantity": 1})
        return mapped

    def _warnings_from_lifecycle(self, validation: dict[str, Any], validation_summary: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        if validation and not validation.get("valid", True):
            warnings.append("lifecycle:state_validation_failed")
        invalid = int(validation_summary.get("invalid", 0) or 0)
        if invalid:
            warnings.append(f"lifecycle:{invalid}_invalid_actions")
        return warnings


class OntologyEvidenceAdapter:
    """Persists plan assessment evidence through Ontology Runtime lineage."""

    SOURCE = "ontology_runtime:plan_assessment_evidence"

    def bind_plan_assessment(self, plan: ProgressionPlan, parsed: ParsedGoal, assessment: AIPlanAssessment) -> dict[str, Any]:
        try:
            from gw2_progression.ontology import OntologyKernel
            from gw2_progression.ontology.evidence_binder import create_chain_link

            evidence_id = f"plan-assessment:{plan.plan_id}"
            content = self._content(plan, parsed, assessment)
            chain_link = create_chain_link(
                evidence_id=evidence_id,
                source_id=f"goal-driven:{plan.plan_id}",
                content=content,
            )
            kernel = OntologyKernel(tenant_id=self._tenant_id(plan), load_persisted=True)
            execution = kernel.execute_kernel_action(
                {
                    "type": "add_entity",
                    "entity": {
                        "id": evidence_id,
                        "type": "evidence",
                        "properties": {
                            "evidence_type": "ai_plan_assessment",
                            "source": self.SOURCE,
                            "object_id": plan.plan_id,
                            "content_hash": chain_link["content_hash"],
                            "chain_hash": chain_link["chain_hash"],
                            "goal_type": str(parsed.goal_type),
                            "warning_count": len(assessment.warnings),
                            "valid": bool(assessment.validation.get("valid", True)),
                            "manifest": content,
                        },
                    },
                },
                source="ai_lab_adapter",
            )
            return {
                "source": self.SOURCE,
                "tenant_id": self._tenant_id(plan),
                "evidence_id": evidence_id,
                "content_hash": chain_link["content_hash"],
                "chain_hash": chain_link["chain_hash"],
                "state_hash": execution.get("state_hash", ""),
                "persisted": execution.get("execution", {}).get("results", [{}])[0].get("result", {}).get("persistence", {}).get("persisted", False),
                "warnings": [],
            }
        except Exception as exc:
            logger.debug("Ontology evidence binding skipped: %s", exc)
            return {
                "source": self.SOURCE,
                "tenant_id": self._tenant_id(plan),
                "evidence_id": f"plan-assessment:{plan.plan_id}",
                "warnings": [f"ontology:adapter_unavailable:{exc}"],
                "persisted": False,
            }

    def _tenant_id(self, plan: ProgressionPlan) -> str:
        account = (plan.account_name or "unknown").strip().replace(" ", "_")
        return f"goal-plan:{account}"

    def _content(self, plan: ProgressionPlan, parsed: ParsedGoal, assessment: AIPlanAssessment) -> dict[str, Any]:
        return {
            "plan_id": plan.plan_id,
            "account_name": plan.account_name,
            "goal_type": str(parsed.goal_type),
            "strategy": plan.strategy,
            "action_count": len(plan.actions),
            "estimated_days": plan.estimated_days,
            "total_cost_copper": plan.total_cost_copper,
            "assessment": {
                "status": assessment.status,
                "maturity": assessment.maturity,
                "valid": bool(assessment.validation.get("valid", True)),
                "warnings": list(assessment.warnings),
                "evidence_sources": list(assessment.evidence_sources),
            },
            "rule_engine_v2": assessment.validation.get("rule_engine_v2", {}),
            "lifecycle": assessment.validation.get("lifecycle", {}),
            "simulation": assessment.simulation,
        }


async def enhance_plan_with_ai_lab(plan: ProgressionPlan, parsed: ParsedGoal, account_state: dict[str, Any]) -> tuple[ProgressionPlan, AIPlanAssessment]:
    """Enhance a plan without allowing AI Lab failures to block product flow."""
    try:
        return await AILabAdapter().enhance_plan(plan, parsed, account_state)
    except Exception as exc:
        logger.warning("AI Lab plan enhancement skipped: %s", exc)
        return plan, AIPlanAssessment(
            status="skipped",
            maturity="L2",
            validation={"valid": True, "warning_count": 0, "goal_type": str(parsed.goal_type)},
            simulation={},
            ontology_evidence={},
            evidence_sources=["goal_driven_os:product_planning"],
            warnings=[f"adapter_error:{exc}"],
        )
