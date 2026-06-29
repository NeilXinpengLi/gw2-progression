from __future__ import annotations

import random
from typing import Any

from gw2_progression.cognitive_os.agents.base import AgentAction, AgentProfile, BaseAgent


class CrafterAgent(BaseAgent):
    """Crafting specialist — converts materials into high-value items.

    Prioritizes recipes with highest value-add.
    Checks ingredient availability before committing.
    """

    def __init__(self, name: str = "Crafter", skill_level: float = 0.7, capital: float = 500.0) -> None:
        super().__init__(AgentProfile(
            name=name,
            agent_type="crafter",
            capital=capital,
            skill_level=skill_level,
            specialization="crafting",
        ))
        self._known_recipes: dict[str, dict[str, int]] = {}
        self._recipe_values: dict[str, float] = {}

    def learn_recipe(self, output_item: str, ingredients: dict[str, int], estimated_value: float) -> None:
        self._known_recipes[output_item] = ingredients
        self._recipe_values[output_item] = estimated_value

    def act(self, world_state: dict[str, Any]) -> AgentAction:
        inventory = world_state.get("inventory", {}) or {}

        best_recipe: str | None = None
        best_value = 0.0

        for output_item, ingredients in self._known_recipes.items():
            if all(inventory.get(ing_id, 0) >= count for ing_id, count in ingredients.items()):
                value = self._recipe_values.get(output_item, 0) * self.profile.skill_level
                if value > best_value:
                    best_value = value
                    best_recipe = output_item

        if best_recipe:
            return AgentAction(
                action_type="craft",
                item_id=best_recipe,
                quantity=1,
                params={"ingredients": self._known_recipes[best_recipe], "estimated_value": best_value},
            )

        available_mats = [iid for iid, count in inventory.items() if count > 5 and isinstance(iid, str)]
        if available_mats and random.random() < 0.3:
            mat_id = random.choice(available_mats)
            return AgentAction(
                action_type="gather",
                item_id=mat_id,
                quantity=min(inventory.get(mat_id, 0), 10),
            )

        return AgentAction(action_type="craft", item_id="salvage", quantity=1)
