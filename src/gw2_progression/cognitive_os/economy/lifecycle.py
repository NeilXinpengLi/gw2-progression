from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketItem:
    item_id: str
    supply: float = 100.0
    demand: float = 100.0
    price: float = 100.0
    volatility: float = 0.1
    velocity: float = 1.0
    meta_factor: float = 1.0
    patch_impact: float = 0.0
    crafting_sink: float = 1.0


@dataclass
class EconomicState:
    t: int = 0
    items: dict[str, MarketItem] = field(default_factory=dict)
    total_gold_supply: float = 100000.0
    inflation_rate: float = 0.001
    market_sentiment: float = 0.5


class EconomicLifecycle:
    """Economic lifecycle modeling with supply/demand/meta dynamics.

    price(t) = f(supply, demand, patch, meta)

    Dynamics:
      - supply shocks (new sources, bottling)
      - demand cycles (patch hype, seasonal)
      - meta shifts (balance patches)
      - crafting sinks (legendary demand)
    """

    def __init__(self) -> None:
        self._state = EconomicState()
        self._history: list[EconomicState] = []
        self._patch_schedule: list[dict[str, Any]] = []

    @property
    def state(self) -> EconomicState:
        return self._state

    def register_item(
        self,
        item_id: str,
        initial_price: float = 100.0,
        volatility: float = 0.1,
        meta_factor: float = 1.0,
    ) -> None:
        self._state.items[item_id] = MarketItem(
            item_id=item_id,
            price=initial_price,
            volatility=volatility,
            meta_factor=meta_factor,
        )

    def register_patch(self, name: str, t: int, impact: dict[str, float]) -> None:
        self._patch_schedule.append({
            "name": name,
            "t": t,
            "impact": impact,
        })

    def step(self, dt: int = 1) -> EconomicState:
        for _ in range(dt):
            self._history.append(EconomicState(
                t=self._state.t,
                items={k: MarketItem(**v.__dict__) for k, v in self._state.items.items()},
                total_gold_supply=self._state.total_gold_supply,
                inflation_rate=self._state.inflation_rate,
                market_sentiment=self._state.market_sentiment,
            ))
            self._state.t += 1
            self._apply_inflation()
            self._apply_patches()
            self._apply_supply_demand()
            self._apply_crafting_sinks()
            self._apply_market_sentiment()
        return self._state

    def step_to(self, target_t: int) -> list[EconomicState]:
        steps = []
        while self._state.t < target_t:
            self.step()
            steps.append(EconomicState(**self._state.__dict__))
        return steps

    def _apply_inflation(self) -> None:
        self._state.total_gold_supply *= 1.0 + self._state.inflation_rate
        for item in self._state.items.values():
            item.price *= 1.0 + self._state.inflation_rate * 0.5

    def _apply_patches(self) -> None:
        for patch in self._patch_schedule:
            if patch["t"] == self._state.t:
                for item_id, impact in patch["impact"].items():
                    if item_id in self._state.items:
                        item = self._state.items[item_id]
                        item.patch_impact = impact
                        item.price *= 1.0 + impact
                        item.volatility *= 1.0 + abs(impact) * 2

    def _apply_supply_demand(self) -> None:
        for item in self._state.items.values():
            supply_shock = random.gauss(0, item.volatility * 0.1)
            demand_cycle = math.sin(self._state.t * 0.1) * item.volatility * 0.05
            item.supply *= 1.0 + supply_shock
            item.demand *= 1.0 + demand_cycle

            equilibrium = item.demand / max(item.supply, 0.01)
            target_price = 100.0 * equilibrium * item.meta_factor * (1.0 + item.patch_impact)
            item.price += (target_price - item.price) * 0.1 * item.velocity

    def _apply_crafting_sinks(self) -> None:
        for item in self._state.items.values():
            if item.crafting_sink > 0:
                demand_boost = item.crafting_sink * 0.01
                item.demand *= 1.0 + demand_boost

    def _apply_market_sentiment(self) -> None:
        self._state.market_sentiment = 0.5 + 0.3 * math.sin(self._state.t * 0.05) + random.gauss(0, 0.05)
        self._state.market_sentiment = max(0.0, min(1.0, self._state.market_sentiment))

    def price_forecast(self, item_id: str, horizon: int = 10) -> list[dict[str, float]]:
        forecast: list[dict[str, float]] = []
        temp_item = None
        if item_id in self._state.items:
            original = self._state.items[item_id]
            temp_item = MarketItem(**original.__dict__)

        temp_supply = temp_item.supply if temp_item else 100.0
        temp_demand = temp_item.demand if temp_item else 100.0
        temp_meta = temp_item.meta_factor if temp_item else 1.0
        temp_vol = temp_item.volatility if temp_item else 0.1

        for offset in range(1, horizon + 1):
            d_cycle = math.sin((self._state.t + offset) * 0.1) * temp_vol * 0.05
            temp_demand *= 1.0 + d_cycle
            eq = temp_demand / max(temp_supply, 0.01)
            predicted_price = 100.0 * eq * temp_meta
            forecast.append({
                "t": self._state.t + offset,
                "predicted_price": round(predicted_price, 2),
                "confidence": max(0.1, 1.0 - offset * 0.08),
            })
        return forecast

    def market_health(self) -> dict[str, Any]:
        if not self._state.items:
            return {"health": 0.5, "message": "No items registered"}
        total_volatility = sum(item.volatility for item in self._state.items.values())
        avg_price = sum(item.price for item in self._state.items.values()) / max(len(self._state.items), 1)
        supply_demand_ratio = sum(item.supply for item in self._state.items.values()) / max(
            sum(item.demand for item in self._state.items.values()), 0.01
        )
        health = max(0.0, min(1.0, 1.0 - total_volatility / max(len(self._state.items), 1) * 0.5))
        return {
            "health": round(health, 3),
            "avg_price": round(avg_price, 2),
            "supply_demand_ratio": round(supply_demand_ratio, 3),
            "items_tracked": len(self._state.items),
            "total_gold_supply": round(self._state.total_gold_supply, 0),
            "inflation_rate": self._state.inflation_rate,
            "market_sentiment": round(self._state.market_sentiment, 3),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "t": self._state.t,
            "items": {k: {
                "supply": round(v.supply, 1),
                "demand": round(v.demand, 1),
                "price": round(v.price, 2),
                "volatility": round(v.volatility, 3),
                "meta_factor": v.meta_factor,
            } for k, v in self._state.items.items()},
            "market_health": self.market_health(),
            "forecast": {item_id: self.price_forecast(item_id, 5) for item_id in list(self._state.items.keys())[:5]},
        }
