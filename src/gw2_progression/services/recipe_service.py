"""Recipe fetching, recipe tree expansion, and craft cost calculation."""

import logging
from typing import Any

import httpx

from ..cache import get_cache
from ..models import CraftIngredient, CraftingResponse, CraftStep
from .holdings_service import (
    extract_bank_holdings,
    extract_character_holdings,
    extract_material_holdings,
    extract_shared_inventory_holdings,
)
from .price_service import fetch_prices

logger = logging.getLogger("gw2.recipe")

GW2_BASE = "https://api.guildwars2.com"
MAX_RECIPE_DEPTH = 3

_cache = get_cache(ttl=86400, maxsize=2048)


async def _gw2_fetch(path: str) -> Any:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{GW2_BASE}{path}")
    if not resp.is_success:
        logger.warning("GW2 API error %d: %s", resp.status_code, path)
        return None
    return resp.json()


async def _fetch_recipes_for_output(
    item_id: int,
    disciplines: dict[str, int] | None = None,
) -> list[dict]:
    cached = _cache.get(f"recipe:output:{item_id}")
    raw_recipes = cached
    if raw_recipes is None:
        data = await _gw2_fetch(f"/v2/recipes/search?output={item_id}")
        if not data:
            return []
        recipe_ids = data if isinstance(data, list) else [data]
        if not recipe_ids:
            return []
        recipes_raw = await _gw2_fetch(f"/v2/recipes?ids={','.join(str(i) for i in recipe_ids[:10])}")
        if not recipes_raw:
            return []
        raw_recipes = recipes_raw if isinstance(recipes_raw, list) else [recipes_raw]
        for r in raw_recipes:
            rid = r.get("id")
            if rid:
                _cache.set(f"recipe:output:{item_id}", raw_recipes)

    if disciplines and raw_recipes:
        return _filter_recipes_by_discipline(raw_recipes, disciplines)
    return raw_recipes or []


async def _fetch_item_name(item_id: int) -> str:
    cached = _cache.get(f"item_name:{item_id}")
    if cached is not None:
        return cached
    data = await _gw2_fetch(f"/v2/items/{item_id}")
    name = data.get("name", f"Item #{item_id}") if data else f"Item #{item_id}"
    _cache.set(f"item_name:{item_id}", name)
    return name


def _extract_disciplines(characters: list | None) -> dict[str, int]:
    """Extract available crafting disciplines with max ratings from account characters."""
    disciplines: dict[str, int] = {}
    if not characters:
        return disciplines
    for char in characters:
        if not isinstance(char, dict):
            continue
        for craft in char.get("crafting", []):
            disc = craft.get("discipline")
            rating = craft.get("rating", 0)
            if disc:
                current = disciplines.get(disc, 0)
                disciplines[disc] = max(current, rating)
    return disciplines


def _filter_recipes_by_discipline(
    recipes: list[dict],
    disciplines: dict[str, int] | None,
) -> list[dict]:
    """Filter recipes to only include those craftable by the account."""
    if not disciplines:
        return recipes
    filtered = []
    for r in recipes:
        recipe_discs = r.get("disciplines", [])
        if not recipe_discs:
            filtered.append(r)
            continue
        recipe_rating = r.get("min_rating", 0)
        for d in recipe_discs:
            char_rating = disciplines.get(d, 0)
            if char_rating >= recipe_rating:
                filtered.append(r)
                break
    return filtered


def _build_owned_map(materials, bank, characters, shared_inventory) -> dict[int, int]:
    """Build {item_id: total_count} from all account holdings."""
    counts: dict[int, int] = {}
    for h in extract_material_holdings(materials):
        counts[h.item_id] = counts.get(h.item_id, 0) + h.count
    for h in extract_bank_holdings(bank):
        counts[h.item_id] = counts.get(h.item_id, 0) + h.count
    for h in extract_character_holdings(characters):
        counts[h.item_id] = counts.get(h.item_id, 0) + h.count
    for h in extract_shared_inventory_holdings(shared_inventory):
        counts[h.item_id] = counts.get(h.item_id, 0) + h.count
    return counts


