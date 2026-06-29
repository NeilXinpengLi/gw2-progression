from __future__ import annotations

from typing import Any

from gw2_progression.lifecycle.core.rules.crafting_rules import CraftingRules
from gw2_progression.lifecycle.core.rules.economy_rules import EconomyRules


class DGSKConstraints:
    def __init__(self, crafting: CraftingRules | None = None, economy: EconomyRules | None = None) -> None:
        self.crafting = crafting or CraftingRules()
        self.economy = economy or EconomyRules()

    def validate(self, state: dict[str, Any]) -> bool:
        return (
            self.check_crafting(state)
            and self.check_economy(state)
            and self.check_consistency(state)
        )

    def validate_detailed(self, state: dict[str, Any]) -> dict[str, Any]:
        crafting_result = self.crafting.validate_crafting_state(state)
        economy_result = self.economy.validate_economy_state(state)
        consistency = self.check_consistency(state)
        return {
            "valid": crafting_result["valid"] and economy_result["valid"] and consistency,
            "crafting": crafting_result,
            "economy": economy_result,
            "consistency": consistency,
        }

    def check_crafting(self, state: dict[str, Any]) -> bool:
        inventory = state.get("inventory", {})
        return all(qty >= 0 for qty in inventory.values())

    def check_economy(self, state: dict[str, Any]) -> bool:
        return self.economy.validate_economy_state(state)["valid"]

    def check_consistency(self, state: dict[str, Any]) -> bool:
        inventory = state.get("inventory", {})
        market = state.get("market", {})
        for item_id, qty in inventory.items():
            if qty < 0:
                return False
        for item_id, data in market.items():
            if data.get("price", 0) < 0 or data.get("supply", 0) < 0 or data.get("demand", 0) < 0:
                return False
        return True

    def check_build(self, state: dict[str, Any]) -> bool:
        equipment = state.get("equipment", {})
        if not equipment:
            return True
        required_slots = ["weapon", "armor", "accessory"]
        return all(slot in equipment for slot in required_slots) if equipment else True

    def is_terminal(self, state: dict[str, Any]) -> bool:
        goal_items = state.get("goal_items", [])
        inventory = state.get("inventory", {})
        if not goal_items:
            return False
        return all(item in inventory and inventory[item] > 0 for item in goal_items)
