from __future__ import annotations

import random
from typing import Any


class EconomySim:
    def __init__(self, seed: int = 1) -> None:
        self.seed = seed
        self._rng = random.Random(seed)
        self.prices: dict[str, float] = {}
        self.volumes: dict[str, int] = {}
        self.history: list[dict[str, Any]] = []

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            self.seed = seed
        self._rng = random.Random(self.seed)
        self.prices = {}
        self.volumes = {}
        self.history = []
        self._init_market()

    def _init_market(self) -> None:
        items = ["mystic_coin", "ecto", "damask", "spiritwood", "glob", "ore", "leather", "wood"]
        for item_id in items:
            self.prices[item_id] = round(50 + self._rng.random() * 150, 2)
            self.volumes[item_id] = self._rng.randint(100, 1000)

    def apply_rules(self, rules: list[dict[str, Any]]) -> dict[str, Any]:
        for rule in rules:
            if rule.get("active", True) and rule.get("target") == "market":
                for item_id in self.prices:
                    impact = rule.get("price_impact", 0)
                    self.prices[item_id] = max(1, self.prices[item_id] * (1 + impact))
        snapshot = {
            "prices": dict(self.prices),
            "volumes": dict(self.volumes),
            "timestamp": len(self.history),
        }
        self.history.append(snapshot)
        return snapshot

    def simulate_step(self, rules: list[dict[str, Any]]) -> dict[str, Any]:
        return self.apply_rules(rules)

    def simulate(self, rules: list[dict[str, Any]], steps: int = 10) -> list[dict[str, Any]]:
        self.reset()
        trajectory: list[dict[str, Any]] = []
        for _ in range(steps):
            snapshot = self.apply_rules(rules)
            trajectory.append(snapshot)
        return trajectory

    def get_metrics(self) -> dict[str, Any]:
        if not self.history:
            return {}
        latest = self.history[-1]
        prices = latest.get("prices", {})
        volumes = latest.get("volumes", {})
        avg_price = sum(prices.values()) / max(len(prices), 1)
        total_volume = sum(volumes.values())
        price_volatility = 0.0
        if len(self.history) >= 2:
            prev = self.history[-2].get("prices", {})
            changes = [abs(prices[k] - prev[k]) / max(prev[k], 1) for k in prices if k in prev]
            price_volatility = sum(changes) / max(len(changes), 1)
        return {
            "avg_price": round(avg_price, 2),
            "total_volume": total_volume,
            "price_volatility": round(price_volatility, 4),
            "item_count": len(prices),
            "steps_simulated": len(self.history),
        }
