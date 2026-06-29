"""Economy Rule Learner — learns price trends, elasticity, and shock responses from price series.

This wraps the existing EconomySimulator and SyntheticWorld with a rule-learning layer
that produces structured economy rules (supply -> price down, demand spike -> volatility up, etc.)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from gw2_progression.rule_engine.core.api_rules.schema_parser import Rule, RuleType


class EconomyRuleLearner:
    """Learns economy rules from price time-series data.

    Wraps the existing EconomySimulator + price service infrastructure
    to produce structured economy rules.
    """

    def __init__(self) -> None:
        self._history: dict[str, list[dict[str, float]]] = defaultdict(list)

    def learn(self, price_series: dict[str, list[dict[str, float]]] | None = None) -> dict[str, Any]:
        rules: dict[str, Any] = {}
        series = price_series or {}

        rules["trend"] = self.detect_trend(series)
        rules["elasticity"] = self.compute_elasticity(series)
        rules["shock_response"] = self.detect_shocks(series)

        return rules

    def detect_trend(self, series: dict[str, list[dict[str, float]]]) -> list[Rule]:
        rules: list[Rule] = []
        for item_id, points in series.items():
            if len(points) < 3:
                continue
            prices = [p.get("price", 0) for p in points]
            first, last = prices[0], prices[-1]
            if first == 0:
                continue
            change = (last - first) / first
            if change > 0.1:
                direction = "upward"
            elif change < -0.1:
                direction = "downward"
            else:
                direction = "stable"

            rules.append(Rule(
                id=f"trend_{item_id}",
                type=RuleType.ECONOMY_TREND,
                source=f"price:{item_id}",
                condition={"item_id": item_id, "direction": direction, "change_pct": round(change * 100, 1)},
                action=f"{'buy' if direction == 'upward' else 'sell' if direction == 'downward' else 'hold'}_{item_id}",
                confidence=min(0.9, abs(change) * 2),
                metadata={"item_id": item_id, "direction": direction, "data_points": len(points)},
            ))
        return rules

    def compute_elasticity(self, series: dict[str, list[dict[str, float]]]) -> list[Rule]:
        rules: list[Rule] = []
        for item_id, points in series.items():
            if len(points) < 4:
                continue
            price_changes: list[float] = []
            supply_changes: list[float] = []
            for i in range(1, len(points)):
                prev, cur = points[i - 1], points[i]
                if prev.get("price", 0) > 0 and prev.get("supply", 0) > 0:
                    price_changes.append((cur.get("price", 0) - prev["price"]) / prev["price"])
                    supply_changes.append((cur.get("supply", 0) - prev["supply"]) / prev["supply"])

            if not price_changes or not supply_changes:
                continue
            avg_price_delta = sum(abs(p) for p in price_changes) / len(price_changes)
            avg_supply_delta = sum(abs(s) for s in supply_changes) / len(supply_changes)
            elasticity = avg_price_delta / max(avg_supply_delta, 0.001)

            rules.append(Rule(
                id=f"elasticity_{item_id}",
                type=RuleType.ECONOMY_ELASTICITY,
                source=f"price:{item_id}",
                condition={"item_id": item_id, "elasticity": round(elasticity, 3)},
                action=f"price_{'elastic' if elasticity > 1.0 else 'inelastic'}_{item_id}",
                confidence=min(0.85, 1.0 / (1.0 + elasticity * 0.1)),
                metadata={"item_id": item_id, "elasticity": round(elasticity, 3)},
            ))
        return rules

    def detect_shocks(self, series: dict[str, list[dict[str, float]]]) -> list[Rule]:
        rules: list[Rule] = []
        for item_id, points in series.items():
            if len(points) < 5:
                continue
            prices = [p.get("price", 0) for p in points]
            for i in range(2, min(len(prices) - 2, len(prices))):
                delta = abs(prices[i] - prices[i - 1]) / max(prices[i - 1], 1)
                if delta > 0.25:
                    recovery = abs(prices[i + 1] - prices[i]) / max(prices[i], 1) if i + 1 < len(prices) else 0
                    rules.append(Rule(
                        id=f"shock_{item_id}_t{i}",
                        type=RuleType.ECONOMY_SHOCK,
                        source=f"price:{item_id}",
                        condition={"item_id": item_id, "shock_delta_pct": round(delta * 100, 1), "recovery_pct": round(recovery * 100, 1)},
                        action=f"monitor_{item_id}",
                        confidence=0.7,
                        metadata={"item_id": item_id, "shock_size": round(delta, 3), "recovery": round(recovery, 3)},
                    ))
        return rules

    def learn_as_rules(self, price_series: dict[str, list[dict[str, float]]] | None = None) -> list[Rule]:
        result = self.learn(price_series)
        all_rules: list[Rule] = []
        for category in ("trend", "elasticity", "shock_response"):
            all_rules.extend(result.get(category, []))
        return all_rules
