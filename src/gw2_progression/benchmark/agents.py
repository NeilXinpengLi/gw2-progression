from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from gw2_progression.benchmark.elo import EloRating


@dataclass
class Agent:
    id: str
    name: str
    agent_type: str
    rating: EloRating = field(default_factory=lambda: EloRating(skill=1200, economic=1200, reasoning=1200))
    policy: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    memory: list[dict[str, Any]] = field(default_factory=list)
    total_reward: float = 0.0

    def act(self, state: dict[str, Any]) -> dict[str, Any]:
        if self.policy:
            return self.policy(state)
        return {"type": "skip", "item_id": None, "quantity": 0}

    def observe(self, reward: dict[str, Any]) -> None:
        self.memory.append(reward)
        self.total_reward += reward.get("score", 0)

    def reset(self) -> None:
        self.memory.clear()
        self.total_reward = 0.0


def _trader_policy(state: dict[str, Any]) -> dict[str, Any]:
    market = state.get("market", {})
    best_spread = 0
    best_item = None
    for item_id, data in market.items():
        supply = data.get("supply", 100)
        demand = data.get("demand", 100)
        price = data.get("price", 100)
        spread = demand - supply
        if spread > best_spread and price > 1:
            best_spread = spread
            best_item = item_id
    if best_item and best_spread > 5:
        return {"type": "trade", "item_id": best_item, "quantity": max(1, int(best_spread / 2)), "price": market[best_item]["price"]}
    return {"type": "skip", "item_id": None, "quantity": 0}


def _crafter_policy(state: dict[str, Any]) -> dict[str, Any]:
    inventory = state.get("inventory", {})
    market = state.get("market", {})
    if inventory.get("mystic_coin", 0) >= 1:
        return {"type": "craft", "item_id": "legendary_component", "consumes": {"mystic_coin": 1}}
    if market.get("mystic_coin", {}).get("price", 999) < 150:
        return {"type": "trade", "item_id": "mystic_coin", "quantity": 2, "price": market.get("mystic_coin", {}).get("price", 100)}
    return {"type": "collect", "item_id": "mystic_coin", "quantity": 1}


def _raider_policy(state: dict[str, Any]) -> dict[str, Any]:
    market = state.get("market", {})
    high_value_items = [k for k, v in market.items() if v.get("price", 0) > 150]
    target = high_value_items[0] if high_value_items else "magnetite_shard"
    return {"type": "farm", "item_id": target, "quantity": 3}


def _flipper_policy(state: dict[str, Any]) -> dict[str, Any]:
    market = state.get("market", {})
    volatile = [(k, v) for k, v in market.items() if v.get("velocity", 0) > 1.5]
    if volatile:
        item_id, data = volatile[0]
        return {"type": "flip", "item_id": item_id, "quantity": 2, "price": data["price"]}
    return {"type": "skip", "item_id": None, "quantity": 0}


class TraderAgent(Agent):
    def __init__(self, name: str = "TraderAgent") -> None:
        super().__init__(id=f"agent:trader:{uuid.uuid4().hex[:8]}", name=name, agent_type="trader", policy=_trader_policy)


class CrafterAgent(Agent):
    def __init__(self, name: str = "CrafterAgent") -> None:
        super().__init__(id=f"agent:crafter:{uuid.uuid4().hex[:8]}", name=name, agent_type="crafter", policy=_crafter_policy)


