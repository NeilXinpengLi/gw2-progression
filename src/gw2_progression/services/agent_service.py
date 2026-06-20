"""Progression Agent v0.1 — aggregated advice and weekly plan generator."""

import logging

from ..models import ProgressionAdvice
from .build_service import get_recommendations
from .progression_service import CURATED_TEMPLATES, generate_goal_plan
from .tp_strategy_service import generate_signals

logger = logging.getLogger("gw2.agent")


async def generate_advice(api_key: str) -> ProgressionAdvice:
    from ..analyzer import fetch_all

    contents = await fetch_all(api_key)
    account_name = contents.account_name or "unknown"

    wallet_gold = 0
    for w in contents.wallet or []:
        if w.get("id") == 1:
            wallet_gold = w.get("value", 0)

    advice = ProgressionAdvice(
        summary=f"Account: {account_name}. Wallet: {wallet_gold // 10000}g. Analyzing goals and builds...",
    )

    actions: list[dict] = []
    weekly_plan: list[dict] = []

    # 1. Goal analysis
    fastest_goal = None
    for t in CURATED_TEMPLATES[:5]:
        try:
            plan = await generate_goal_plan(api_key, t.template_id)
            if fastest_goal is None or (plan.total_completion_percent > fastest_goal.total_completion_percent and t.difficulty_level != "hard"):
                fastest_goal = plan
        except Exception:
            continue

    if fastest_goal:
        actions.append(
            {
                "action": "continue_goal",
                "target": fastest_goal.template_id,
                "reason": f"Goal '{fastest_goal.template_id}' is {fastest_goal.total_completion_percent}% complete, {fastest_goal.total_missing_cost // 10000}g remaining",
                "cost": fastest_goal.total_missing_cost,
            }
        )

    # 2. Tradeable asset signals
    try:
        signals = await generate_signals(account_name)
        sell_signals = [s for s in signals if s.signal_type == "sell_candidate" and s.quantity_owned >= 10]
        for s in sell_signals[:3]:
            actions.append(
                {
                    "action": "sell_asset",
                    "target": str(s.item_id),
                    "reason": f"Item #{s.item_id}: {s.quantity_owned}x valued at {s.value_owned // 10000}g, not goal-protected",
                    "cost": s.value_owned,
                }
            )
    except Exception as e:
        logger.warning("Signal generation failed: %s", e)

    # 3. Build readiness
    try:
        recs = await get_recommendations(api_key)
        if recs:
            best = recs[0]
            actions.append(
                {
                    "action": "build_recommendation",
                    "target": best.build_id,
                    "reason": f"Best match build: {best.build_name} (readiness: {best.readiness_score:.0%}, missing: {best.missing_items_count} items)",
                    "cost": best.missing_cost,
                }
            )
    except Exception:
        pass

    # 4. Weekly plan
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for i, day in enumerate(days):
        entry = {"day": day, "tasks": []}
        if i < len(actions):
            entry["tasks"].append(actions[i]["reason"])
        if i == 0 and actions:
            entry["tasks"].append(f"Review {len(actions)} recommendations")
        weekly_plan.append(entry)

    if not actions:
        actions.append(
            {
                "action": "run_analysis",
                "target": "",
                "reason": "No actionable advice yet. Try creating a goal first.",
                "cost": 0,
            }
        )

    advice.recommended_actions = actions
    advice.weekly_plan = weekly_plan
    return advice


async def generate_weekly_plan(api_key: str) -> list[dict]:
    advice = await generate_advice(api_key)
    return advice.weekly_plan
