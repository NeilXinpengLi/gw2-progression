from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GW2WorldState:
    time: int = 0
    market: dict[str, dict[str, float]] = field(default_factory=dict)
    inventory: dict[str, int] = field(default_factory=dict)
    achievements: list[str] = field(default_factory=list)
    players: int = 1
    gold_supply: float = 100000.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def copy(self) -> GW2WorldState:
        return GW2WorldState(
            time=self.time,
            market=deepcopy(self.market),
            inventory=dict(self.inventory),
            achievements=list(self.achievements),
            players=self.players,
            gold_supply=self.gold_supply,
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.time,
            "market": deepcopy(self.market),
            "inventory": dict(self.inventory),
            "achievements": list(self.achievements),
            "players": self.players,
            "gold_supply": self.gold_supply,
        }


class GW2WorldSim:
    def __init__(self, seed: int = 1) -> None:
        self.seed = seed
        self._rng = random.Random(seed)
        self.state = GW2WorldState()

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            self.seed = seed
        self._rng = random.Random(self.seed)
        self.state = GW2WorldState()
        self._init_economy()

    def _init_economy(self) -> None:
        items = ["mystic_coin", "ecto", "magnetite_shard", "damask", "spiritwood", "glob_of_ectoplasm", "obsidian_shard"]
        for item_id in items:
            self.state.market[item_id] = {
                "price": round(50 + self._rng.random() * 200, 2),
                "supply": 100 + self._rng.random() * 200,
                "demand": 100 + self._rng.random() * 200,
                "velocity": 0.5 + self._rng.random() * 2,
            }

    def step(self, rules: list[dict[str, Any]]) -> GW2WorldState:
        self.state.time += 1
        for rule in rules:
            if rule.get("active", True):
                self.state = self._apply_rule(rule, self.state)
        self._tick_economy()
        return self.state.copy()

    def step_batch(self, rules: list[dict[str, Any]], steps: int = 10) -> list[GW2WorldState]:
        trajectory: list[GW2WorldState] = []
        for _ in range(steps):
            trajectory.append(self.step(rules))
        return trajectory

    def _apply_rule(self, rule: dict[str, Any], state: GW2WorldState) -> GW2WorldState:
        new_state = state.copy()
        rule.get("action", "skip")
        target = rule.get("target", "market")
        if target == "market":
            for item_id in new_state.market:
                impact = rule.get("price_impact", 0)
                new_state.market[item_id]["price"] = max(1, new_state.market[item_id]["price"] * (1 + impact))
                new_state.market[item_id]["velocity"] += impact * 2
        elif target == "inventory":
            for item_id in list(new_state.inventory.keys()):
                impact = rule.get("inventory_impact", 0)
                new_state.inventory[item_id] = max(0, new_state.inventory[item_id] + int(impact))
        return new_state

    def _tick_economy(self) -> None:
        for item_id in self.state.market:
            data = self.state.market[item_id]
            pressure = (data["demand"] - data["supply"]) / max(data["demand"] + data["supply"], 1)
            data["price"] = round(max(data["price"] * (1 + pressure * 0.05 + data["velocity"] * 0.001), 1), 2)
            data["velocity"] = round(max(data["velocity"] * 0.97, 0), 3)
            data["demand"] = round(max(data["demand"] * 0.995, 0), 3)
            data["supply"] = round(max(data["supply"] * 0.995, 0), 3)
