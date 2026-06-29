from __future__ import annotations

from copy import deepcopy
from typing import Any

from gw2_progression.lifecycle.core.forward.state_evolver import StateEvolver
from gw2_progression.lifecycle.core.rules.dgsk_constraints import DGSKConstraints


class OOSKSimulator:
    def __init__(self, evolver: StateEvolver | None = None, constraints: DGSKConstraints | None = None) -> None:
        self.evolver = evolver or StateEvolver()
        self.constraints = constraints or DGSKConstraints()

    def simulate(self, state: dict[str, Any], steps: int = 10) -> list[dict[str, Any]]:
        trajectory: list[dict[str, Any]] = [deepcopy(state)]
        current = deepcopy(state)
        for _ in range(steps):
            action = self._select_action(current)
            current = self.evolver.evolve(current, action)
            trajectory.append(deepcopy(current))
            if self.constraints.is_terminal(current):
                break
        return trajectory

    def simulate_with_actions(self, state: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        trajectory = [deepcopy(state)]
        current = deepcopy(state)
        for action in actions:
            current = self.evolver.evolve(current, action)
            trajectory.append(deepcopy(current))
        return trajectory

    def simulate_branching(self, state: dict[str, Any], steps: int = 5, branches: int = 3) -> list[list[dict[str, Any]]]:
        trajectories: list[list[dict[str, Any]]] = []
        for _ in range(branches):
            traj = self.simulate(state, steps=steps)
            trajectories.append(traj)
        return trajectories

    def _select_action(self, state: dict[str, Any]) -> dict[str, Any]:
        inventory = state.get("inventory", {})
        market = state.get("market", {})
        if inventory.get("mystic_coin", 0) >= 1:
            return {"type": "craft", "item_id": "legendary_component", "consumes": {"mystic_coin": 1}}
        if market and any(v.get("price", 100) < 120 for v in market.values()):
            cheap_items = [k for k, v in market.items() if v.get("price", 100) < 120]
            if cheap_items:
                return {"type": "trade", "item_id": cheap_items[0], "quantity": 1, "price": market[cheap_items[0]]["price"]}
        return {"type": "farm", "item_id": "magnetite_shard", "quantity": 3}
