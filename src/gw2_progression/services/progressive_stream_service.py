"""Progressive Result Streaming — delivers account data in 4 stages.

Stage 1 (1-3s):  account_name, wallet_gold, character_count
Stage 2 (3-8s):  total_value_estimate, hidden_wealth, top_assets
Stage 3 (8-15s): best_build, closest_goal, first_action
Stage 4 (15-30s): full_plan, crafting_path, report_preview
"""

import logging

logger = logging.getLogger("gw2.progressive")


async def stage_1_wallet_and_chars(api_key: str) -> dict:
    """Stage 1: Fast account basics."""
    from ..analyzer import fetch_all

    contents = await fetch_all(api_key)
    wallet_gold = 0
    for w in contents.wallet or []:
        if w.get("id") == 1:
            wallet_gold = w.get("value", 0)

    return {
        "stage": 1,
        "label": "Account loaded",
        "account_name": contents.account_name or "unknown",
        "wallet_gold": wallet_gold,
        "wallet_gold_display": f"{wallet_gold // 10000}g {wallet_gold % 10000 // 100}s {wallet_gold % 100}c",
        "character_count": len(contents.characters or []),
        "ready": True,
    }


async def stage_2_value_estimate(api_key: str) -> dict:
    """Stage 2: Total value and hidden wealth."""
    from ..analyzer import fetch_all
    from ..services.holdings_service import (
        extract_bank_holdings,
        extract_character_holdings,
        extract_material_holdings,
        extract_shared_inventory,
        extract_tradingpost_holdings,
        extract_wallet_holdings,
    )
    from ..services.valuation_service import apply_prices, compute_summary

    contents = await fetch_all(api_key)

    holdings = []
    holdings.extend(extract_wallet_holdings(contents.wallet or []))
    holdings.extend(extract_material_holdings(contents.materials or []))
    holdings.extend(extract_bank_holdings(contents.bank or []))
    holdings.extend(extract_character_holdings(contents.characters or []))
    holdings.extend(extract_shared_inventory(contents.shared_inventory or [] if hasattr(contents, 'shared_inventory') else []))
    tp_buys = contents.tradingpost_buys or [] if hasattr(contents, 'tradingpost_buys') else []
    tp_sells = contents.tradingpost_sells or [] if hasattr(contents, 'tradingpost_sells') else []
    holdings.extend(extract_tradingpost_holdings(tp_buys, tp_sells))

    # Apply prices
    from ..services.price_service import fetch_prices
    item_ids = list(set(h.item_id for h in holdings))
    prices = await fetch_prices(item_ids)
    holdings = apply_prices(holdings, prices)

    summary = compute_summary(holdings)
    wallet_gold = summary.wallet_value

    # Compute hidden wealth (unpriced + account bound items estimated value)
    priced = [h for h in holdings if h.valuation_status == "priced"]
    unpriced = [h for h in holdings if h.valuation_status != "priced"]
    hidden_wealth = sum(h.vendor_value * h.count for h in unpriced if h.vendor_value > 0)

    # Top assets
    sorted_holdings = sorted(priced, key=lambda h: h.value_buy, reverse=True)
    top_assets = [
        {"item_id": h.item_id, "count": h.count, "value_buy": h.value_buy, "location": h.location_type}
        for h in sorted_holdings[:10]
    ]

    return {
        "stage": 2,
        "label": "Value estimated",
        "total_value_buy": summary.total_value_buy,
        "total_value_sell": summary.total_value_sell,
        "net_sell_value": summary.net_sell_value,
        "total_value_display": f"{summary.total_value_buy // 10000}g",
        "wallet_value": wallet_gold,
        "material_value": summary.material_value_buy,
        "bank_value": summary.bank_value_buy,
        "hidden_wealth": hidden_wealth,
        "hidden_wealth_display": f"{hidden_wealth // 10000}g",
        "priced_item_count": summary.priced_item_count,
        "unpriced_item_count": summary.unpriced_item_count,
        "top_assets": top_assets,
        "ready": True,
    }


