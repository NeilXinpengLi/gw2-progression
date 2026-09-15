from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass
class CompetitiveItem:
    id: str
    price: float = 100.0
    supply: float = 100.0
    demand: float = 100.0
    velocity: float = 1.0
    owner: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "price": self.price,
            "supply": self.supply,
            "demand": self.demand,
            "velocity": self.velocity,
            "owner": self.owner,
        }


class EconomyEngine:
    def __init__(self, seed: int = 1) -> None:
        self.seed = seed
        self._rng = random.Random(seed)
        self.items: dict[str, CompetitiveItem] = {}
        self._init_items()

    def _init_items(self) -> None:
        base_items = ["mystic_coin", "ecto", "magnetite_shard", "legendary_component", "skin_unlock", "glob_of_ectoplasm", "obsidian_shard"]
        for item_id in base_items:
            self.items[item_id] = CompetitiveItem(
                id=item_id,
                price=round(50 + self._rng.random() * 200, 2),
                supply=50 + self._rng.random() * 100,
                demand=50 + self._rng.random() * 100,
                velocity=0.5 + self._rng.random() * 2,
            )

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            self.seed = seed
        self._rng = random.Random(self.seed)
        self.items.clear()
        self._init_items()

    def update_price(self, item_id: str | None = None) -> dict[str, float]:
        if item_id:
            targets = [self.items[item_id]]
        else:
            targets = list(self.items.values())
        results = {}
        for item in targets:
            delta = (item.demand - item.supply) * 0.02
            item.price = max(0.01, round(item.price + delta, 2))
            item.velocity = round(max(item.velocity * 0.97 + abs(delta) * 0.5, 0), 3)
            item.demand = round(max(item.demand * 0.995, 0), 3)
            item.supply = round(max(item.supply * 0.995, 0), 3)
            results[item.id] = item.to_dict()
        return results

    def apply_trade(self, item_id: str, quantity: int, buyer: str | None = None, seller: str | None = None) -> dict[str, Any]:
        item = self.items.get(item_id)
        if not item:
            return {"error": f"item {item_id} not found"}
        item.demand += quantity
        item.velocity += 0.05 * quantity
        if seller:
            item.owner = seller
        self.update_price(item_id)
        return {
            "item": item.to_dict(),
            "quantity": quantity,
            "buyer": buyer,
            "seller": seller,
        }

    def apply_craft(self, item_id: str, consumes: dict[str, int], crafter: str | None = None) -> dict[str, Any]:
        item = self.items.get(item_id)
        if not item:
            return {"error": f"item {item_id} not found"}
        for consumed_id, qty in consumes.items():
            consumed = self.items.get(consumed_id)
            if consumed:
                consumed.demand += qty * 2
                self.update_price(consumed_id)
        item.supply += 1
        item.owner = crafter
        self.update_price(item_id)
        return {"item": item.to_dict(), "consumed": dict(consumes), "crafter": crafter}

    def apply_farm(self, item_id: str, quantity: int, farmer: str | None = None) -> dict[str, Any]:
        item = self.items.get(item_id)
        if not item:
            return {"error": f"item {item_id} not found"}
        item.supply += quantity * 2
        item.owner = farmer
        self.update_price(item_id)
        return {"item": item.to_dict(), "quantity": quantity, "farmer": farmer}

    def market_snapshot(self) -> dict[str, Any]:
        return {item_id: item.to_dict() for item_id, item in self.items.items()}

    def competitive_score(self, agent_id: str, actions: list[dict[str, Any]]) -> float:
        impact = 0.0
        for action in actions:
            item_id = action.get("item_id")
            if item_id and item_id in self.items:
                item = self.items[item_id]
                impact += abs(item.velocity - 1.0) * 0.1
                impact += max(0, item.price - 100) * 0.01
        return round(impact, 4)
