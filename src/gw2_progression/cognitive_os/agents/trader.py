from __future__ import annotations

import random
from typing import Any

from gw2_progression.cognitive_os.agents.base import AgentAction, AgentProfile, BaseAgent


class TraderAgent(BaseAgent):
    """Trading Post specialist — flips items for profit.

    Scans market for spread opportunities, executes buy-low/sell-high.
    Risk-aware: adjusts position size based on volatility.
    """

    def __init__(self, name: str = "Trader", capital: float = 1000.0, risk_tolerance: float = 0.6) -> None:
        super().__init__(AgentProfile(
            name=name,
            agent_type="trader",
            capital=capital,
            risk_tolerance=risk_tolerance,
            specialization="trading_post",
        ))
        self._spread_threshold: float = 0.05

    def set_spread_threshold(self, threshold: float) -> None:
        self._spread_threshold = threshold

    def act(self, world_state: dict[str, Any]) -> AgentAction:
        market = world_state.get("market", {}) or {}
        inventory = world_state.get("inventory", {}) or {}

        candidates: list[tuple[str, float, str]] = []
        for item_id, data in market.items():
            if not isinstance(data, dict):
                continue
            buy = data.get("buy_price") or data.get("price", 0)
            sell = data.get("sell_price") or data.get("price", 0)
            spread = (sell - buy) / max(buy, 1)
            supply = data.get("supply", 0)
            data.get("demand", 0)

            if spread > self._spread_threshold and supply > 0:
                if random.random() < self.profile.risk_tolerance:
                    candidates.append((item_id, spread, "buy"))
            if item_id in inventory and inventory[item_id] > 0:
                if spread > self._spread_threshold * 0.5:
                    candidates.append((item_id, spread, "sell"))

        if not candidates:
            return AgentAction(action_type="trade", item_id="gold", quantity=1)

        candidates.sort(key=lambda x: -x[1])
        item_id, spread, direction = candidates[0]
        quantity = max(1, int(self.profile.capital / max(spread * 100, 10)))
        return AgentAction(
            action_type="trade",
            item_id=item_id,
            quantity=min(quantity, 250),
            params={"direction": direction, "spread": round(spread, 3)},
        )
