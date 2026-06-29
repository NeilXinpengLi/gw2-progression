"""Synthetic GW2 world simulation embedded in the Expert AI subsystem."""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SyntheticPlayer:
    id: str
    goal: str
    style: str
    gold: float
    inventory: dict[str, int] = field(default_factory=dict)

    def act(self, world: "SyntheticWorld") -> dict[str, Any]:
        if self.style == "trader":
            return {"type": "trade", "item_id": "mystic_coin", "quantity": 1, "price": world.price("mystic_coin")}
        if self.style == "crafter":
            return {"type": "craft", "item_id": "legendary_component", "consumes": {"mystic_coin": 1}}
        if self.style == "flipper":
            return {"type": "flip", "item_id": "ecto", "quantity": 2, "price": world.price("ecto")}
        if self.style == "raider":
            return {"type": "farm", "item_id": "magnetite_shard", "quantity": 3}
        return {"type": "collect", "item_id": "skin_unlock", "quantity": 1}


@dataclass
class SyntheticWorld:
    seed: int = 1
    time: int = 0
    players: list[SyntheticPlayer] = field(default_factory=list)
    market: dict[str, dict[str, float]] = field(default_factory=dict)
    interactions: list[dict[str, Any]] = field(default_factory=list)

    def price(self, item_id: str) -> float:
        row = self.market.setdefault(item_id, {"price": 100.0, "supply": 100.0, "demand": 100.0, "velocity": 1.0})
        return row["price"]

    def apply(self, player: SyntheticPlayer, action: dict[str, Any]) -> dict[str, Any]:
        item_id = action.get("item_id", "unknown")
        row = self.market.setdefault(item_id, {"price": 100.0, "supply": 100.0, "demand": 100.0, "velocity": 1.0})
        action_type = action.get("type")
        if action_type in {"trade", "flip"}:
            qty = int(action.get("quantity", 1))
            row["demand"] += qty
            row["velocity"] += 0.05 * qty
            player.gold = max(player.gold - row["price"] * qty, 0)
            player.inventory[item_id] = player.inventory.get(item_id, 0) + qty
        elif action_type == "craft":
            for consumed, qty in action.get("consumes", {}).items():
                player.inventory[consumed] = max(player.inventory.get(consumed, 0) - int(qty), 0)
                self.market.setdefault(consumed, {"price": 100.0, "supply": 100.0, "demand": 100.0, "velocity": 1.0})["demand"] += int(qty) * 2
            player.inventory[item_id] = player.inventory.get(item_id, 0) + 1
            row["supply"] += 1
        else:
            qty = int(action.get("quantity", 1))
            row["supply"] += qty
            player.inventory[item_id] = player.inventory.get(item_id, 0) + qty
        self.update_price(item_id)
        result = {"player_id": player.id, "action": action, "market": dict(row), "time": self.time}
        self.interactions.append(result)
        return result

    def update_price(self, item_id: str) -> dict[str, float]:
        row = self.market[item_id]
        pressure = (row["demand"] - row["supply"]) / max(row["demand"] + row["supply"], 1)
        row["price"] = round(max(row["price"] * (1 + pressure * 0.05 + row["velocity"] * 0.001), 1), 2)
        row["velocity"] = round(max(row["velocity"] * 0.97, 0), 3)
        row["demand"] = round(max(row["demand"] * 0.99, 0), 3)
        row["supply"] = round(max(row["supply"] * 0.995, 0), 3)
        return row


