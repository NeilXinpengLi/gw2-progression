from __future__ import annotations

from typing import Any

from gw2_progression.data_acquisition.registry.source_registry import SourceConfig


class HorizontalExpander:
    """Horizontal Expansion — merge related data across sources.

    Example: merge gw2_api_account + gw2_api_wallet → unified player state.
    """

    def __init__(self) -> None:
        self._merge_registry: dict[str, dict[str, Any]] = {}
        self._asset_registry: dict[str, dict[str, Any]] = {}

    def expand(self, data: dict[str, Any], source: SourceConfig) -> dict[str, Any]:
        entities = data.get("entities", [])
        source_id = data.get("source", source.id)
        new_entities = list(entities)
        new_relations: list[dict[str, Any]] = list(data.get("relations", []))

        for entity in entities:
            eid = entity.get("id", "")
            if eid:
                if eid not in self._merge_registry:
                    self._merge_registry[eid] = {"sources": [], "properties": {}}
                self._merge_registry[eid]["sources"].append(source_id)
                self._merge_registry[eid]["properties"].update(entity.get("properties", {}))
            self._index_asset_entity(entity, source_id)

        merged_entities = []
        for eid, mdata in self._merge_registry.items():
            merged_entities.append({
                "id": eid,
                "type": "merged_entity",
                "name": eid,
                "sources": mdata["sources"],
                "properties": mdata["properties"],
                "source": source_id,
            })
        asset_entities, asset_relations = self._build_asset_views(source_id)

        result = dict(data)
        result["entities"] = new_entities + merged_entities + asset_entities
        result["relations"] = new_relations + asset_relations
        result["_horizontal_expanded"] = True
        return result

    def reset(self) -> None:
        self._merge_registry.clear()
        self._asset_registry.clear()

    def _index_asset_entity(self, entity: dict[str, Any], source_id: str) -> None:
        props = entity.get("properties", {})
        native_id = props.get("output_item_id") if entity.get("type") == "recipe" else props.get("native_id")
        if native_id is None:
            return
        key = str(native_id)
        entry = self._asset_registry.setdefault(key, {"sources": [], "item": None, "market": None, "recipes": []})
        if source_id not in entry["sources"]:
            entry["sources"].append(source_id)
        etype = entity.get("type")
        if etype == "item":
            entry["item"] = entity
        elif etype in {"market_item", "market_price_snapshot"}:
            entry["market"] = entity
        elif etype == "recipe":
            entry["recipes"].append(entity)

    def _build_asset_views(self, source_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        entities: list[dict[str, Any]] = []
        relations: list[dict[str, Any]] = []
        for native_id, entry in self._asset_registry.items():
            item = entry.get("item")
            market = entry.get("market")
            if not item or not market:
                continue
            item_props = item.get("properties", {})
            market_props = market.get("properties", {})
            asset_id = f"asset:{native_id}"
            recipes = entry.get("recipes", [])
            best_recipe = recipes[0] if recipes else None
            recipe_props = best_recipe.get("properties", {}) if best_recipe else {}
            output_count = int(recipe_props.get("output_item_count") or 1)
            sell_price = self._market_unit_price(market_props, "sells")
            buy_price = self._market_unit_price(market_props, "buys")
            ingredients = recipe_props.get("ingredients", []) if isinstance(recipe_props.get("ingredients", []), list) else []
            cost = self._craft_cost(ingredients)
            fee_adjusted_revenue = self._trading_post_net_revenue(sell_price * output_count)
            net_profit = fee_adjusted_revenue - cost if recipes and cost > 0 else 0
            asset = {
                "id": asset_id,
                "type": "merged_asset",
                "name": item.get("name", asset_id),
                "properties": {
                    "native_id": native_id,
                    "item": item_props,
                    "market": market_props,
                    "source_count": len(entry["sources"]),
                    "has_recipe": bool(recipes),
                    "recipe_count": len(recipes),
                    "craft_output_count": output_count if recipes else 0,
                    "craft_input_item_count": len(ingredients),
                    "craft_cost": cost,
                    "craft_revenue_sell": sell_price * output_count if recipes else 0,
                    "tp_fee_adjusted_revenue": fee_adjusted_revenue if recipes else 0,
                    "net_profit": net_profit,
                    "profit_per_output": int(net_profit / output_count) if recipes and output_count > 0 and cost > 0 else 0,
                    "craft_cost_complete": bool(recipes) and self._craft_cost_complete(ingredients),
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                },
                "source": source_id,
                "confidence": min(float(item.get("confidence", 0.8)), float(market.get("confidence", 0.8))),
                "lineage": list(entry["sources"]),
            }
            entities.append(asset)
            if recipes and asset["properties"]["craft_cost_complete"]:
                entities.append(self._profit_opportunity(asset, best_recipe, source_id))
            relations.extend([
                {"source": asset_id, "target": item["id"], "relation": "describes_item", "confidence": 0.95},
                {"source": asset_id, "target": market["id"], "relation": "priced_by", "confidence": 0.95},
            ])
            if recipes and asset["properties"]["craft_cost_complete"]:
                relations.append({
                    "source": asset_id,
                    "target": f"profit:{native_id}",
                    "relation": "has_profit_opportunity",
                    "confidence": 0.9,
                })
            for recipe in recipes:
                relations.append({"source": asset_id, "target": recipe["id"], "relation": "crafted_by", "confidence": 0.9})
                for ingredient in self._ingredient_ids(recipe):
                    relations.append({"source": asset_id, "target": f"asset:{ingredient}", "relation": "consumes_asset", "confidence": 0.85})
        return entities, relations

    def _market_unit_price(self, market_props: dict[str, Any], side: str) -> int:
        value = market_props.get(side, {})
        if isinstance(value, dict):
            return int(value.get("unit_price") or value.get("price") or 0)
        return 0

    def _craft_cost(self, ingredients: list[Any]) -> int:
        total = 0
        for ingredient in ingredients:
            if not isinstance(ingredient, dict):
                continue
            item_id = ingredient.get("item_id")
            if item_id is None:
                continue
            market = self._asset_registry.get(str(item_id), {}).get("market")
            if not market:
                continue
            count = int(ingredient.get("count") or 1)
            total += self._market_unit_price(market.get("properties", {}), "sells") * count
        return total

    def _craft_cost_complete(self, ingredients: list[Any]) -> bool:
        if not ingredients:
            return False
        for ingredient in ingredients:
            if not isinstance(ingredient, dict):
                return False
            item_id = ingredient.get("item_id")
            if item_id is None or not self._asset_registry.get(str(item_id), {}).get("market"):
                return False
        return True

    def _trading_post_net_revenue(self, gross_revenue: int) -> int:
        return int(gross_revenue * 0.85)

    def _ingredient_ids(self, recipe: dict[str, Any]) -> list[str]:
        props = recipe.get("properties", {})
        ingredients = props.get("ingredients", []) if isinstance(props.get("ingredients", []), list) else []
        ids = []
        for ingredient in ingredients:
            if isinstance(ingredient, dict) and ingredient.get("item_id") is not None:
                ids.append(str(ingredient["item_id"]))
        return ids

    def _profit_opportunity(self, asset: dict[str, Any], recipe: dict[str, Any] | None, source_id: str) -> dict[str, Any]:
        props = asset.get("properties", {})
        craft_cost = int(props.get("craft_cost") or 0)
        net_profit = int(props.get("net_profit") or 0)
        roi = round(net_profit / craft_cost, 4) if craft_cost > 0 else 0.0
        native_id = props.get("native_id", asset.get("id", "unknown"))
        recipe_props = recipe.get("properties", {}) if recipe else {}
        return {
            "id": f"profit:{native_id}",
            "type": "craft_profit_opportunity",
            "name": f"Craft profit for {asset.get('name', native_id)}",
            "properties": {
                "asset_id": asset["id"],
                "output_item_id": native_id,
                "recipe_id": recipe.get("id") if recipe else None,
                "recipe_native_id": recipe_props.get("native_id"),
                "craft_cost": craft_cost,
                "craft_revenue_sell": props.get("craft_revenue_sell", 0),
                "tp_fee_adjusted_revenue": props.get("tp_fee_adjusted_revenue", 0),
                "net_profit": net_profit,
                "profit_per_output": props.get("profit_per_output", 0),
                "roi": roi,
                "profitable": net_profit > 0,
                "craft_input_item_count": props.get("craft_input_item_count", 0),
                "ingredient_item_ids": self._ingredient_ids(recipe) if recipe else [],
            },
            "source": source_id,
            "confidence": asset.get("confidence", 0.8),
            "lineage": asset.get("lineage", []),
        }