async def stage_3_builds_and_goals(api_key: str, wallet_gold: int = 0) -> dict:
    """Stage 3: Best build, closest goal, first action."""
    from ..services.build_service import get_recommendations
    from ..services.progression_service import CURATED_TEMPLATES, generate_goal_plan

    best_build_name = ""
    best_build_readiness = 0.0
    closest_goal_name = ""
    closest_goal_pct = 0.0
    first_action_text = ""

    try:
        recs = await get_recommendations(api_key)
        if recs:
            best = recs[0]
            best_build_name = best.build_name
            best_build_readiness = best.readiness_score * 100
    except Exception as e:
        logger.warning("Build analysis in stage 3 failed: %s", e)

    try:
        best_goal = None
        for t in CURATED_TEMPLATES[:5]:
            try:
                gp = await generate_goal_plan(api_key, t.template_id)
                if best_goal is None or gp.total_completion_percent > best_goal.total_completion_percent:
                    best_goal = gp
                    closest_goal_name = t.name
                    closest_goal_pct = gp.total_completion_percent
            except Exception:
                continue
    except Exception as e:
        logger.warning("Goal analysis in stage 3 failed: %s", e)

    # Generate first action
    if closest_goal_pct > 50 and closest_goal_name:
        first_action_text = f"Continue working on {closest_goal_name} ({closest_goal_pct:.0f}% complete)"
    elif best_build_name:
        first_action_text = f"Acquire gear for {best_build_name} ({best_build_readiness:.0f}% readiness)"
    elif wallet_gold < 10000:
        first_action_text = "Run T4 Fractals + dailies to build liquid gold"
    else:
        first_action_text = "Review your top assets and consider selling excess materials"

    return {
        "stage": 3,
        "label": "Goals & builds analyzed",
        "best_build_name": best_build_name,
        "best_build_readiness": round(best_build_readiness, 1),
        "closest_goal_name": closest_goal_name,
        "closest_goal_progress": round(closest_goal_pct, 1),
        "first_action": first_action_text,
        "ready": True,
    }


async def stage_4_full_plan(api_key: str, goal_text: str = "") -> dict:
    """Stage 4: Full plan with crafting path and report preview."""
    from .goal_driven_engine import generate_plan_from_goal
    from .goal_interpreter import interpret_goal

    plan = None
    try:
        if goal_text.strip():
            parsed = await interpret_goal(goal_text)
            plan = await generate_plan_from_goal(api_key, parsed)
    except Exception as e:
        logger.warning("Full plan generation in stage 4 failed: %s", e)

    return {
        "stage": 4,
        "label": "Full plan ready",
        "plan_id": plan.plan_id if plan else "",
        "estimated_days": plan.estimated_days if plan else 7,
        "total_cost": plan.total_cost_copper if plan else 0,
        "completion_percent": plan.completion_percent if plan else 0,
        "action_count": len(plan.actions) if plan and plan.actions else 0,
        "insight": plan.insight if plan else "Plan generated",
        "has_plan": plan is not None,
        "ready": True,
    }


async def run_progressive_analysis(api_key: str, goal_text: str = "") -> list[dict]:
    """Run all 4 stages and return results as they complete."""
    results = []

    # Stage 1: Fast
    try:
        s1 = await stage_1_wallet_and_chars(api_key)
        results.append(s1)
    except Exception as e:
        results.append({"stage": 1, "error": str(e), "ready": True})

    # Stage 2: Medium
    try:
        s2 = await stage_2_value_estimate(api_key)
        results.append(s2)
    except Exception as e:
        results.append({"stage": 2, "error": str(e), "ready": True})

    # Stage 3: Slow (runs parallel with stage 4 prep)
    wallet_gold = 0
    for r in results:
        if r.get("stage") == 1:
            wallet_gold = r.get("wallet_gold", 0)

    try:
        s3 = await stage_3_builds_and_goals(api_key, wallet_gold)
        results.append(s3)
    except Exception as e:
        results.append({"stage": 3, "error": str(e), "ready": True})

    # Stage 4: Slowest
    try:
        s4 = await stage_4_full_plan(api_key, goal_text)
        results.append(s4)
    except Exception as e:
        results.append({"stage": 4, "error": str(e), "ready": True})

    return results
