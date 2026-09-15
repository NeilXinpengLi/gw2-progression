from __future__ import annotations

from typing import Any


class EconomyRules:
    def __init__(self, price_floor: float = 1.0, volatility_cap: float = 0.3) -> None:
        self.price_floor = price_floor
        self.volatility_cap = volatility_cap

    def validate_price(self, item_id: str, price: float, market: dict[str, Any] | None = None) -> dict[str, Any]:
        if price < self.price_floor:
            return {"valid": False, "reason": f"Price {price} below floor {self.price_floor}", "item_id": item_id}
        if market and item_id in market:
            historical = market[item_id].get("historical_price", price)
            if historical > 0:
                change = abs(price - historical) / historical
                if change > self.volatility_cap:
                    return {"valid": False, "reason": f"Price change {change:.1%} exceeds cap {self.volatility_cap:.1%}", "item_id": item_id}
        return {"valid": True, "reason": "ok", "item_id": item_id}

    def validate_trade(self, buy_price: float, sell_price: float, quantity: int, market: dict[str, Any] | None = None) -> dict[str, Any]:
        if buy_price <= 0 or sell_price <= 0:
            return {"valid": False, "reason": "Invalid price"}
        if buy_price >= sell_price:
            return {"valid": False, "reason": f"Buy price {buy_price} >= sell price {sell_price}"}
        spread = sell_price - buy_price
        spread_pct = spread / buy_price if buy_price > 0 else 0
        if spread_pct < 0.05:
            return {"valid": False, "reason": f"Spread {spread_pct:.1%} too low"}
        return {"valid": True, "reason": "ok", "spread": round(spread, 2), "spread_pct": round(spread_pct, 4)}

    def validate_economy_state(self, state: dict[str, Any]) -> dict[str, Any]:
        market = state.get("market", {})
        total_supply = sum(v.get("supply", 0) for v in market.values())
        total_demand = sum(v.get("demand", 0) for v in market.values())
        avg_price = sum(v.get("price", 0) for v in market.values()) / max(len(market), 1)
        high_volatility = sum(1 for v in market.values() if v.get("velocity", 0) > 2)
        return {
            "valid": total_supply > 0 and total_demand > 0 and avg_price >= self.price_floor,
            "supply": total_supply,
            "demand": total_demand,
            "avg_price": round(avg_price, 2),
            "high_volatility_items": high_volatility,
        }

    def price_trend(self, item_id: str, market: dict[str, Any]) -> str:
        item = market.get(item_id)
        if not item:
            return "unknown"
        supply = item.get("supply", 100)
        demand = item.get("demand", 100)
        if demand > supply * 1.2:
            return "up"
        elif supply > demand * 1.2:
            return "down"
        return "stable"

    def is_market_stable(self, market: dict[str, Any]) -> bool:
        if not market:
            return True
        volatile = sum(1 for v in market.values() if v.get("velocity", 0) > 2)
        return volatile / len(market) < 0.3
