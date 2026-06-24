"""v4 Economic Model — pricing, liquidity, volatility, and crafting economics."""

from dataclasses import dataclass


@dataclass
class PricePoint:
    buy_price: int = 0
    sell_price: int = 0
    buy_qty: int = 0
    sell_qty: int = 0

    @property
    def mid_price(self) -> float:
        return (self.buy_price + self.sell_price) / 2 if self.buy_price or self.sell_price else 0

    @property
    def spread(self) -> int:
        return self.sell_price - self.buy_price

    @property
    def spread_ratio(self) -> float:
        return round(self.spread / max(self.sell_price, 1), 4)

    @property
    def liquidity_score(self) -> str:
        total = self.buy_qty + self.sell_qty
        if total >= 5000:
            return "high"
        if total >= 500:
            return "medium"
        if total > 0:
            return "low"
        return "illiquid"

    @property
    def sell_after_fee(self) -> int:
        return int(self.sell_price * 0.85)


@dataclass
class CraftCost:
    total_buy_cost: int = 0
    total_craft_cost: int = 0
    sell_price: int = 0

    @property
    def profit_if_craft(self) -> int:
        return int(self.sell_price * 0.85) - self.total_craft_cost

    @property
    def profit_if_buy(self) -> int:
        return int(self.sell_price * 0.85) - self.total_buy_cost

    @property
    def craft_margin_pct(self) -> float:
        return round(self.profit_if_craft / max(self.total_craft_cost, 1) * 100, 1)


STRATEGIES = {
    "gold": {
        "name": "Gold Farming",
        "desc": "Maximize gold per hour — prioritize high-liquidity, high-ROI actions",
        "weights": {"gold": 0.6, "build": 0.1, "legendary": 0.1, "time": -0.3, "risk": -0.1},
    },
    "build": {
        "name": "Build Completion",
        "desc": "Prioritize acquiring missing gear and completing builds",
        "weights": {"gold": 0.1, "build": 0.7, "legendary": 0.1, "time": -0.2, "risk": -0.1},
    },
    "legendary": {
        "name": "Legendary Rush",
        "desc": "Minimize time to complete legendary weapons and gear",
        "weights": {"gold": 0.1, "build": 0.1, "legendary": 0.6, "time": -0.3, "risk": -0.1},
    },
    "hybrid": {
        "name": "Balanced",
        "desc": "Balanced progression across gold, builds, and legendaries",
        "weights": {"gold": 0.3, "build": 0.3, "legendary": 0.3, "time": -0.2, "risk": -0.05},
    },
}


def score_action(action: dict, price: PricePoint | None, strategy: str) -> dict:
    """Score a single action with full explainable breakdown."""
    weights = STRATEGIES.get(strategy, STRATEGIES["hybrid"])["weights"]
    reward_copper = abs(action.get("reward_copper", 0))
    build_impact = action.get("build_impact", 0)
    legendary_impact = action.get("legendary_impact", 0)
    time_cost = action.get("time_cost_minutes", 0)
    risk = action.get("risk", 0.5)

    gold_score = min(reward_copper / 10000 / 100, 1.0) if reward_copper > 0 else 0
    time_score = max(0, 1 - time_cost / 120) if time_cost > 0 else 0.5
    liquidity_bonus = {"high": 0.2, "medium": 0.1, "low": 0, "illiquid": -0.1}.get(price.liquidity_score if price else "medium", 0) if price else 0

    final = gold_score * weights["gold"] + build_impact * weights["build"] + legendary_impact * weights["legendary"] + time_score * weights["time"] - risk * weights["risk"] + liquidity_bonus * 0.1

    return {
        "final_score": round(final, 3),
        "breakdown": {
            "gold_score": round(gold_score, 3),
            "build_impact": round(build_impact, 3),
            "legendary_impact": round(legendary_impact, 3),
            "time_efficiency": round(time_score, 3),
            "liquidity_bonus": round(liquidity_bonus, 3),
            "risk_penalty": round(risk * weights["risk"], 3),
        },
        "strategy": strategy,
        "weights": weights,
    }
