from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CraftingRecipe:
    id: str
    name: str
    output_item: str
    output_count: int = 1
    ingredients: dict[str, int] = field(default_factory=dict)
    required_rating: int = 0
    required_profession: str = ""
    discipline: str = ""


RECIPES: dict[str, CraftingRecipe] = {
    "legendary_component": CraftingRecipe(
        id="legendary_component", name="Legendary Component",
        output_item="legendary_component", ingredients={"mystic_coin": 1, "ectoplasm": 2},
        required_rating=400, discipline="mystic_forge",
    ),
    "gift_of_mastery": CraftingRecipe(
        id="gift_of_mastery", name="Gift of Mastery",
        output_item="gift_of_mastery", ingredients={"gift_of_exploration": 1, "gift_of_battle": 1},
    ),
    "gift_of_fortune": CraftingRecipe(
        id="gift_of_fortune", name="Gift of Fortune",
        output_item="gift_of_fortune", ingredients={"mystic_clover": 1, "mystic_coin": 10, "ectoplasm": 10},
    ),
    "ascended_armor": CraftingRecipe(
        id="ascended_armor", name="Ascended Armor",
        output_item="ascended_armor", ingredients={"damask": 3, "spiritwood": 2, "vision_crystal": 1},
        required_rating=500, discipline="armorsmith",
    ),
    "ascended_insignia": CraftingRecipe(
        id="ascended_insignia", name="Ascended Insignia",
        output_item="ascended_insignia", ingredients={"damask": 2, "spiritwood": 1},
        required_rating=450, discipline="tailor",
    ),
    "vision_crystal": CraftingRecipe(
        id="vision_crystal", name="Vision Crystal",
        output_item="vision_crystal", ingredients={"mystic_coin": 5, "ectoplasm": 3},
    ),
}


class CraftingRules:
    def __init__(self, recipes: dict[str, CraftingRecipe] | None = None) -> None:
        self.recipes = recipes or RECIPES

    def can_craft(self, inventory: dict[str, int], recipe_id: str) -> bool:
        recipe = self.recipes.get(recipe_id)
        if not recipe:
            return False
        for ing_id, qty in recipe.ingredients.items():
            if inventory.get(ing_id, 0) < qty:
                return False
        return True

    def craft(self, inventory: dict[str, int], recipe_id: str) -> dict[str, Any]:
        recipe = self.recipes.get(recipe_id)
        if not recipe:
            return {"success": False, "reason": f"Recipe {recipe_id} not found"}
        if not self.can_craft(inventory, recipe_id):
            return {"success": False, "reason": "Missing ingredients"}
        consumed: dict[str, int] = {}
        for ing_id, qty in recipe.ingredients.items():
            inventory[ing_id] = inventory.get(ing_id, 0) - qty
            if inventory[ing_id] <= 0:
                del inventory[ing_id]
            consumed[ing_id] = qty
        inventory[recipe.output_item] = inventory.get(recipe.output_item, 0) + recipe.output_count
        return {
            "success": True,
            "output": recipe.output_item,
            "count": recipe.output_count,
            "consumed": consumed,
            "inventory_after": dict(inventory),
        }

    def reverse_craft(self, output_item: str, count: int = 1) -> dict[str, Any] | None:
        for recipe_id, recipe in self.recipes.items():
            if recipe.output_item == output_item and count >= recipe.output_count:
                return {
                    "recipe_id": recipe_id,
                    "ingredients": dict(recipe.ingredients),
                    "output_count": recipe.output_count,
                    "required_rating": recipe.required_rating,
                    "discipline": recipe.discipline,
                }
        return None

    def get_crafting_chain(self, target_item: str, inventory: dict[str, int] | None = None) -> list[dict[str, Any]]:
        chain: list[dict[str, Any]] = []
        visited: set[str] = set()
        queue = [target_item]
        while queue:
            item = queue.pop(0)
            if item in visited:
                continue
            visited.add(item)
            recipe = None
            for rid, r in self.recipes.items():
                if r.output_item == item:
                    recipe = (rid, r)
                    break
            if recipe:
                rid, r = recipe
                chain.append({
                    "item": item,
                    "recipe_id": rid,
                    "ingredients": dict(r.ingredients),
                    "can_craft": self.can_craft(inventory or {}, rid),
                })
                for ing_id in r.ingredients:
                    queue.append(ing_id)
        return chain

    def validate_crafting_state(self, state: dict[str, Any]) -> dict[str, Any]:
        inventory = state.get("inventory", {})
        valid = True
        messages: list[str] = []
        for recipe_id, recipe in self.recipes.items():
            if not self.can_craft(inventory, recipe_id):
                needed = {k: v for k, v in recipe.ingredients.items() if inventory.get(k, 0) < v}
                if needed:
                    valid = False
                    messages.append(f"Missing {needed} for {recipe.name}")
        return {"valid": valid, "messages": messages}
