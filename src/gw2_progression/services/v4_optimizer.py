"""v4 Optimization Engine — multi-strategy explainable action planning."""

from gw2_progression.services.v4_economic_model import STRATEGIES, PricePoint, score_action


def generate_explainable_actions(
    account_data: dict,
    value_data: dict | None,
    builds: list,
    goals: list,
    strategy: str = "hybrid",
) -> dict:
    """Generate ranked, explainable actions using the v4 engine."""
    weights = STRATEGIES.get(strategy, STRATEGIES["hybrid"])["weights"]
    wallet = account_data.get("wallet", [])
    wallet_gold = sum(w.get("value", 0) for w in wallet if w.get("id") == 1)
    chars = account_data.get("characters", [])
    char_count = len(chars)
    lvl80 = sum(1 for c in chars if c.get("level") == 80)
    total_value = (value_data or {}).get("total_value_buy", 0) if value_data else 0

    raw_actions = []

    # Value actions
    if total_value > 0:
        raw_actions.append(
            {
                "action": "Review Top Items",
                "reason": f"Account valued at {total_value // 10000}g. Check which items drive value.",
                "reward_copper": total_value,
                "build_impact": 0,
                "legendary_impact": 0,
                "time_cost_minutes": 10,
                "risk": 0.1,
                "tab": "value",
                "icon": "💰",
            }
        )

    # Character actions
    if char_count - lvl80 > 0:
        raw_actions.append(
            {
                "action": f"Level {char_count - lvl80} Characters",
                "reason": f"{char_count - lvl80} characters below 80. Max level unlocks full build potential.",
                "reward_copper": 0,
                "build_impact": 0.8,
                "legendary_impact": 0,
                "time_cost_minutes": 60,
                "risk": 0.1,
                "tab": "characters",
                "icon": "⬆",
            }
        )

    # Build actions
    if builds:
        top = builds[0]
        score = top.get("readiness_score") or 0
        missing = top.get("missing_items_count", 0)
        if score > 0.5:
            raw_actions.append(
                {
                    "action": f"Complete {top.get('build_name', 'Build')}",
                    "reason": f"{score:.0%} ready! Only {missing} items needed.",
                    "reward_copper": 0,
                    "build_impact": 0.9,
                    "legendary_impact": 0,
                    "time_cost_minutes": 30,
                    "risk": 0.2,
                    "tab": "builds",
                    "icon": "⚔",
                }
            )

    # Goal actions
    if goals:
        best = max(goals, key=lambda g: g.get("progress", 0) or 0)
        pct = best.get("progress", 0) or 0
        raw_actions.append(
            {
                "action": f"Progress {best.get('name', 'Legendary')}",
                "reason": f"{pct:.0f}% complete. Continue farming materials.",
                "reward_copper": 0,
                "build_impact": 0,
                "legendary_impact": 0.9,
                "time_cost_minutes": 45,
                "risk": 0.3,
                "tab": "goals",
                "icon": "🏆",
            }
        )

    # Gold actions
    if wallet_gold < 10000:
        raw_actions.append(
            {
                "action": "Farm Gold",
                "reason": "Low liquid gold. Run T4 fractals + dailies for ~20g/day.",
                "reward_copper": 200000,
                "build_impact": 0.1,
                "legendary_impact": 0.1,
                "time_cost_minutes": 60,
                "risk": 0.2,
                "tab": "wallet",
                "icon": "🪙",
            }
        )

    # Default daily actions
    raw_actions.append(
        {
            "action": "Complete Dailies",
            "reason": "Daily achievements provide consistent gold and materials.",
            "reward_copper": 100000,
            "build_impact": 0.1,
            "legendary_impact": 0.1,
            "time_cost_minutes": 30,
            "risk": 0.05,
            "tab": "activities",
            "icon": "📋",
        }
    )

    # Score and rank
    scored = []
    for action in raw_actions:
        price = PricePoint(buy_qty=100, sell_qty=100) if action["reward_copper"] > 0 else None
        result = score_action(action, price, strategy)
        scored.append({**action, **result})

    ranked = sorted(scored, key=lambda x: x["final_score"], reverse=True)

    # Split into P0/P1/P2
    if len(ranked) >= 3:
        cutoff1 = max(a["final_score"] for a in ranked) * 0.6
        cutoff2 = max(a["final_score"] for a in ranked) * 0.3
    else:
        cutoff1, cutoff2 = 0.5, 0.2

    p0 = [a for a in ranked if a["final_score"] >= cutoff1][:3]
    p1 = [a for a in ranked if cutoff2 <= a["final_score"] < cutoff1][:3]
    p2 = [a for a in ranked if a["final_score"] < cutoff2][:3]

    return {
        "strategy": strategy,
        "strategy_name": STRATEGIES.get(strategy, STRATEGIES["hybrid"])["name"],
        "p0": p0,
        "p1": p1,
        "p2": p2,
        "weights": weights,
    }


def optimize_paths(goals: list | None = None) -> dict:
    """Generate multiple optimized paths to a goal."""
    goals = goals or []

    paths = [
        {
            "name": "Fast Path",
            "desc": "Minimum time to completion — uses buy orders for all materials",
            "estimated_days": 14,
            "estimated_cost_gold": 2500,
            "risk": "low",
            "suitable_for": "Players with gold reserves",
        },
        {
            "name": "Efficient Path",
            "desc": "Balance of cost and time — farm some materials, buy others",
            "estimated_days": 30,
            "estimated_cost_gold": 1200,
            "risk": "medium",
            "suitable_for": "Most players",
        },
        {
            "name": "Frugal Path",
            "desc": "Minimum gold cost — farm all materials, craft everything",
            "estimated_days": 60,
            "estimated_cost_gold": 300,
            "risk": "low",
            "suitable_for": "Players with time but limited gold",
        },
    ]

    # Customize based on goals if provided
    if goals:
        best = max(goals, key=lambda g: g.get("progress", 0) or 0)
        pct = best.get("progress", 0) or 0
        remaining = 100 - pct
        for p in paths:
            p["estimated_days"] = max(1, int(p["estimated_days"] * remaining / 100))
            p["estimated_cost_gold"] = max(0, int(p["estimated_cost_gold"] * remaining / 100))

    return {
        "paths": paths,
        "total_paths": len(paths),
    }
