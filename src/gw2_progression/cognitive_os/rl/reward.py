from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RewardComponents:
    economic_gain: float = 0.0
    progression_efficiency: float = 0.0
    reasoning_accuracy: float = 0.0
    instability: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.economic_gain
            + self.progression_efficiency
            + self.reasoning_accuracy
            - self.instability
        )


class RewardFunction:
    """Computes reward = economic_gain + progression_efficiency
    + reasoning_accuracy - instability.

    All components normalized to [0, 1] range.
    """

    def __init__(self) -> None:
        self._history: list[RewardComponents] = []

    def compute(
        self,
        state_before: dict[str, Any],
        state_after: dict[str, Any],
        action: dict[str, Any] | None = None,
        validation_results: list[dict[str, Any]] | None = None,
    ) -> RewardComponents:
        components = RewardComponents(
            economic_gain=self._calc_economic_gain(state_before, state_after),
            progression_efficiency=self._calc_progression_efficiency(state_before, state_after),
            reasoning_accuracy=self._calc_reasoning_accuracy(action, validation_results),
            instability=self._calc_instability(state_before, state_after),
        )
        self._history.append(components)
        return components

    def compute_from_trajectory(
        self,
        trajectory: list[dict[str, Any]],
        actions: list[dict[str, Any]],
        validations: list[list[dict[str, Any]]] | None = None,
    ) -> list[RewardComponents]:
        results: list[RewardComponents] = []
        for i in range(1, len(trajectory)):
            v = validations[i] if validations and i < len(validations) else None
            comp = self.compute(trajectory[i - 1], trajectory[i], actions[i - 1] if i - 1 < len(actions) else None, v)
            results.append(comp)
        return results

    def _calc_economic_gain(self, before: dict[str, Any], after: dict[str, Any]) -> float:
        before_gold = before.get("gold", 0)
        after_gold = after.get("gold", 0)
        gain = after_gold - before_gold
        max_expected_gain = 1000.0
        return max(0.0, min(1.0, gain / max_expected_gain))

    def _calc_progression_efficiency(self, before: dict[str, Any], after: dict[str, Any]) -> float:
        before_inv = before.get("inventory", {})
        after_inv = after.get("inventory", {})
        before_ach = set(before.get("achievements", []) or [])
        after_ach = set(after.get("achievements", []) or [])
        new_items = sum(1 for k, v in after_inv.items() if isinstance(v, (int, float)) and v > 0 and before_inv.get(k, 0) <= 0)
        new_ach = len(after_ach - before_ach)
        max_expected_progress = 10.0
        return max(0.0, min(1.0, (new_items + new_ach * 3) / max_expected_progress))

    def _calc_reasoning_accuracy(
        self,
        action: dict[str, Any] | None,
        validation_results: list[dict[str, Any]] | None,
    ) -> float:
        if not validation_results:
            return 1.0 if action else 0.5
        valid_count = sum(1 for v in validation_results if v.get("valid", False))
        return valid_count / max(len(validation_results), 1)

    def _calc_instability(self, before: dict[str, Any], after: dict[str, Any]) -> float:
        market_before = before.get("market", {}) or {}
        market_after = after.get("market", {}) or {}
        price_changes = 0
        total_items = max(len(market_before), 1)
        for item_id in set(market_before.keys()) & set(market_after.keys()):
            pb = market_before[item_id]
            pa = market_after[item_id]
            if isinstance(pb, dict) and isinstance(pa, dict):
                if abs(pa.get("price", 0) - pb.get("price", 0)) > 0.01 * max(pb.get("price", 1), 1):
                    price_changes += 1
        return min(1.0, price_changes / total_items)

    def reward_history(self) -> list[dict[str, float]]:
        return [
            {
                "economic_gain": r.economic_gain,
                "progression_efficiency": r.progression_efficiency,
                "reasoning_accuracy": r.reasoning_accuracy,
                "instability": r.instability,
                "total": r.total,
            }
            for r in self._history
        ]

    def average_reward(self, window: int = 100) -> float:
        window_data = self._history[-window:]
        if not window_data:
            return 0.0
        return sum(r.total for r in window_data) / len(window_data)
