"""Recipe optimization engine with multi-strategy support."""

import logging
import uuid
from datetime import datetime, timezone

from ..cache import get_cache
from ..models import RecipeDecision, RecipeOptimizationResult
from .holdings_service import (
    extract_bank_holdings,
    extract_character_holdings,
    extract_material_holdings,
    extract_shared_inventory_holdings,
)
from .price_service import fetch_prices
from .recipe_service import _fetch_recipes_for_output

logger = logging.getLogger("gw2.optimizer")

_cache = get_cache(ttl=86400, maxsize=2048)
MAX_OPT_DEPTH = 5

_strategies = {
    "cheapest": {"prefer_buy": False, "use_owned": True, "minimize_gold": False, "preserve_owned": False},
    "fastest": {"prefer_buy": True, "use_owned": True, "minimize_gold": False, "preserve_owned": False},
    "use_owned_first": {"prefer_buy": False, "use_owned": True, "minimize_gold": False, "preserve_owned": False},
    "preserve_owned": {"prefer_buy": False, "use_owned": False, "minimize_gold": False, "preserve_owned": True},
    "minimize_gold": {"prefer_buy": False, "use_owned": True, "minimize_gold": True, "preserve_owned": False},
}


async def optimize_item(
    item_id: int,
    needed_count: int,
    owned_map: dict[int, int],
    prices: dict[int, tuple[int, int]],
    strategy: str = "cheapest",
    visited: set[int] | None = None,
    depth: int = 0,
) -> RecipeDecision:
    if visited is None:
        visited = set()

    owned = owned_map.get(item_id, 0)
    buy_price = prices.get(item_id, (0, 0))[1] or prices.get(item_id, (0, 0))[0]
    missing = max(0, needed_count - owned)
    direct_buy_cost = missing * buy_price

    cfg = _strategies.get(strategy, _strategies["cheapest"])
    use_owned = cfg["use_owned"]

    if use_owned and owned >= needed_count:
        return RecipeDecision(
            item_id=item_id,
            decision="use_owned",
            reason="Fully owned in account",
            cost_buy=0,
            cost_craft=0,
            owned_count=owned,
            missing_count=0,
        )

    if depth >= MAX_OPT_DEPTH or item_id in visited:
        return RecipeDecision(
            item_id=item_id,
            decision="buy",
            reason=f"Max depth ({depth}) or cycle detected",
            cost_buy=direct_buy_cost,
            cost_craft=direct_buy_cost,
            owned_count=owned,
            missing_count=missing,
        )

    visited = visited | {item_id}
    recipes = await _fetch_recipes_for_output(item_id)
    if not recipes or not any(r.get("ingredients") for r in recipes):
        return RecipeDecision(
            item_id=item_id,
            decision="buy",
            reason="No recipe or no ingredients",
            cost_buy=direct_buy_cost,
            cost_craft=direct_buy_cost,
            owned_count=owned,
            missing_count=missing,
        )

    best_craft_cost = direct_buy_cost
    best_decision = RecipeDecision(
        item_id=item_id,
        decision="buy",
        reason=f"Direct buy cheaper ({fmt(direct_buy_cost)})",
        cost_buy=direct_buy_cost,
        cost_craft=direct_buy_cost,
        owned_count=owned,
        missing_count=missing,
    )

    for recipe in recipes:
        output_count = recipe.get("output_item_count", 1)
        multiplier = -(-missing // output_count)
        total_ingredient_cost = 0
        all_owned = True
        sub_decisions = []

        for ing in recipe.get("ingredients", []):
            sub_id = ing.get("item_id")
            sub_count = ing.get("count", 1) * multiplier
            sub = await optimize_item(sub_id, sub_count, owned_map, prices, strategy, visited.copy(), depth + 1)
            sub_decisions.append(sub)
            total_ingredient_cost += sub.cost_buy
            if sub.decision != "use_owned":
                all_owned = False

        if all_owned:
            return RecipeDecision(
                item_id=item_id,
                decision="craft",
                reason="All ingredients owned, can craft for free",
                cost_buy=0,
                cost_craft=0,
                owned_count=owned,
                missing_count=0,
            )

        if cfg["prefer_buy"]:
            if direct_buy_cost <= total_ingredient_cost:
                continue
        elif cfg["minimize_gold"]:
            if owned > 0:
                total_ingredient_cost = max(0, total_ingredient_cost - owned * buy_price)
        elif cfg["preserve_owned"]:
            pass

        if total_ingredient_cost < best_craft_cost:
            best_craft_cost = total_ingredient_cost
            best_decision = RecipeDecision(
                item_id=item_id,
                decision="craft",
                reason=f"Craft cheaper ({fmt(total_ingredient_cost)} vs buy {fmt(direct_buy_cost)})",
                cost_buy=direct_buy_cost,
                cost_craft=total_ingredient_cost,
                owned_count=owned,
                missing_count=missing,
            )

    return best_decision


def fmt(c: int) -> str:
    return f"{c // 10000}g {c % 10000 // 100}s {c % 100}c" if c else "0g"


def _extract_required_disciplines(recipes: list[dict]) -> list[str]:
    discs = set()
    for r in recipes:
        for d in r.get("disciplines", []):
            discs.add(d)
    return sorted(discs)


async def optimize(
    api_key: str,
    target_item_id: int,
    target_count: int = 1,
    strategy: str = "cheapest",
    use_owned: bool = True,
) -> RecipeOptimizationResult:
    from ..analyzer import fetch_all

    contents = await fetch_all(api_key)

    owned_map: dict[int, int] = {}
    if use_owned:
        for h in extract_material_holdings(contents.materials):
            owned_map[h.item_id] = owned_map.get(h.item_id, 0) + h.count
        for h in extract_bank_holdings(contents.bank):
            owned_map[h.item_id] = owned_map.get(h.item_id, 0) + h.count
        for h in extract_character_holdings(contents.characters):
            owned_map[h.item_id] = owned_map.get(h.item_id, 0) + h.count
        for h in extract_shared_inventory_holdings(contents.shared_inventory):
            owned_map[h.item_id] = owned_map.get(h.item_id, 0) + h.count

    item_ids = {target_item_id}
    recipes = await _fetch_recipes_for_output(target_item_id)
    if recipes:
        for r in recipes[:1]:
            for ing in r.get("ingredients", []):
                item_ids.add(ing.get("item_id"))

    prices_raw = await fetch_prices(list(item_ids))
    prices = {iid: (pd.buy_unit_price, pd.sell_unit_price) for iid, pd in prices_raw.items()}

    root_decision = await optimize_item(target_item_id, target_count, owned_map, prices, strategy)

    total_missing_cost = root_decision.cost_buy
    owned_value = root_decision.owned_count * prices.get(target_item_id, (0, 0))[1] if root_decision.owned_count > 0 else 0

    direct_buy = prices.get(target_item_id, (0, 0))[1] * target_count if prices.get(target_item_id, (0, 0))[1] else 0

    shopping_list = []
    if root_decision.decision == "buy":
        shopping_list.append(
            {
                "item_id": target_item_id,
                "count": root_decision.missing_count,
                "unit_price": prices.get(target_item_id, (0, 0))[1],
                "total": total_missing_cost,
                "source": "TP buy",
            }
        )

    discs = _extract_required_disciplines(recipes) if recipes else []

    return RecipeOptimizationResult(
        result_id=uuid.uuid4().hex[:12],
        target_item_id=target_item_id,
        target_count=target_count,
        strategy=strategy,
        total_cost=root_decision.cost_buy,
        owned_value_used=owned_value,
        missing_cost=total_missing_cost,
        direct_buy_cost=direct_buy,
        craft_vs_buy_delta=root_decision.cost_buy - direct_buy,
        decisions=[root_decision],
        shopping_list=shopping_list,
        required_disciplines=discs,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
