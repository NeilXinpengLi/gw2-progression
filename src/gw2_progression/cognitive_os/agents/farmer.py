from __future__ import annotations

from typing import Any

from gw2_progression.cognitive_os.agents.base import AgentAction, AgentProfile, BaseAgent


class FarmerAgent(BaseAgent):
    """Resource acquisition specialist over farming and gathering loops."""

    def __init__(self, name: str = "Farmer", efficiency: float = 0.75) -> None:
        super().__init__(AgentProfile(
            name=name,
            agent_type="farmer",
            skill_level=efficiency,
            risk_tolerance=0.35,
            specialization="resource_farming",
        ))
        self._preferred_targets = ["gold", "ore", "wood", "volatile_magic", "mystic_coin"]

    def act(self, world_state: dict[str, Any]) -> AgentAction:
        inventory = world_state.get("inventory", {}) or {}
        market = world_state.get("market", {}) or {}

        target = "gold"
        best_score = 0.0
        for item_id in self._preferred_targets:
            market_data = market.get(item_id, {}) if isinstance(market, dict) else {}
            price = float(market_data.get("sell_price") or market_data.get("price") or 1.0)
            scarcity = 1.0 / max(float(inventory.get(item_id, 0) or 0) + 1.0, 1.0)
            score = price * scarcity
            if score > best_score:
                best_score = score
                target = item_id

        return AgentAction(
            action_type="farm",
            item_id=target,
            quantity=max(1, int(self.profile.skill_level * 6)),
            params={"source": "open_world", "score": round(best_score, 3)},
        )
