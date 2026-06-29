from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Dependency:
    entity_id: str
    entity_type: str
    required_by: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "required_by": list(self.required_by),
            "requires": list(self.requires),
            "properties": dict(self.properties),
            "resolved": self.resolved,
        }


class DependencySolver:
    def __init__(self) -> None:
        self.dependencies: dict[str, Dependency] = {}

    def register(self, entity_id: str, entity_type: str, requires: list[str] | None = None, properties: dict[str, Any] | None = None) -> Dependency:
        dep = Dependency(
            entity_id=entity_id,
            entity_type=entity_type,
            requires=requires or [],
            properties=properties or {},
        )
        self.dependencies[entity_id] = dep
        for req_id in dep.requires:
            if req_id not in self.dependencies:
                self.dependencies[req_id] = Dependency(entity_id=req_id, entity_type="unknown")
            self.dependencies[req_id].required_by.append(entity_id)
        return dep

    def get_dependency(self, entity_id: str) -> Dependency | None:
        return self.dependencies.get(entity_id)

    def resolve(self, entity_id: str) -> list[Dependency]:
        chain: list[Dependency] = []
        visited: set[str] = set()
        current_id = entity_id
        while current_id and current_id not in visited:
            visited.add(current_id)
            dep = self.dependencies.get(current_id)
            if not dep:
                break
            chain.append(dep)
            if dep.requires:
                current_id = dep.requires[0]
            else:
                break
        for d in chain:
            d.resolved = True
        return chain

    def resolve_all(self, entity_ids: list[str]) -> dict[str, list[Dependency]]:
        return {eid: self.resolve(eid) for eid in entity_ids}

    def has_dependency(self, entity_id: str) -> bool:
        dep = self.dependencies.get(entity_id)
        return bool(dep and dep.requires)

    def register_account_dependencies(self) -> None:
        self.register("legendary_weapon", "crafting", requires=["gift_of_mastery", "gift_of_fortune", "precursor"])
        self.register("gift_of_mastery", "currency", requires=["gift_of_exploration", "gift_of_battle"])
        self.register("gift_of_exploration", "achievement", requires=["world_completion"])
        self.register("gift_of_battle", "achievement", requires=["wvw_rank"])
        self.register("gift_of_fortune", "currency", requires=["mystic_clover", "mystic_coin", "ectoplasm"])
        self.register("mystic_clover", "currency", requires=["mystic_coin"])
        self.register("mystic_coin", "material")
        self.register("ectoplasm", "material")
        self.register("precursor", "weapon", requires=["mystic_coin", "ectoplasm"])
        self.register("ascended_armor", "crafting", requires=["ascended_insignia", "vision_crystal", "damask"])
        self.register("ascended_insignia", "crafting", requires=["damask", "spiritwood"])
        self.register("damask", "material")
        self.register("spiritwood", "material")
        self.register("vision_crystal", "currency", requires=["mystic_coin", "ectoplasm"])

    def register_from_recipe(self, output_item_id: int, ingredient_map: dict[int, int]) -> None:
        """Register a real GW2 recipe as a dependency chain."""
        oid_str = str(output_item_id)
        requires = [str(iid) for iid in ingredient_map]
        self.register(oid_str, "crafting", requires=requires)
        for ing_id, ing_count in ingredient_map.items():
            iid_str = str(ing_id)
            existing = self.get_dependency(iid_str)
            if not existing:
                self.register(iid_str, "material", properties={"count": ing_count})
            else:
                existing.properties["count"] = existing.properties.get("count", 1) + ing_count
            if oid_str not in self.dependencies[iid_str].required_by:
                self.dependencies[iid_str].required_by.append(oid_str)

    def register_real_recipes(self, recipe_data: dict[int, dict[int, int]]) -> None:
        """Batch register real recipes from API data.

        recipe_data: {output_item_id: {ingredient_item_id: count, ...}, ...}
        """
        for output_id, ingredients in recipe_data.items():
            self.register_from_recipe(output_id, ingredients)

    def register_real_recipes_from_resolver(self, resolver: Any, item_ids: list[int]) -> int:
        """Fetch recipes from RecipeResolver and register them."""
        registered = 0
        for iid in item_ids:
            if self.has_dependency(str(iid)):
                continue
            ingredients = resolver.get_ingredients(iid)
            if ingredients:
                self.register_from_recipe(iid, ingredients)
                registered += 1
        return registered

    def to_dict(self) -> dict[str, Any]:
        return {eid: dep.to_dict() for eid, dep in self.dependencies.items()}
