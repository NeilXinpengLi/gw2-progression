from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CRAFT = "CRAFT"
    FARM = "FARM"
    RAID = "RAID"
    ACHIEVEMENT = "ACHIEVEMENT"
    META = "META"


@dataclass
class DecisionDistribution:
    """A probability distribution over decisions."""
    decision_type: str
    probabilities: dict[str, float]
    expected_value: float = 0.0
    uncertainty: float = 0.0
    factors: dict[str, float] = field(default_factory=dict)


class ProbabilisticBORS:
    """Probabilistic BORS — decisions as probability distributions.

    Instead of a single deterministic decision, BORS outputs a distribution
    over possible decisions, calibrated by:
      - KPI signals (gold, inventory, market)
      - Behavioral profile (archetype mixture)
      - Risk tolerance (from behavior profile)
      - Market conditions
    """

    def __init__(self, default_risk_tolerance: float = 0.5) -> None:
        self.default_risk_tolerance = default_risk_tolerance
        self._decision_history: list[DecisionDistribution] = []

    def compute_decision_distribution(
        self,
        state: dict[str, Any],
        behavioral_profile: dict[str, Any] | None = None,
    ) -> DecisionDistribution:
        """Compute P(decision | state, behavioral profile)."""
        gold = state.get("gold", 0)
        inventory = state.get("inventory", {}) or {}
        market = state.get("market", {}) or {}
        total_items = sum(inventory.values()) if isinstance(inventory, dict) else 0

        risk_tolerance = (behavioral_profile or {}).get("risk_tolerance", self.default_risk_tolerance)
        arch_dist = (behavioral_profile or {}).get("action_distribution", {})

        raw_scores: dict[str, float] = {}

        raw_scores["BUY"] = self._score_buy(gold, market, risk_tolerance)
        raw_scores["SELL"] = self._score_sell(gold, inventory, market, risk_tolerance)
        raw_scores["HOLD"] = self._score_hold(gold, risk_tolerance)
        raw_scores["CRAFT"] = self._score_craft(gold, total_items, risk_tolerance)
        raw_scores["FARM"] = self._score_farm(gold, risk_tolerance)
        raw_scores["RAID"] = 0.3 + risk_tolerance * 0.2
        raw_scores["ACHIEVEMENT"] = 0.2 + (1.0 - risk_tolerance) * 0.3
        raw_scores["META"] = 0.4 * (1.0 - risk_tolerance) * (1.0 + gold / 5000)

        for action_type_str, weight in arch_dist.items():
            if action_type_str.upper() in raw_scores:
                raw_scores[action_type_str.upper()] *= (1.0 + float(weight))

        total = sum(raw_scores.values())
        if total > 0:
            probabilities = {k: round(v / total, 4) for k, v in raw_scores.items()}
        else:
            probabilities = {d.value: 1.0 / len(DecisionType) for d in DecisionType}

        expected_value = self._expected_value(probabilities, state)
        uncertainty = self._estimate_uncertainty(probabilities)

        dist = DecisionDistribution(
            decision_type="BORS",
            probabilities=probabilities,
            expected_value=round(expected_value, 4),
            uncertainty=round(uncertainty, 4),
            factors={
                "gold": gold,
                "risk_tolerance": risk_tolerance,
                "inventory_size": total_items,
            },
        )
        self._decision_history.append(dist)
        return dist

    def _score_buy(self, gold: float, market: dict[str, Any], risk: float) -> float:
        if gold < 10:
            return 0.0
        cheap_items = sum(1 for v in market.values() if isinstance(v, dict) and v.get("price", 100) < 120)
        return 0.5 + cheap_items * 0.1 + risk * 0.3

    def _score_sell(self, gold: float, inventory: dict[str, Any], market: dict[str, Any], risk: float) -> float:
        if not inventory:
            return 0.0
        total_value = 0
        for item_id, count in inventory.items():
            if isinstance(item_id, str) and item_id in market:
                price = market[item_id].get("price", 0) if isinstance(market[item_id], dict) else 0
                total_value += price * count if isinstance(count, (int, float)) else 0
        return 0.3 + min(1.0, total_value / 5000) * 0.4 + risk * 0.2

    def _score_hold(self, gold: float, risk: float) -> float:
        if gold > 1000:
            return 0.4 * (1.0 - risk * 0.5)
        return 0.3

    def _score_craft(self, gold: float, total_items: int, risk: float) -> float:
        if total_items < 5:
            return 0.0
        return 0.3 + total_items * 0.01 + (1.0 - risk) * 0.2

    def _score_farm(self, gold: float, risk: float) -> float:
        if gold > 5000:
            return 0.1
        return 0.5 + (1.0 - gold / 5000) * 0.3 + risk * 0.1

    def _expected_value(self, probabilities: dict[str, float], state: dict[str, Any]) -> float:
        gold = state.get("gold", 0)
        ev = 0.0
        ev += probabilities.get("BUY", 0) * (-gold * 0.05)
        ev += probabilities.get("SELL", 0) * (gold * 0.10)
        ev += probabilities.get("HOLD", 0) * 0.0
        ev += probabilities.get("CRAFT", 0) * (gold * 0.02)
        ev += probabilities.get("FARM", 0) * (gold * 0.03)
        return ev

    def _estimate_uncertainty(self, probabilities: dict[str, float]) -> float:
        n = len(probabilities)
        if n <= 1:
            return 0.0
        h = 0.0
        for p in probabilities.values():
            if p > 0:
                h -= p * math.log2(p)
        return h / math.log2(n)

    def sample_decision(self, rng: random.Random | None = None) -> str:
        if not self._decision_history:
            return "HOLD"
        latest = self._decision_history[-1]
        rng = rng or random.Random()
        decisions = list(latest.probabilities.keys())
        weights = [latest.probabilities[d] for d in decisions]
        return rng.choices(decisions, weights=weights, k=1)[0]

    @property
    def decision_entropy_trend(self) -> list[float]:
        """Return entropy over last 20 decisions."""
        recent = self._decision_history[-20:]
        return [
            round(-sum(p * math.log2(p) if p > 0 else 0 for p in d.probabilities.values())
                  / math.log2(len(d.probabilities)), 4)
            for d in recent
        ]

    def to_dict(self) -> dict[str, Any]:
        latest = self._decision_history[-1] if self._decision_history else None
        return {
            "latest_distribution": latest.probabilities if latest else {},
            "latest_expected_value": latest.expected_value if latest else 0.0,
            "latest_uncertainty": latest.uncertainty if latest else 0.0,
            "decision_count": len(self._decision_history),
            "entropy_trend": self.decision_entropy_trend[-5:] if self._decision_history else [],
        }
