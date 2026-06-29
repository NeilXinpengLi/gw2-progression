from __future__ import annotations

from typing import Any

from gw2_progression.cognitive_os.agents.base import AgentAction, AgentProfile, BaseAgent


class OptimizerAgent(BaseAgent):
    """Policy sampler that chooses the highest expected utility action."""

    def __init__(self, name: str = "Optimizer", skill_level: float = 0.9) -> None:
        super().__init__(AgentProfile(
            name=name,
            agent_type="optimizer",
            skill_level=skill_level,
            risk_tolerance=0.45,
            specialization="strategy_optimization",
        ))

    def act(self, world_state: dict[str, Any]) -> AgentAction:
        inventory = world_state.get("inventory", {}) or {}
        market = world_state.get("market", {}) or {}
        gold = float(world_state.get("gold", 0.0) or 0.0)

        best_trade: tuple[str, float] | None = None
        market_items = market.items() if isinstance(market, dict) else []
        for item_id, data in market_items:
            if not isinstance(data, dict):
                continue
            buy = float(data.get("buy_price") or data.get("price") or 0.0)
            sell = float(data.get("sell_price") or data.get("price") or 0.0)
            spread = sell - buy
            if spread > 0 and (best_trade is None or spread > best_trade[1]):
                best_trade = (str(item_id), spread)

        if best_trade and gold > best_trade[1]:
            return AgentAction(
                action_type="trade",
                item_id=best_trade[0],
                quantity=max(1, int(self.profile.skill_level * 3)),
                params={"expected_edge": round(best_trade[1], 3), "policy": "max_expected_value"},
            )

        if inventory:
            item_id, count = max(inventory.items(), key=lambda item: item[1])
            return AgentAction(
                action_type="craft",
                item_id=str(item_id),
                quantity=max(1, min(int(count), 5)),
                params={"policy": "inventory_conversion"},
            )

        return AgentAction(
            action_type="farm",
            item_id="gold",
            quantity=max(1, int(self.profile.skill_level * 4)),
            params={"policy": "bootstrap_capital"},
        )
