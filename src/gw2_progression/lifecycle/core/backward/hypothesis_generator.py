from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from gw2_progression.lifecycle.core.backward.dependency_solver import DependencySolver


@dataclass
class Hypothesis:
    steps: list[dict[str, Any]]
    probability: float = 0.5
    economy_likelihood: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


STEP_TEMPLATES = [
    {"type": "farm", "item_id": "magnetite_shard", "quantity": 3, "duration_days": 1},
    {"type": "trade", "item_id": "mystic_coin", "quantity": 5, "price_min": 80, "price_max": 120},
    {"type": "craft", "item_id": "legendary_component", "consumes": {"mystic_coin": 1}, "duration_days": 2},
    {"type": "flip", "item_id": "ecto", "quantity": 10, "spread": 5},
    {"type": "collect", "item_id": "skin_unlock", "quantity": 1},
    {"type": "achievement", "item_id": "world_completion", "progress": 10},
    {"type": "craft", "item_id": "ascended_armor", "consumes": {"damask": 3, "spiritwood": 2}, "duration_days": 3},
    {"type": "gather", "item_id": "ore_node", "quantity": 20},
]


CATEGORY_ACTIONS: dict[str, list[dict[str, Any]]] = {
    "equipment": [
        {"type": "craft", "consumes": {}, "duration_days": 3},
        {"type": "trade", "quantity": 1, "price_min": 50, "price_max": 500},
        {"type": "collect", "quantity": 1},
    ],
    "material": [
        {"type": "farm", "quantity": 5, "duration_days": 1},
        {"type": "gather", "quantity": 20},
        {"type": "trade", "quantity": 10, "price_min": 1, "price_max": 50},
    ],
    "consumable": [
        {"type": "trade", "quantity": 5, "price_min": 5, "price_max": 100},
        {"type": "farm", "quantity": 3, "duration_days": 1},
    ],
    "tool": [
        {"type": "trade", "quantity": 1, "price_min": 50, "price_max": 300},
        {"type": "collect", "quantity": 1},
    ],
    "container": [
        {"type": "collect", "quantity": 1},
        {"type": "trade", "quantity": 1, "price_min": 10, "price_max": 200},
    ],
    "upgrade": [
        {"type": "craft", "consumes": {}, "duration_days": 2},
        {"type": "trade", "quantity": 1, "price_min": 20, "price_max": 300},
    ],
    "cosmetic": [
        {"type": "collect", "quantity": 1},
        {"type": "achievement", "progress": 100},
    ],
    "special": [
        {"type": "collect", "quantity": 1},
        {"type": "achievement", "progress": 50},
    ],
}