class SyntheticSimulationEngine:
    """Deterministic synthetic world simulation that feeds OOSK/BORS/training."""

    PLAYER_STYLES = ["trader", "crafter", "raider", "collector", "flipper"]

    def __init__(self, system: Any) -> None:
        self.system = system
        self.world = SyntheticWorld()
        self.rng = random.Random(self.world.seed)

    def reset(self, seed: int = 1) -> dict[str, Any]:
        self.world = SyntheticWorld(seed=seed)
        self.rng = random.Random(seed)
        self.system.observability.record_flow("simulation.reset", "completed", {"seed": seed})
        return self.snapshot()

    def spawn_agents(self, count: int = 5, styles: list[str] | None = None) -> dict[str, Any]:
        styles = styles or self.PLAYER_STYLES
        spawned = []
        for idx in range(count):
            style = styles[idx % len(styles)]
            player = SyntheticPlayer(id=f"synthetic:{uuid.uuid4()}", goal=f"{style}_progression", style=style, gold=1000 + idx * 100)
            self.world.players.append(player)
            self.system.runtime.add_entity({"id": player.id, "type": "SyntheticPlayer", "properties": player_to_dict(player)})
            spawned.append(player_to_dict(player))
        self.system.observability.record_flow("agents.spawn", "completed", {"count": count})
        return {"agents": spawned, "count": len(spawned)}

    def run(self, ticks: int = 1, seed: int | None = None, agent_count: int | None = None) -> dict[str, Any]:
        if seed is not None:
            self.reset(seed)
        if agent_count and not self.world.players:
            self.spawn_agents(agent_count)
        trajectory = []
        for _ in range(max(ticks, 0)):
            trajectory.extend(self.tick())
        labels = self.generate_labels()
        reasoning = self.build_reasoning()
        dataset = self.export_dataset(trajectory=trajectory, labels=labels, reasoning=reasoning)
        self.system.observability.record_flow("simulation.run", "completed", {"ticks": ticks, "trajectory": len(trajectory)})
        return {"world": self.snapshot(), "trajectory": trajectory, "labels": labels, "reasoning": reasoning, "dataset": dataset}

    def tick(self) -> list[dict[str, Any]]:
        self.world.time += 1
        interactions = []
        for player in self.world.players:
            action = player.act(self.world)
            result = self.world.apply(player, action)
            interactions.append(result)
            self.system.runtime.simulate_step({
                "type": "update_state",
                "entity_id": player.id,
                "patch": {"gold": player.gold, "inventory": dict(player.inventory), "last_action": action["type"], "world_time": self.world.time},
            })
        return interactions

    def update_economy(self, updates: dict[str, dict[str, float]]) -> dict[str, Any]:
        for item_id, patch in updates.items():
            row = self.world.market.setdefault(item_id, {"price": 100.0, "supply": 100.0, "demand": 100.0, "velocity": 1.0})
            row.update({key: float(value) for key, value in patch.items()})
            self.world.update_price(item_id)
        self.system.observability.record_flow("economy.update", "completed", {"items": len(updates)})
        return {"market": self.world.market}

    def generate_labels(self) -> dict[str, Any]:
        labels = {}
        for item_id, row in self.world.market.items():
            demand_high = row["demand"] > row["supply"] * 1.2
            profit = row["price"] - 100
            crafting_required = any(i["action"].get("type") == "craft" and i["action"].get("item_id") == item_id for i in self.world.interactions)
            if demand_high and row["supply"] < 80:
                label = "HOLD"
            elif profit > 10:
                label = "SELL"
            elif crafting_required:
                label = "CRAFT"
            else:
                label = "REVIEW"
            score = min(abs(profit) / 100 + (0.3 if demand_high else 0), 1)
            labels[item_id] = {"decision": label, "score": round(score, 3), "risk": "HIGH" if row["velocity"] > 2 else "LOW"}
        return labels

    def build_reasoning(self) -> list[dict[str, Any]]:
        rows = []
        for item_id, label in self.generate_labels().items():
            rows.append({
                "item": item_id,
                "chain": [
                    {"node": item_id, "relation": "used_in", "target": "synthetic_progression"},
                    {"node": "synthetic_progression", "relation": "affected_by", "target": "market_shift"},
                    {"node": "market_shift", "relation": "leads_to", "target": label["decision"]},
                ],
                "decision": label,
            })
        return rows

    def export_dataset(self, trajectory: list[dict[str, Any]] | None = None, labels: dict[str, Any] | None = None, reasoning: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        trajectory = trajectory if trajectory is not None else self.world.interactions
        labels = labels if labels is not None else self.generate_labels()
        reasoning = reasoning if reasoning is not None else self.build_reasoning()
        dataset = {
            "version": f"sim-v1-seed-{self.world.seed}-t{self.world.time}",
            "state": self.snapshot(),
            "graph": self.system.runtime.graph.to_dict(),
            "trajectory": trajectory,
            "labels": labels,
            "reasoning": reasoning,
        }
        return dataset

    def snapshot(self) -> dict[str, Any]:
        return {
            "seed": self.world.seed,
            "time": self.world.time,
            "players": [player_to_dict(player) for player in self.world.players],
            "market": self.world.market,
            "interaction_count": len(self.world.interactions),
        }


def player_to_dict(player: SyntheticPlayer) -> dict[str, Any]:
    return {"id": player.id, "goal": player.goal, "style": player.style, "gold": player.gold, "inventory": dict(player.inventory)}
