"""Impact Analyzer — computes blast radius of player actions.

Before any sell/buy/change recommendation is delivered, the impact analyzer
traces what would break: which goals lose progress, which do-not-sell
rules are violated, which reports become stale.

Key use cases:
  - Selling an item → can it block a legendary goal?
  - Changing goal priority → which reserved quantities change?
  - Stale build source → which recommendations weaken?
  - Stale snapshot → which reports are affected?
"""

import logging
from typing import Any

from ..database import load_latest_holdings, using_db
from . import graph_query as gq
from . import object_store as store
from .models import ImpactReport, SafeSurplusResult

logger = logging.getLogger("gw2.ontology.impact")


async def analyze_sell_impact(
    item_id: int,
    quantity: int,
    account_name: str,
    item_name: str = "",
) -> ImpactReport:
    surplus_data = gq.compute_asset_safe_surplus(item_id, account_name)
    surplus = surplus_data["safe_surplus"]
    total_owned = surplus_data["total_owned"]
    goals = surplus_data["goals"]

    affected_goals: list[dict] = []
    blocked_goals: list[str] = []
    partially_affected: list[dict] = []
    warnings: list[str] = []

    if total_owned <= 0:
        warnings.append(f"Item #{item_id} not found in account holdings.")

    for g in goals:
        if g.get("status") != "active":
            continue
        required = g.get("required_count", 0)
        after_sell_total = max(0, total_owned - quantity)
        shortfall = max(0, required - after_sell_total)

        if shortfall > 0:
            blocked_goals.append(g.get("goal_name", g.get("template_id", "")))
            affected_goals.append({
                "goal_name": g.get("goal_name", ""),
                "template_id": g.get("template_id", ""),
                "required": required,
                "owned_before": total_owned,
                "owned_after": after_sell_total,
                "shortfall": shortfall,
                "impact": "blocked" if shortfall >= required / 2 else "delayed",
            })

    if quantity > total_owned and total_owned > 0:
        warnings.append(f"Cannot sell {quantity}, only have {total_owned}.")

    remaining = total_owned - quantity
    if remaining < 0:
        remaining = 0

    if quantity > surplus and surplus > 0:
        warnings.append(
            f"Selling {quantity} exceeds safe surplus of {surplus}. "
            f"Active goals may be affected."
        )

    if surplus <= 0 and total_owned > 0:
        warnings.append("No safe surplus — all owned items are reserved for active goals.")

    blocked_count = len(blocked_goals)
    if blocked_count > 0:
        risk_level = "high"
        recommendation = "Do not sell — this item is required for active goals."
    elif warnings:
        risk_level = "medium"
        recommendation = "Sell with caution — some goals may be affected."
    else:
        risk_level = "low"
        recommendation = f"Safe to sell up to {surplus}."

    return ImpactReport(
        item_id=item_id,
        item_name=item_name,
        quantity_to_sell=quantity,
        risk_level=risk_level,
        affected_goals=affected_goals,
        blocked_goals=blocked_goals,
        partially_affected_goals=partially_affected,
        warnings=warnings,
        safe_surplus=surplus,
        recommendation=recommendation,
        evidence_source="ontology_graph_query",
        qa_status="pass",
    )


async def compute_safe_surplus(item_id: int, account_name: str) -> SafeSurplusResult:
    surplus_data = gq.compute_asset_safe_surplus(item_id, account_name)
    reserved_details = gq.get_reserved_details(account_name)
    item_reservations = [r for r in reserved_details if r.get("item_id") == item_id]

    db = await using_db().__aenter__()
    try:
        holdings = await load_latest_holdings(db, account_name)
    finally:
        await db.close()

    owned = next((h.count for h in holdings if h.item_id == item_id), 0)

    return SafeSurplusResult(
        item_id=item_id,
        item_name="",
        total_owned=owned,
        total_reserved=surplus_data["total_reserved"],
        safe_surplus=surplus_data["safe_surplus"],
        reserved_by_goals=item_reservations,
        evidence_source="account_snapshot + ontology_graph_query",
        qa_status="pass",
    )


async def analyze_goal_priority_change(
    goal_id: str,
    new_priority: str,
    account_name: str,
) -> dict[str, Any]:
    goal_obj = store.get_object(goal_id)
    if not goal_obj or goal_obj.class_name != "legendary_goal":
        return {"error": f"Goal {goal_id} not found or not a legendary_goal"}

    old_priority = goal_obj.properties.get("priority", "normal")

    effects: list[str] = []
    if new_priority == "high" and old_priority != "high":
        effects.append(f"Goal {goal_obj.properties.get('name', '')} moved to high priority.")
    elif old_priority == "high" and new_priority != "high":
        effects.append(f"Goal {goal_obj.properties.get('name', '')} demoted. "
                       f"Reserved items may be reallocated to other active goals.")

    return {
        "goal_id": goal_id,
        "goal_name": goal_obj.properties.get("name", ""),
        "old_priority": old_priority,
        "new_priority": new_priority,
        "effects": effects,
        "risk_level": "low" if new_priority != "low" else "medium",
    }
