from __future__ import annotations

import copy
import random
from typing import Any


class RuleMutator:
    def __init__(self, mutation_rate: float = 0.3, noise_scale: float = 0.1) -> None:
        self.mutation_rate = mutation_rate
        self.noise_scale = noise_scale
        self._rng = random.Random(1)

    def mutate(self, rule: dict[str, Any]) -> dict[str, Any]:
        if self._rng.random() > self.mutation_rate:
            return rule
        mutated = copy.deepcopy(rule)
        strategy = self._rng.choice(["parameter", "structural", "threshold", "swap"])
        if strategy == "parameter":
            for key in ("price_impact", "base_accuracy", "profit", "volatility", "inventory_impact"):
                if key in mutated:
                    mutated[key] = mutated[key] + self._rng.uniform(-self.noise_scale, self.noise_scale)
                    if isinstance(mutated[key], (int, float)):
                        mutated[key] = max(0, mutated[key])
        elif strategy == "structural":
            if "conditions" in mutated and mutated["conditions"]:
                idx = self._rng.randint(0, len(mutated["conditions"]) - 1)
                mutated["conditions"][idx] = f"mutated_condition_{self._rng.randint(100, 999)}"
            elif "type" in mutated:
                mutated["type"] = self._rng.choice(["crafting", "economy", "behavior", "meta"])
        elif strategy == "threshold":
            if "priority" in mutated:
                mutated["priority"] = max(0, mutated.get("priority", 1) + self._rng.randint(-1, 1))
            for key in ("confidence", "threshold"):
                if key in mutated:
                    mutated[key] = max(0, min(1, mutated[key] + self._rng.uniform(-0.1, 0.1)))
        elif strategy == "swap":
            if "action" in mutated and "target" in mutated:
                if self._rng.random() < 0.5:
                    mutated["action"] = self._rng.choice(["trade", "craft", "farm", "skip", "merge"])
                else:
                    mutated["target"] = self._rng.choice(["market", "inventory", "achievement", "economy"])
        mutated["mutated"] = True
        mutated["mutation_strategy"] = strategy
        return mutated

    def mutate_batch(self, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.mutate(r) for r in rules]

    def add_random_variation(self, rule: dict[str, Any]) -> dict[str, Any]:
        return self.mutate(rule)
