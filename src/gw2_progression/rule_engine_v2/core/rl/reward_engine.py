from __future__ import annotations

from typing import Any


class RuleReward:
    def __init__(self, accuracy_weight: float = 0.4, profit_weight: float = 0.3, stability_weight: float = 0.2, complexity_penalty: float = 0.1) -> None:
        self.weights = {
            "accuracy": accuracy_weight,
            "profit": profit_weight,
            "stability": stability_weight,
        }
        self.complexity_penalty = complexity_penalty

    def compute(self, rule: dict[str, Any]) -> dict[str, float]:
        accuracy = self.sim_accuracy(rule)
        profit = self.economy_gain(rule)
        stability = self.system_stability(rule)
        complexity = self.rule_complexity(rule)
        total = (
            self.weights["accuracy"] * accuracy
            + self.weights["profit"] * profit
            + self.weights["stability"] * stability
            - self.complexity_penalty * complexity
        )
        return {
            "accuracy": round(accuracy, 4),
            "profit": round(profit, 4),
            "stability": round(stability, 4),
            "complexity": round(complexity, 4),
            "total": round(total, 4),
        }

    def compute_batch(self, rules: list[dict[str, Any]]) -> list[dict[str, float]]:
        return [self.compute(r) for r in rules]

    def sim_accuracy(self, rule: dict[str, Any]) -> float:
        base = rule.get("base_accuracy", 0.7)
        test_count = rule.get("test_count", 1)
        pass_count = rule.get("test_pass", 0)
        if test_count > 0:
            return min(base * (pass_count / test_count) * 1.2, 1.0)
        return base

    def economy_gain(self, rule: dict[str, Any]) -> float:
        profit = abs(rule.get("profit", 0))
        volume = abs(rule.get("volume", 1))
        gain = profit * volume / 1000
        return min(max(gain, 0), 1.0)

    def system_stability(self, rule: dict[str, Any]) -> float:
        volatility = abs(rule.get("volatility", 0))
        impact = abs(rule.get("market_impact", 0))
        stability = max(0, 1.0 - volatility * 0.5 - impact * 0.3)
        return min(stability, 1.0)

    def rule_complexity(self, rule: dict[str, Any]) -> float:
        conditions = rule.get("conditions", [])
        actions = rule.get("actions", [])
        depth = rule.get("depth", 1)
        complexity = (len(conditions) + len(actions)) * depth / 20
        return min(complexity, 1.0)

    def fitness(self, rule: dict[str, Any]) -> float:
        return self.compute(rule)["total"]