class HypothesisGenerator:
    CRAFT_CATEGORIES = frozenset({"equipment", "upgrade"})

    def __init__(self, dependency_solver: DependencySolver | None = None) -> None:
        self.solver = dependency_solver or DependencySolver()
        self.solver.register_account_dependencies()
        self._rng = random.Random(1)
        self._categorizer: Any = None
        self._recipe_resolver: Any = None

    def _lazy_categorizer(self) -> Any:
        if self._categorizer is None:
            from gw2_progression.lifecycle.core.utils.item_categorizer import get_categorizer
            self._categorizer = get_categorizer()
        return self._categorizer

    def _lazy_recipe_resolver(self) -> Any:
        if self._recipe_resolver is None:
            from gw2_progression.lifecycle.core.utils.recipe_resolver import get_recipe_resolver
            self._recipe_resolver = get_recipe_resolver()
        return self._recipe_resolver

    def generate(self, current_state: dict[str, Any], max_depth: int = 10, count: int = 5) -> list[Hypothesis]:
        state_items = set(current_state.get("items", []))
        state_inventory = current_state.get("inventory", {})
        state_achievements = current_state.get("achievements", [])
        hypotheses: list[Hypothesis] = []

        for _ in range(count):
            steps = self._generate_steps_from_inventory(state_inventory, state_achievements, max_depth)
            if not steps:
                steps = self._generate_steps(state_items, state_inventory, state_achievements, max_depth)
            if steps:
                prob = self._estimate_probability(steps, state_items)
                eco = self._estimate_economy_likelihood(steps)
                hypotheses.append(Hypothesis(steps=steps, probability=prob, economy_likelihood=eco))
        return hypotheses

    def _weighted_choice(self, items: list[int], weights: list[float]) -> int | None:
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        total = sum(weights)
        if total <= 0:
            return self._rng.choice(items)
        r = self._rng.uniform(0, total)
        cumulative = 0.0
        for i, w in zip(items, weights):
            cumulative += w
            if r <= cumulative:
                return i
        return items[-1]

    def generate_for_item(self, item_id: str, current_state: dict[str, Any], max_depth: int = 5) -> list[Hypothesis]:
        chain = self.solver.resolve(item_id)
        steps: list[dict[str, Any]] = []
        for dep in chain:
            if dep.entity_type == "crafting":
                steps.append({"type": "craft", "item_id": dep.entity_id, "consumes": {r: 1 for r in dep.requires}, "duration_days": 2})
            elif dep.entity_type == "currency":
                steps.append({"type": "farm", "item_id": dep.entity_id, "quantity": 10, "duration_days": 1})
            elif dep.entity_type == "achievement":
                steps.append({"type": "achievement", "item_id": dep.entity_id, "progress": 100})
            else:
                steps.append({"type": "collect", "item_id": dep.entity_id, "quantity": 5})
        if not steps:
            return []
        prob = self._estimate_probability(steps, set(current_state.get("items", [])))
        eco = self._estimate_economy_likelihood(steps)
        return [Hypothesis(steps=steps, probability=prob, economy_likelihood=eco)]

    def _generate_steps_from_inventory(self, inventory: dict[str, int], achievements: list, max_depth: int) -> list[dict[str, Any]]:
        if not inventory:
            return []
        numeric_ids = [int(iid) for iid in inventory if iid.isdigit()]
        if not numeric_ids:
            return []
        categorizer = self._lazy_categorizer()
        import asyncio
        try:
            asyncio.run(categorizer.fetch_batch(numeric_ids[:200]))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(categorizer.fetch_batch(numeric_ids[:200]))
            loop.close()
        classified = categorizer.classify_items(numeric_ids)
        steps: list[dict[str, Any]] = []
        categories_present = [c for c in classified if classified[c]]
        if not categories_present:
            return []

        cat_order = sorted(categories_present, key=lambda c: len(classified[c]), reverse=True)
        step_count = min(max_depth, max(3, sum(len(classified[c]) for c in cat_order) // 5))

        used_ids: set[int] = set()
        for cat in cat_order:
            cat_ids = classified[cat]
            available = [iid for iid in cat_ids if iid not in used_ids]
            if not available:
                continue
            weights = [float(inventory.get(str(iid), 1)) for iid in available]
            chosen_id = self._weighted_choice(available, weights)
            if chosen_id is None:
                continue
            used_ids.add(chosen_id)
            count = inventory.get(str(chosen_id), 1)

            action_templates = CATEGORY_ACTIONS.get(cat, [{"type": "collect", "quantity": 1}])
            if cat in self.CRAFT_CATEGORIES and self._lazy_recipe_resolver().has_recipe(chosen_id):
                template = deepcopy(action_templates[0])
                template["type"] = "craft"
            else:
                template = deepcopy(self._rng.choice(action_templates))
            template["item_id"] = str(chosen_id)
            template["quantity"] = template.get("quantity", 1)
            if template["type"] in ("farm", "gather"):
                template["quantity"] = max(1, count // 2)
            elif template["type"] == "trade":
                template["quantity"] = max(1, count // 4)
            if template.get("type") == "craft":
                recipe_resolver = self._lazy_recipe_resolver()
                real_ingredients = recipe_resolver.get_ingredients(chosen_id)
                if real_ingredients:
                    template["consumes"] = {str(iid): ing_count for iid, ing_count in real_ingredients.items()}
                    template["recipe_sourced"] = True
                    template["produced_quantity"] = recipe_resolver.get_recipes(chosen_id)[0].output_count if recipe_resolver.get_recipes(chosen_id) else 1
                    self.solver.register_from_recipe(chosen_id, real_ingredients)
                else:
                    candidate_ids = classified.get("material", []) + classified.get("consumable", [])
                    consumed_ids = self._rng.sample(candidate_ids, min(2, len(candidate_ids)))
                    template["consumes"] = {str(cid): self._rng.randint(1, 5) for cid in consumed_ids} if consumed_ids else {}
            template["id"] = f"step:{self._rng.randint(1000, 9999)}"
            steps.append(template)

            if len(steps) >= step_count:
                break

        if len(steps) < 2 and categories_present:
            cat = cat_order[0]
            if classified[cat]:
                extra_id = self._weighted_choice(classified[cat], [float(inventory.get(str(iid), 1)) for iid in classified[cat]])
                if extra_id is not None and extra_id not in used_ids:
                    steps.append({
                        "type": "collect",
                        "item_id": str(extra_id),
                        "quantity": 1,
                        "id": f"step:{self._rng.randint(1000, 9999)}",
                    })
        return steps

    def _generate_steps(self, state_items: set, state_inventory: dict, state_achievements: list, max_depth: int) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = []
        for _ in range(min(max_depth, self._rng.randint(2, 6))):
            template = deepcopy(self._rng.choice(STEP_TEMPLATES))
            template["id"] = f"step:{self._rng.randint(1000, 9999)}"
            steps.append(template)
        return steps

    def _estimate_probability(self, steps: list[dict[str, Any]], state_items: set) -> float:
        if not steps:
            return 0.0
        base = 0.7
        variety = min(len(set(s["type"] for s in steps)) / 5, 1.0)
        item_overlap = sum(1 for s in steps if s.get("item_id", "") in state_items) / max(len(steps), 1)
        return round(base * 0.4 + variety * 0.3 + item_overlap * 0.3, 4)

    def _estimate_economy_likelihood(self, steps: list[dict[str, Any]]) -> float:
        if not steps:
            return 0.0
        trade_steps = sum(1 for s in steps if s["type"] in ("trade", "flip"))
        craft_steps = sum(1 for s in steps if s["type"] == "craft")
        trade_factor = min(trade_steps / max(len(steps), 1), 0.5)
        craft_factor = min(craft_steps / max(len(steps), 1), 0.5)
        return round(0.3 + trade_factor + craft_factor, 4)