class RLAgent(Agent):
    def __init__(self, name: str = "RLAgent", model_path: str | None = None) -> None:
        super().__init__(id=f"agent:rl:{uuid.uuid4().hex[:8]}", name=name, agent_type="rl")
        self.model = None
        self.model_path = model_path
        self._load_model()

    def _load_model(self) -> None:
        if self.model_path:
            try:
                import joblib
                self.model = joblib.load(self.model_path)
            except Exception:
                self.model = None

    def act(self, state: dict[str, Any]) -> dict[str, Any]:
        if self.model:
            try:
                features = self._extract_features(state)
                pred = self.model.predict([features])[0]
                return self._prediction_to_action(pred, state)
            except Exception:
                pass
        return _trader_policy(state)

    def _extract_features(self, state: dict[str, Any]) -> list[float]:
        market = state.get("market", {})
        prices = [v.get("price", 100) for v in market.values()] or [100]
        supplies = [v.get("supply", 100) for v in market.values()] or [100]
        demands = [v.get("demand", 100) for v in market.values()] or [100]
        velocities = [v.get("velocity", 1) for v in market.values()] or [1]
        return [
            float(np.mean(prices)) / 100,
            float(np.std(prices)) / 100,
            float(np.mean(supplies)) / 100,
            float(np.mean(demands)) / 100,
            float(np.mean(velocities)),
            float(max(velocities)),
            float(len(market)),
            float(state.get("agent_gold", 1000)) / 10000,
            float(state.get("step", 0)) / 100,
        ]

    def _prediction_to_action(self, pred: int, state: dict[str, Any]) -> dict[str, Any]:
        state.get("market", {})
        action_map = {
            0: _trader_policy,
            1: _crafter_policy,
            2: _flipper_policy,
        }
        policy = action_map.get(pred, _trader_policy)
        return policy(state)


class MetaStrategyAgent(Agent):
    def __init__(self, name: str = "MetaAgent") -> None:
        super().__init__(id=f"agent:meta:{uuid.uuid4().hex[:8]}", name=name, agent_type="meta")
        self.sub_agents: list[Agent] = [
            TraderAgent(name=f"{name}_sub_trader"),
            CrafterAgent(name=f"{name}_sub_crafter"),
        ]
        self.current_idx = 0
        self.performance: dict[str, list[float]] = {a.id: [] for a in self.sub_agents}

    def act(self, state: dict[str, Any]) -> dict[str, Any]:
        agent = self.sub_agents[self.current_idx]
        action = agent.act(state)
        action["meta_agent"] = self.id
        action["delegated_to"] = agent.id
        return action

    def observe(self, reward: dict[str, Any]) -> None:
        for agent in self.sub_agents:
            agent.observe(reward)
        if self.performance:
            for aid in self.performance:
                self.performance[aid].append(reward.get("score", 0))
        self._maybe_switch()

    def _maybe_switch(self) -> None:
        if len(self.memory) > 0 and len(self.memory) % 5 == 0:
            self.current_idx = (self.current_idx + 1) % len(self.sub_agents)

    def reset(self) -> None:
        super().reset()
        for agent in self.sub_agents:
            agent.reset()
        self.current_idx = 0
        self.performance = {a.id: [] for a in self.sub_agents}


class GW2EfficiencyToolAgent(Agent):
    def __init__(self, name: str = "EfficiencyAgent") -> None:
        super().__init__(id=f"agent:efficiency:{uuid.uuid4().hex[:8]}", name=name, agent_type="efficiency")

    def act(self, state: dict[str, Any]) -> dict[str, Any]:
        market = state.get("market", {})
        inventory = state.get("inventory", {})
        items = sorted(market.items(), key=lambda kv: kv[1].get("price", 0) / max(kv[1].get("supply", 1), 1), reverse=True)
        if items:
            item_id, data = items[0]
            if data.get("demand", 0) > data.get("supply", 0) * 1.1:
                return {"type": "trade", "item_id": item_id, "quantity": 1, "price": data["price"], "tool_used": "efficiency_calc"}
        if inventory.get("mystic_coin", 0) > 0:
            return {"type": "craft", "item_id": "legendary_component", "consumes": {"mystic_coin": 1}, "tool_used": "crafting_opt"}
        return _trader_policy(state)


def create_default_agent_roster() -> list[Agent]:
    return [
        TraderAgent(name="AlphaTrader"),
        CrafterAgent(name="BetaCrafter"),
        RLAgent(name="GammaRL"),
        MetaStrategyAgent(name="DeltaMeta"),
        GW2EfficiencyToolAgent(name="EpsilonEfficiency"),
    ]
