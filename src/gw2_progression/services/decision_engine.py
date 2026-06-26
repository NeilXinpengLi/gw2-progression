"""Decision engine — generates ranked P0/P1/P2 actions for the Action Center.

Integrates with ontology to validate sell recommendations and annotate
risk levels on all generated actions.
"""


async def decide(account_name: str, wallet_gold: int = 0, characters: list = None, goals: list = None, builds: list = None, value_data: dict = None) -> dict:
    """Generate ranked P0/P1/P2 actions from account state."""
    chars = characters or []
    lvl80_count = sum(1 for c in chars if c.get("level") == 80)
    total_value = (value_data or {}).get("total_value_buy", 0) // 10000

    p0, p1, p2 = [], [], []

    if total_value > 0:
        p0.append({"action": "Review Top Items", "reason": f"Your account is worth {total_value}g. Check which items drive the most value.", "reward": f"+{total_value}g", "tab": "value"})
    if lvl80_count < len(chars):
        p0.append({"action": "Level Characters", "reason": f"Level {len(chars) - lvl80_count} characters to 80 for full build access.", "reward": "+Build Access", "tab": "characters"})

    if goals:
        best = max(goals, key=lambda g: g.get("progress", 0) or 0)
        pct = best.get("progress", 0) or 0
        if pct > 50:
            name = best.get("name", "your goal")
            p0.append({"action": "Complete Legendary", "reason": f"You are {pct:.0f}% toward {name}. Finish remaining materials.", "reward": "Legendary Unlock", "tab": "goals"})
        else:
            p1.append({"action": "Start Goal", "reason": f"Begin working toward {best.get('name', 'a legendary')}. Check the Goals tab for requirements.", "reward": "+Progression", "tab": "goals"})

    if builds:
        top = builds[0]
        score = (top.get("readiness_score") or 0) * 100
        if score > 70:
            p0.append({"action": "Equip Build", "reason": f"You are {score:.0f}% ready for {top.get('build_name', 'a build')}! Acquire the missing items.", "reward": "Meta Build", "tab": "builds"})
        elif score > 30:
            p1.append({"action": "Build Toward", "reason": f"You are {score:.0f}% toward {top.get('build_name', 'a build')}. Prioritize the missing gear.", "reward": "+Build Score", "tab": "builds"})

    if wallet_gold < 100:
        p1.append({"action": "Earn Gold", "reason": "Low liquid gold. Run T4 fractals and daily achievements for ~20g/day.", "reward": "~20g/day", "tab": "wallet"})

    p2.append({"action": "Complete Dailies", "reason": "Daily achievements and world boss trains provide consistent rewards.", "reward": "~10g/day", "tab": "activities"})
    p2.append({"action": "Check TP", "reason": "Review Trading Post for profitable flips and undervalued listings.", "reward": "Variable", "tab": "market"})

    try:
        from ..ontology.impact_analyzer import analyze_sell_impact
        for priority_group in [p0, p1, p2]:
            for action in priority_group:
                if "sell" in action.get("action", "").lower():
                    impact = await analyze_sell_impact(0, 1, account_name, action.get("action", ""))
                    if impact.risk_level != "low":
                        action["reason"] += f" [Ontology: {impact.risk_level} risk — {impact.recommendation}]"
    except Exception:
        pass

    return {"p0": p0[:3], "p1": p1[:3], "p2": p2[:3]}


async def generate_plan(goals: list = None, builds: list = None) -> dict:
    """Generate a 7-day plan for the Timeline page."""
    base_plan = [
        {"day": "Day 1", "focus": "Sell & Liquidate", "tasks": ["Review TP listings", "Sell excess materials", "Consolidate gold"]},
        {"day": "Day 2", "focus": "Goal Progress", "tasks": ["Farm time-gated materials", "Use mystic forge", "Check legendary requirements"]},
        {"day": "Day 3", "focus": "Build Gear", "tasks": ["Acquire missing build items", "Run T4 fractals", "Check stat-selectable rewards"]},
        {"day": "Day 4", "focus": "Map Completion", "tasks": ["Gather volatile magic", "Farm map currencies", "Complete map dailies"]},
        {"day": "Day 5", "focus": "Fractal Push", "tasks": ["Complete T4 dailies + recs", "Work on fractal masteries", "Sell fractal junk"]},
        {"day": "Day 6", "focus": "WvW / PvP", "tasks": ["Complete weekly rewards", "Earn skirmish tickets", "Gift of Battle progress"]},
        {"day": "Day 7", "focus": "Review & Plan", "tasks": ["Review week's progress", "Plan next week's goals", "Export weekly report"]},
    ]

    if goals:
        best = max(goals, key=lambda g: g.get("progress", 0) or 0)
        base_plan[1]["tasks"].insert(0, f"Work on {best.get('name', 'legendary')} ({best.get('progress', 0):.0f}% complete)")
    if builds:
        top = builds[0]
        base_plan[2]["tasks"].insert(0, f"Acquire items for {top.get('build_name', 'build')} ({top.get('readiness_score', 0) * 100:.0f}% ready)")

    return {"plan": base_plan, "total_days": 7}
