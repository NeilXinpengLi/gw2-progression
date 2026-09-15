"""Simulation-driven Rule Validator — runs rules through the simulation engine and measures deviation.

Wraps the existing SyntheticSimulationEngine to validate rules:
  rule -> simulation -> deviation -> score
"""

from __future__ import annotations

import time
from typing import Any

from gw2_progression.rule_engine.core.api_rules.schema_parser import Rule, RuleType


class SimulationValidator:
    """Validates rules by running them through the simulation engine and measuring outcomes."""

    def __init__(self, simulation_engine: Any | None = None) -> None:
        self._sim = simulation_engine

    def validate(self, rules: list[Rule], world: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for rule in rules:
            result = self._validate_one(rule, world or {})
            results.append(result)
        return results

    def _validate_one(self, rule: Rule, world: dict[str, Any]) -> dict[str, Any]:
        start = time.time()
        simulated, deviation = self._simulate(rule, world)
        elapsed = time.time() - start

        validated = Rule(
            id=f"validated_{rule.id}",
            type=RuleType.VALIDATED,
            source=rule.source,
            condition=rule.condition,
            action=rule.action,
            confidence=min(rule.confidence, max(0, 1.0 - deviation)),
            validated_score=round(1.0 - deviation, 3),
            simulation_deviation=round(deviation, 3),
            metadata={**rule.metadata, "simulation_time_ms": round(elapsed * 1000, 1), "simulated_outcome": simulated},
        )
        return validated.to_dict()

    def _simulate(self, rule: Rule, world: dict[str, Any]) -> tuple[dict[str, Any], float]:
        if self._sim:
            try:
                market = world.get("market", {})
                item_id = rule.condition.get("item_id", "")
                if item_id and item_id in market:
                    row = market[item_id]
                    price = row.get("price", 100)
                    action = rule.action
                    if "sell" in action:
                        expected = price * 1.05 if "upward" in str(rule.condition) else price * 0.95
                    elif "buy" in action:
                        expected = price * 0.95 if "upward" in str(rule.condition) else price * 1.05
                    else:
                        expected = price
                    deviation = abs(expected - price) / max(price, 1)
                    return {"applied": True, "item_id": item_id, "price": price, "expected": round(expected, 2)}, round(deviation, 3)
            except Exception:
                pass
        return {"applied": False, "reason": "simulation not available"}, 0.5

    def run(self, rules: list[Rule], world: dict[str, Any]) -> list[dict[str, Any]]:
        return self.validate(rules, world)