async def _expand_ingredient(
    item_id: int,
    needed_count: int,
    owned_map: dict[int, int],
    prices: dict[int, tuple[int, int]],
    depth: int = 0,
    disciplines: dict[str, int] | None = None,
) -> CraftIngredient:
    """Expand a single ingredient (first recipe only, original behavior)."""
    owned = owned_map.get(item_id, 0)
    buy_price = prices.get(item_id, (0, 0))[1] or prices.get(item_id, (0, 0))[0]
    missing = max(0, needed_count - owned)

    ing = CraftIngredient(
        item_id=item_id,
        count=needed_count,
        owned=min(owned, needed_count),
        missing=missing,
        buy_unit_price=buy_price,
        total_buy_cost=missing * buy_price,
        has_recipe=False,
        sub_tree=[],
    )

    if depth < MAX_RECIPE_DEPTH and missing > 0:
        recipes = await _fetch_recipes_for_output(item_id, disciplines)
        if recipes:
            ing.has_recipe = True
            best = recipes[0]
            output_count = best.get("output_item_count", 1)
            multiplier = -(-missing // output_count)

            sub_ings = []
            for raw in best.get("ingredients", []):
                sub_id = raw.get("item_id")
                sub_count = raw.get("count", 1) * multiplier
                sub = await _expand_ingredient(sub_id, sub_count, owned_map, prices, depth + 1, disciplines)
                sub_ings.append(sub)
            ing.sub_tree = sub_ings

    return ing


async def _expand_cheapest(
    item_id: int,
    needed_count: int,
    owned_map: dict[int, int],
    prices: dict[int, tuple[int, int]],
    visited: set[int] | None = None,
    depth: int = 0,
    disciplines: dict[str, int] | None = None,
) -> CraftIngredient:
    """Expand an ingredient using the cheapest available recipe, comparing multiple options."""
    if visited is None:
        visited = set()

    owned = owned_map.get(item_id, 0)
    buy_price = prices.get(item_id, (0, 0))[1] or prices.get(item_id, (0, 0))[0]
    missing = max(0, needed_count - owned)
    direct_buy_cost = missing * buy_price

    ing = CraftIngredient(
        item_id=item_id,
        count=needed_count,
        owned=min(owned, needed_count),
        missing=missing,
        buy_unit_price=buy_price,
        total_buy_cost=direct_buy_cost,
        has_recipe=False,
        sub_tree=[],
    )

    # Stop if nothing missing, at max depth, or in a cycle
    if missing == 0 or depth >= MAX_RECIPE_DEPTH or item_id in visited:
        return ing

    visited = visited | {item_id}
    recipes = await _fetch_recipes_for_output(item_id, disciplines)
    if not recipes:
        return ing

    ing.has_recipe = True
    best_recipe = None
    best_cost = direct_buy_cost  # Baseline: just buy it

    for recipe in recipes:
        output_count = recipe.get("output_item_count", 1)
        multiplier = -(-missing // output_count)
        total_recipe_cost = 0
        sub_results = []

        for raw in recipe.get("ingredients", []):
            sub_id = raw.get("item_id")
            sub_count = raw.get("count", 1) * multiplier
            sub = await _expand_cheapest(sub_id, sub_count, owned_map, prices, visited.copy(), depth + 1, disciplines)
            sub_results.append(sub)
            total_recipe_cost += sub.total_buy_cost if sub.missing > 0 else 0

        if total_recipe_cost < best_cost:
            best_cost = total_recipe_cost
            best_recipe = sub_results

    if best_recipe is not None:
        ing.sub_tree = best_recipe
        ing.total_buy_cost = best_cost

    return ing


async def calculate_cheapest(
    api_key: str,
    target_item_id: int,
    quantity: int = 1,
    use_owned: bool = True,
) -> CraftingResponse:
    """Calculate crafting costs using cheapest recipe traversal."""
    from ..analyzer import fetch_all

    contents = await fetch_all(api_key)
    disciplines = _extract_disciplines(contents.characters)

    owned_map = (
        _build_owned_map(
            contents.materials,
            contents.bank,
            contents.characters,
            contents.shared_inventory,
        )
        if use_owned
        else {}
    )

    item_ids_needed = {target_item_id}
    recipes = await _fetch_recipes_for_output(target_item_id, disciplines)
    if recipes:
        for r in recipes[:1]:
            for ing in r.get("ingredients", []):
                item_ids_needed.add(ing.get("item_id"))

    prices_raw = await fetch_prices(list(item_ids_needed))
    prices = {iid: (pd.buy_unit_price, pd.sell_unit_price) for iid, pd in prices_raw.items()}

    root = await _expand_cheapest(target_item_id, quantity, owned_map, prices, disciplines=disciplines)
    craft_cost = await _compute_craft_cost(root)

    missing_items = []
    shopping_list = []

    def _collect_missing(node: CraftIngredient, path: str = ""):
        if node.missing > 0 and not node.sub_tree:
            name = _cache.get(f"item_name:{node.item_id}") or f"Item #{node.item_id}"
            missing_items.append(
                {
                    "item_id": node.item_id,
                    "name": name,
                    "needed": node.count,
                    "owned": node.owned,
                    "missing": node.missing,
                    "buy_unit_price": node.buy_unit_price,
                    "total_cost": node.total_buy_cost,
                }
            )
            shopping_list.append(
                {
                    "item_id": node.item_id,
                    "name": name,
                    "count": node.missing,
                    "unit_price": node.buy_unit_price,
                    "total": node.total_buy_cost,
                }
            )
        for sub in node.sub_tree:
            _collect_missing(sub, f"{path}/{node.item_id}")

    _collect_missing(root)

    missing_items.sort(key=lambda x: x["total_cost"], reverse=True)
    shopping_list.sort(key=lambda x: x["total"], reverse=True)

    crafting_steps = []

    def _collect_steps(node: CraftIngredient, depth_lvl: int = 0):
        if node.sub_tree:
            name = _cache.get(f"item_name:{node.item_id}") or f"Item #{node.item_id}"
            crafting_steps.append(
                {
                    "depth": depth_lvl,
                    "item_id": node.item_id,
                    "name": name,
                    "count": node.count,
                    "owned": node.owned,
                    "missing": node.missing,
                    "buy_cost": node.total_buy_cost,
                }
            )
            for sub in node.sub_tree:
                _collect_steps(sub, depth_lvl + 1)

    _collect_steps(root)

    total_buy_cost = sum(item["total_cost"] for item in missing_items)
    owned_used = sum(node.owned for node in [root] if node.owned > 0)

    return CraftingResponse(
        target_item_id=target_item_id,
        target_count=quantity,
        total_buy_cost=total_buy_cost,
        total_craft_cost=craft_cost,
        owned_used=owned_used,
        missing_items=missing_items,
        shopping_list=shopping_list,
        crafting_steps=crafting_steps,
    )


async def _compute_craft_cost(ing: CraftIngredient) -> int:
    if ing.sub_tree:
        total = 0
        for sub in ing.sub_tree:
            total += await _compute_craft_cost(sub)
        return total
    return ing.total_buy_cost


async def calculate(
    api_key: str,
    target_item_id: int,
    quantity: int = 1,
    use_owned: bool = True,
) -> CraftingResponse:
    from ..analyzer import fetch_all

    contents = await fetch_all(api_key)
    disciplines = _extract_disciplines(contents.characters)

    owned_map = (
        _build_owned_map(
            contents.materials,
            contents.bank,
            contents.characters,
            contents.shared_inventory,
        )
        if use_owned
        else {}
    )

    item_ids_needed = {target_item_id}
    recipes_for_output = await _fetch_recipes_for_output(target_item_id, disciplines)
    if recipes_for_output:
        for r in recipes_for_output[:1]:
            for ing in r.get("ingredients", []):
                item_ids_needed.add(ing.get("item_id"))

    prices_raw = await fetch_prices(list(item_ids_needed))
    prices = {iid: (pd.buy_unit_price, pd.sell_unit_price) for iid, pd in prices_raw.items()}

    root = await _expand_ingredient(target_item_id, quantity, owned_map, prices, depth=0, disciplines=disciplines)
    craft_cost = await _compute_craft_cost(root)

    missing_items = []
    shopping_list = []

    def _collect_missing(node: CraftIngredient, path: str = ""):
        if node.missing > 0 and not node.sub_tree:
            name = _cache.get(f"item_name:{node.item_id}") or f"Item #{node.item_id}"
            missing_items.append(
                {
                    "item_id": node.item_id,
                    "name": name,
                    "needed": node.count,
                    "owned": node.owned,
                    "missing": node.missing,
                    "buy_unit_price": node.buy_unit_price,
                    "total_cost": node.total_buy_cost,
                }
            )
            shopping_list.append(
                {
                    "item_id": node.item_id,
                    "name": name,
                    "count": node.missing,
                    "unit_price": node.buy_unit_price,
                    "total": node.total_buy_cost,
                }
            )
        for sub in node.sub_tree:
            _collect_missing(sub, f"{path}/{node.item_id}")

    _collect_missing(root)

    missing_items.sort(key=lambda x: x["total_cost"], reverse=True)
    shopping_list.sort(key=lambda x: x["total"], reverse=True)

    crafting_steps = []

    def _collect_steps(node: CraftIngredient, depth: int = 0):
        if node.sub_tree:
            name = _cache.get(f"item_name:{node.item_id}") or f"Item #{node.item_id}"
            crafting_steps.append(
                {
                    "depth": depth,
                    "item_id": node.item_id,
                    "name": name,
                    "count": node.count,
                    "owned": node.owned,
                    "missing": node.missing,
                    "buy_cost": node.total_buy_cost,
                }
            )
            for sub in node.sub_tree:
                _collect_steps(sub, depth + 1)

    _collect_steps(root)

    total_buy_cost = sum(item["total_cost"] for item in missing_items)
    owned_used = sum(node.owned for node in [root] if node.owned > 0)

    _recipe_tree = None
    alt_recipes = []
    if recipes_for_output:
        r = recipes_for_output[0]
        _recipe_tree = CraftStep(
            recipe_id=r.get("id", 0),
            output_item_id=target_item_id,
            output_count=r.get("output_item_count", 1),
            disciplines=r.get("disciplines", []),
            min_rating=r.get("min_rating", 0),
            ingredients=root.sub_tree,
            craft_cost=craft_cost,
        )
        for r in recipes_for_output[1:]:
            alt_recipes.append(
                {
                    "recipe_id": r.get("id"),
                    "disciplines": r.get("disciplines", []),
                    "min_rating": r.get("min_rating", 0),
                    "output_count": r.get("output_item_count", 1),
                    "ingredients": [{"item_id": i.get("item_id"), "count": i.get("count")} for i in r.get("ingredients", [])],
                }
            )

    return CraftingResponse(
        target_item_id=target_item_id,
        target_count=quantity,
        total_buy_cost=total_buy_cost,
        total_craft_cost=craft_cost,
        owned_used=owned_used,
        missing_items=missing_items,
        shopping_list=shopping_list,
        crafting_steps=crafting_steps,
        recipe_tree=_recipe_tree,
        alternative_recipes=alt_recipes,
    )
