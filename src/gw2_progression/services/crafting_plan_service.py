"""Enhanced crafting plan with craft_vs_buy_delta and formal models.

Integrates with ontology to reserve crafting materials and track
which goals the crafted item contributes toward.
"""

import logging
import uuid
from datetime import datetime, timezone

from ..models import CraftingPlanLine, CraftingPlanResult
from .price_service import fetch_prices
from .recipe_service import calculate

logger = logging.getLogger("gw2.craftplan")


async def create_plan(
    api_key: str,
    target_item_id: int,
    quantity: int = 1,
    use_owned: bool = True,
) -> CraftingPlanResult:
    # Get market price for direct buy
    prices_raw = await fetch_prices([target_item_id])
    target_price = prices_raw.get(target_item_id)
    direct_buy_price = (target_price.sell_unit_price if target_price else 0) * quantity

    # Use existing recipe calculator for detailed breakdown
    calc_result = await calculate(
        api_key=api_key,
        target_item_id=target_item_id,
        quantity=quantity,
        use_owned=use_owned,
    )

    lines: list[CraftingPlanLine] = []
    total_owned_value = 0
    total_missing_cost = 0

    # Build lines from shopping list
    for sl in calc_result.shopping_list:
        line = CraftingPlanLine(
            item_id=sl.get("item_id", 0),
            required_count=sl.get("needed", sl.get("count", 0)),
            owned_count=sl.get("owned", 0),
            used_owned_count=min(sl.get("owned", 0), sl.get("needed", sl.get("count", 0))),
            missing_count=sl.get("missing", sl.get("count", 0)),
            unit_buy_price=sl.get("unit_price", 0),
            missing_buy_cost=sl.get("total", 0),
            source="missing",
        )
        total_missing_cost += line.missing_buy_cost
        total_owned_value += line.used_owned_count * line.unit_buy_price
        lines.append(line)

    # Build lines from owned materials not in shopping list (fully owned)
    for mi in calc_result.missing_items:
        owned = mi.get("owned", 0)
        needed = mi.get("needed", 0)
        if owned >= needed:
            lines.append(
                CraftingPlanLine(
                    item_id=mi.get("item_id", 0),
                    required_count=needed,
                    owned_count=owned,
                    used_owned_count=needed,
                    missing_count=0,
                    source="material_storage",
                )
            )

    plan = CraftingPlanResult(
        plan_id=uuid.uuid4().hex[:12],
        target_item_id=target_item_id,
        target_count=quantity,
        total_market_buy_cost=total_missing_cost,
        total_market_sell_cost=calc_result.total_buy_cost,
        owned_material_value_used=total_owned_value,
        missing_material_cost=total_missing_cost,
        direct_buy_price=direct_buy_price,
        craft_vs_buy_delta=total_missing_cost - direct_buy_price,
        lines=lines,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    try:
        from ..database import using_db
        db = await using_db().__aenter__()
        try:
            from ..analyzer import fetch_all
            contents = await fetch_all(api_key)
            acct = contents.account_name or "unknown"
            await db.close()
            db = None

            from ..ontology.account_mapper import sync_account_to_ontology
            from ..ontology.goal_mapper import sync_goal_reservations
            await sync_account_to_ontology(api_key, acct)
            await sync_goal_reservations(acct)
        finally:
            if db:
                await db.close()
    except Exception as e:
        logger.debug("Ontology crafting sync skipped (non-blocking): %s", e)

    return plan
