from __future__ import annotations

from typing import Any

from gw2_progression.data_acquisition.registry.source_registry import SourceConfig


class VerticalExpander:
    """Vertical Expansion — build dependency trees for entities.

    Example: given a recipe, discover its material dependencies
    and the sub-recipes needed to craft them.
    """

    def expand(self, data: dict[str, Any], source: SourceConfig) -> dict[str, Any]:
        entities = data.get("entities", [])
        new_entities = list(entities)
        new_relations: list[dict[str, Any]] = list(data.get("relations", []))

        for entity in entities:
            etype = entity.get("type", "")
            if etype == "recipe":
                props = entity.get("properties", {})
                ingredients = props.get("ingredients", []) if isinstance(props.get("ingredients", []), list) else []
                new_entities.append({
                    "id": f"sub_dep:{entity['id']}",
                    "type": "dependency_tree",
                    "name": f"Dependencies for {entity.get('name', '')}",
                    "properties": {"parent": entity["id"], "depth": 1, "ingredient_count": len(ingredients)},
                    "source": data.get("source", source.id),
                })
                new_relations.append({
                    "source": entity["id"],
                    "target": f"sub_dep:{entity['id']}",
                    "relation": "depends_on",
                    "confidence": 0.9,
                })
                output_item_id = props.get("output_item_id")
                if output_item_id is not None:
                    new_relations.append({
                        "source": entity["id"],
                        "target": f"item:{output_item_id}",
                        "relation": "produces_item",
                        "confidence": 0.95,
                        "metadata": {"output_item_count": props.get("output_item_count", 1)},
                    })
                for ingredient in ingredients:
                    item_id = ingredient.get("item_id") if isinstance(ingredient, dict) else None
                    if item_id is None:
                        continue
                    ingredient_id = f"ingredient:{entity['id']}:{item_id}"
                    new_entities.append({
                        "id": ingredient_id,
                        "type": "ingredient_dependency",
                        "name": f"Ingredient {item_id}",
                        "properties": {
                            "item_id": item_id,
                            "count": ingredient.get("count", 1),
                            "recipe_id": entity["id"],
                        },
                        "source": data.get("source", source.id),
                    })
                    new_relations.append({
                        "source": entity["id"],
                        "target": ingredient_id,
                        "relation": "requires_ingredient",
                        "confidence": 0.95,
                    })
                    new_relations.append({
                        "source": ingredient_id,
                        "target": f"item:{item_id}",
                        "relation": "references_item",
                        "confidence": 0.9,
                    })

        result = dict(data)
        result["entities"] = new_entities
        result["relations"] = new_relations
        result["_vertical_expanded"] = True
        return result
