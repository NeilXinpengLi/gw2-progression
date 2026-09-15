from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import Any

from gw2_progression.rule_engine_v2.core.rl.reward_engine import RuleReward


@dataclass
class RuleAgent:
    id: str
    name: str
    rules: list[dict[str, Any]]
    fitness: float = 0.0
    generation: int = 0
    wins: int = 0
    total_matches: int = 0
    strategy: str = "conservative"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def win_rate(self) -> float:
        return self.wins / max(self.total_matches, 1)

    def apply_rules(self, world: dict[str, Any]) -> dict[str, Any]:
        result = dict(world)
        for rule in sorted(self.rules, key=lambda r: r.get("priority", 0), reverse=True):
            if rule.get("active", True):
                result = self._apply_rule(rule, result)
        return result

    def _apply_rule(self, rule: dict[str, Any], world: dict[str, Any]) -> dict[str, Any]:
        rule.get("action", "skip")
        target = rule.get("target", "market")
        if target == "market" and "market" in world:
            market = world["market"]
            for item_id, data in market.items():
                data["price"] = data.get("price", 100) * (1 + rule.get("price_impact", 0))
        elif target == "inventory" and "inventory" in world:
            inventory = world["inventory"]
            for item_id in list(inventory.keys()):
                inventory[item_id] = max(0, inventory.get(item_id, 0) + rule.get("inventory_impact", 0))
        return world

    def evaluate(self, world: dict[str, Any]) -> float:
        try:
            result = self.apply_rules(world)
            RuleReward()
            score = 0.0
            market = result.get("market", {})
            inventory = result.get("inventory", {})
            if market:
                total_value = sum(v.get("price", 0) * v.get("supply", 0) for v in market.values())
                score += min(total_value / 100000, 0.5)
            if inventory:
                score += min(sum(inventory.values()) / 100, 0.3)
            return round(score, 4)
        except Exception:
            return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "fitness": self.fitness,
            "generation": self.generation,
            "wins": self.wins,
            "total_matches": self.total_matches,
            "win_rate": self.win_rate,
            "strategy": self.strategy,
            "rule_count": len(self.rules),
        }


def create_rule_agent(name: str, rules: list[dict[str, Any]] | None = None) -> RuleAgent:
    if rules is None:
        rules = [
            {"id": f"rule:{uuid.uuid4().hex[:8]}", "type": "economy", "action": "trade", "target": "market", "price_impact": 0.02, "active": True, "priority": 1},
            {"id": f"rule:{uuid.uuid4().hex[:8]}", "type": "crafting", "action": "craft", "target": "inventory", "inventory_impact": 1, "active": True, "priority": 2},
        ]
    return RuleAgent(
        id=f"agent:{uuid.uuid4().hex[:8]}",
        name=name,
        rules=rules,
        strategy=random.choice(["conservative", "aggressive", "balanced", "adaptive"]),
    )
