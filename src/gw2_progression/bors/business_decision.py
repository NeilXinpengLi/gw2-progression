"""DecisionEngine — weighted, explainable decision engine for BORS.

Produces DecisionRecord with:
  - decision: APPROVE / REJECT / REVIEW / CERTIFY / DEFER
  - score:    0..1 weighted score
  - factors:  per-factor breakdown (name, value, weight, impact)
  - reason:   human-readable explanation

Integrates with v4 scoring for action-level decisions and KPI/Risk for
business-level decisions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Decision(Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REVIEW = "REVIEW"
    CERTIFY = "CERTIFY"
    DEFER = "DEFER"


@dataclass
class DecisionFactor:
    name: str
    value: float       # 0..1
    weight: float      # 0..1 (sum need not be 1; normalized internally)
    impact: str = ""   # "positive" / "negative"
    detail: str = ""


@dataclass
class DecisionRecord:
    decision: Decision
    score: float           # weighted total 0..1
    confidence: float = 1.0
    threshold: float = 0.6
    factors: list[DecisionFactor] = field(default_factory=list)
    reason: str = ""
    metadata: dict = field(default_factory=dict)


DEFAULT_THRESHOLDS = {
    "publish_report": 0.6,
    "approve_recommendation": 0.5,
    "allow_sell": 0.7,
    "certify_build": 0.8,
}


class DecisionEngine:
    """Weighted multi-factor decision engine."""

    def __init__(self, thresholds: dict[str, float] | None = None):
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def decide(
        self,
        decision_type: str,
        factors: list[DecisionFactor],
        metadata: dict | None = None,
    ) -> DecisionRecord:
        weighted_sum = sum(f.value * f.weight for f in factors)
        total_weight = sum(f.weight for f in factors)
        score = weighted_sum / max(total_weight, 1)
        score = max(0, min(score, 1))

        threshold = self.thresholds.get(decision_type, 0.6)
        negative_factors = [f for f in factors if f.impact == "negative" and f.value > 0]
        blocking = [f for f in factors if f.impact == "negative" and f.value >= 0.9]

        if blocking:
            decision = Decision.REJECT
            reason = f"Insufficient score ({score:.2f} < {threshold}); blocking: {', '.join(f.name for f in blocking)}"
        elif score >= threshold and not negative_factors:
            decision = Decision.APPROVE
            reason = f"All gates passed (score={score:.2f} >= {threshold})"
        elif score >= threshold and negative_factors:
            decision = Decision.REVIEW
            reason = f"Score adequate but negative factors present (score={score:.2f})"
        else:
            decision = Decision.REJECT
            reason = f"Insufficient score (score={score:.2f} < {threshold})"

        return DecisionRecord(
            decision=decision,
            score=round(score, 3),
            threshold=threshold,
            factors=factors,
            reason=reason,
            metadata=metadata or {},
            confidence=round(1 - len(blocking) * 0.2, 2),
        )

    def decide_from_kpis(
        self,
        decision_type: str,
        kpis: list[Any],
        risks: list[Any],
        extra_factors: list[DecisionFactor] | None = None,
    ) -> DecisionRecord:
        factors = list(extra_factors or [])
        for kpi in kpis:
            if hasattr(kpi, "value"):
                normalized = max(0, min(kpi.value, 1))
                factors.append(DecisionFactor(
                    name=kpi.name if hasattr(kpi, "name") else "kpi",
                    value=normalized,
                    weight=0.3,
                    impact="positive" if normalized >= 0.5 else "negative",
                    detail=getattr(kpi, "detail", ""),
                ))
        for risk in risks:
            if hasattr(risk, "level"):
                level_str = risk.level if hasattr(risk, "level") else "MEDIUM"
                levels = {"NONE": 0, "LOW": 0.2, "MEDIUM": 0.5, "HIGH": 0.8, "CRITICAL": 1.0}
                risk_val = levels.get(str(level_str).upper(), 0.5)
                factors.append(DecisionFactor(
                    name=getattr(risk, "name", "risk"),
                    value=risk_val,
                    weight=0.3,
                    impact="negative",
                    detail=getattr(risk, "detail", ""),
                ))
        return self.decide(decision_type, factors)

    def score_action(
        self,
        action: dict,
        strategy_weights: dict[str, float],
        **kwargs,
    ) -> float:
        """Legacy score_action wrapper."""
        from ..services.v4_economic_model import score_action as v4_score
        price = kwargs.get("price")
        strategy = kwargs.get("strategy", "hybrid")
        result = v4_score(action, price, strategy)
        return result.get("final_score", 0)
