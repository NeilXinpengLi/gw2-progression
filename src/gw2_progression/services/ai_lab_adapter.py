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
    evidence_sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "maturity": self.maturity,
            "validation": copy.deepcopy(self.validation),
            "simulation": copy.deepcopy(self.simulation),
            "evidence_sources": list(self.evidence_sources),
            "warnings": list(self.warnings),
        }


class AILabAdapter:
    """Product-safe facade over AI Lab, Rule, Lifecycle, and evidence layers."""

    SOURCE = "ai_lab_adapter:v1"

    async def enhance_plan(self, plan: ProgressionPlan, parsed: ParsedGoal, account_state: dict[str, Any]) -> tuple[ProgressionPlan, AIPlanAssessment]:
        """Annotate a plan with validation and simulation evidence.

        This phase intentionally does not reorder or replace actions. It only
        adds evidence, risk notes, and a compact insight suffix so the product
        path remains deterministic and easy to roll back.
        """
        warnings = self._validate_plan(plan, parsed)
        simulation = self._simulate_plan(plan, account_state)
        evidence_sources = [
            self.SOURCE,
            "goal_driven_os:product_planning",
            "ontology_runtime:evidence_contract",
            "rule_engine_v2:validation_adapter_pending",
            "lifecycle:simulation_adapter_pending",
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
                "valid": not any(warning.startswith("blocking:") for warning in warnings),
                "warning_count": len(warnings),
                "goal_type": str(parsed.goal_type),
            },
            simulation=simulation,
            evidence_sources=evidence_sources,
            warnings=warnings,
        )
        return enhanced, assessment

    def _validate_plan(self, plan: ProgressionPlan, parsed: ParsedGoal) -> list[str]:
        warnings: list[str] = []
        if not plan.actions:
            warnings.append("blocking:no_actions")
            return warnings
        if plan.estimated_days > 30:
            warnings.append("long_horizon:plan_exceeds_30_days")
        if plan.total_cost_copper > 0 and parsed.gold_budget_copper > 0 and plan.total_cost_copper > parsed.gold_budget_copper:
            warnings.append("budget:plan_cost_exceeds_declared_budget")
        low_confidence = [action.action_id for action in plan.actions if 0 < action.confidence < 0.55]
        if low_confidence:
            warnings.append(f"confidence:{len(low_confidence)}_low_confidence_actions")
        if len(plan.actions) > 21:
            warnings.append("complexity:more_than_21_actions")
        return warnings

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
            evidence_sources=["goal_driven_os:product_planning"],
            warnings=[f"adapter_error:{exc}"],
        )
