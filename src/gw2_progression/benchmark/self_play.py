from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from gw2_progression.benchmark.agents import Agent


@dataclass
class ArenaWorld:
    max_steps: int = 100
    seed: int = 1
    time: int = 0
    agents: dict[str, dict[str, Any]] = field(default_factory=dict)
    market: dict[str, dict[str, float]] = field(default_factory=dict)
    interactions: list[dict[str, Any]] = field(default_factory=list)
    _rng: random.Random = field(default_factory=lambda: random.Random(1))

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self._init_market()

    def _init_market(self) -> None:
        base_items = ["mystic_coin", "ecto", "magnetite_shard", "legendary_component", "skin_unlock"]
        for item_id in base_items:
            self.market[item_id] = {
                "price": round(50 + self._rng.random() * 150, 2),
                "supply": 50 + self._rng.random() * 100,
                "demand": 50 + self._rng.random() * 100,
                "velocity": 0.5 + self._rng.random() * 2,
            }

    @property
    def state(self) -> dict[str, Any]:
        return {
            "market": dict(self.market),
            "inventory": {},
            "agent_gold": 1000,
            "step": self.time,
            "max_steps": self.max_steps,
            "seed": self.seed,
        }

    def apply(self, action: dict[str, Any], agent_id: str = "unknown") -> dict[str, Any]:
        item_id = action.get("item_id")
        if not item_id or item_id not in self.market:
            return {"score": 0, "action": action, "agent_id": agent_id, "error": "invalid_item"}
        row = self.market[item_id]
        action_type = action.get("type")
        qty = int(action.get("quantity", 1))
        score = 0.0
        if action_type == "trade":
            row["demand"] += qty
            row["velocity"] += 0.05 * qty
            if row["supply"] > 0:
                profit = qty * row["price"] * 0.1
                score = profit / 1000
        elif action_type == "flip":
            row["velocity"] += 0.1 * qty
            score = 0.15 * qty
        elif action_type == "craft":
            for consumed, cqty in action.get("consumes", {}).items():
                if consumed in self.market:
                    self.market[consumed]["demand"] += int(cqty) * 2
            row["supply"] += qty
            score = 0.2 * qty
        elif action_type == "farm":
            row["supply"] += qty * 2
            score = 0.1 * qty
        else:
            score = 0.01 * qty
        self._update_price(item_id)
        result = {"score": round(score, 4), "action": action, "agent_id": agent_id, "item_id": item_id, "time": self.time}
        self.interactions.append(result)
        return result

    def _update_price(self, item_id: str) -> None:
        row = self.market.get(item_id)
        if not row:
            return
        pressure = (row["demand"] - row["supply"]) / max(row["demand"] + row["supply"], 1)
        row["price"] = round(max(row["price"] * (1 + pressure * 0.05 + row["velocity"] * 0.001), 1), 2)
        row["velocity"] = round(max(row["velocity"] * 0.97, 0), 3)
        row["demand"] = round(max(row["demand"] * 0.995, 0), 3)
        row["supply"] = round(max(row["supply"] * 0.995, 0), 3)

    def tick(self) -> dict[str, Any]:
        self.time += 1
        return {
            "time": self.time,
            "market_snapshot": {k: dict(v) for k, v in self.market.items()},
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "time": self.time,
            "max_steps": self.max_steps,
            "market": {k: dict(v) for k, v in self.market.items()},
            "interaction_count": len(self.interactions),
        }

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            self.seed = seed
        self.time = 0
        self.interactions.clear()
        self._rng = random.Random(self.seed)
        self._init_market()


class SelfPlayEngine:
    def __init__(self, world: ArenaWorld | None = None) -> None:
        self.world = world or ArenaWorld()

    def run_match(self, agents: list[Agent], world: ArenaWorld | None = None) -> list[dict[str, Any]]:
        w = world or self.world
        w.reset()
        history: list[dict[str, Any]] = []
        for agent in agents:
            agent.reset()
        for t in range(w.max_steps):
            step_actions = []
            for agent in agents:
                state = w.state.copy()
                state["agent_id"] = agent.id
                state["agent_gold"] = 1000 + agent.total_reward * 100
                state["inventory"] = self._get_agent_inventory(agent, w)
                action = agent.act(state)
                reward = w.apply(action, agent_id=agent.id)
                agent.observe(reward)
                entry = {
                    "agent": agent.id,
                    "agent_name": agent.name,
                    "agent_type": agent.agent_type,
                    "action": action,
                    "reward": reward,
                    "t": t,
                }
                step_actions.append(entry)
                history.append(entry)
            w.tick()
        return history

    def _get_agent_inventory(self, agent: Agent, world: ArenaWorld) -> dict[str, int]:
        inv: dict[str, int] = {}
        for entry in agent.memory:
            action = entry.get("action", {})
            item_id = action.get("item_id")
            if item_id:
                inv[item_id] = inv.get(item_id, 0) + 1
            for consumed in action.get("consumes", {}):
                inv[consumed] = max(inv.get(consumed, 0) - 1, 0)
        return inv

    def run_self_play_loop(self, agents: list[Agent], num_rounds: int = 3) -> list[dict[str, Any]]:
        all_history: list[dict[str, Any]] = []
        for round_idx in range(num_rounds):
            seed = self.world.seed + round_idx
            round_world = ArenaWorld(max_steps=self.world.max_steps, seed=seed)
            round_history = self.run_match(agents, world=round_world)
            for entry in round_history:
                entry["round"] = round_idx
            all_history.extend(round_history)
        return all_history
