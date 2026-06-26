"""Goal-Driven Decision Engine — generates actionable plans from parsed goals.

Upgrades the existing decision engine with goal-aware ranking,
strategy selection, and 7-day plan generation.
"""

import logging
import uuid
from datetime import datetime, timezone

from ..models import (
    GoalType,
    ParsedGoal,
    PlanAction,
    ProgressionPlan,
)

logger = logging.getLogger("gw2.goal_driven_engine")

ACTION_WEIGHTS = {
    "gold_gain": 0.3,
    "progress_gain": 0.25,
    "build_impact": 0.2,
    "time_cost": -0.15,
    "risk": -0.1,
}

ACTION_CONFIDENCE_METADATA = {
    "SELL_ITEM": (
        0.72,
        ["gw2_account_materials", "gw2_account_bank", "gw2_commerce_prices", "curated_strategy_rules"],
        "Sell value depends on live TP demand, spread, and whether stored materials are actually tradable.",
    ),
    "BUY_ITEM": (
        0.66,
        ["gw2_commerce_prices", "curated_strategy_rules"],
        "Purchase cost can drift quickly when TP liquidity or buy/sell spread changes.",
    ),
    "CRAFT_ITEM": (
        0.78,
        ["gw2_account_materials", "gw2_recipe_tree", "gw2_commerce_prices"],
        "Crafting estimate depends on recipe coverage, owned materials, and live material prices.",
    ),
    "FARM_ACTIVITY": (
        0.68,
        ["gw2_account_characters", "curated_activity_baseline"],
        "Gold and progress yield vary by daily rotation, player skill, group quality, and market conversion.",
    ),
    "COMPLETE_ACHIEVEMENT": (
        0.74,
        ["gw2_account_progression", "curated_goal_templates"],
        "Completion effort can vary when collection steps are time-gated or account progress data is partial.",
    ),
    "IMPROVE_BUILD": (
        0.82,
        ["gw2_account_builds", "curated_build_templates", "gw2_commerce_prices"],
        "Build readiness is strongest when current equipment and missing gear prices are available.",
    ),
    "CLEAN_INVENTORY": (
        0.76,
        ["gw2_account_inventory", "gw2_account_materials", "curated_strategy_rules"],
        "Cleanup value depends on item binding, salvage choice, and whether TP valuation exists.",
    ),
}


def _confidence_from_goal(base_confidence: float, parsed: ParsedGoal) -> float:
    """Blend action rule confidence with goal parser confidence."""
    if parsed.confidence <= 0:
        return base_confidence
    return round(min(0.95, max(0.1, base_confidence * 0.75 + parsed.confidence * 0.25)), 2)


def _with_action_confidence(actions: list[PlanAction], parsed: ParsedGoal) -> list[PlanAction]:
    """Populate confidence metadata for generated plan actions."""
    for action in actions:
        base_confidence, data_sources, risk_reason = ACTION_CONFIDENCE_METADATA.get(
            action.action_type,
            (
                0.62,
                ["gw2_account_state", "curated_strategy_rules"],
                "Recommendation is based on broad account state and may need manual validation.",
            ),
        )
        if action.confidence <= 0:
            action.confidence = _confidence_from_goal(base_confidence, parsed)
        if not action.data_sources:
            action.data_sources = list(data_sources)
        if not action.risk_reason:
            action.risk_reason = risk_reason
    return actions


def _score_action(
    action_type: str,
    gold_gain: int = 0,
    progress_gain: float = 0.0,
    build_impact: float = 0.0,
    time_cost_minutes: int = 60,
    risk: float = 0.0,
    strategy: str = "balanced",
) -> float:
    """Score an action using weighted formula. Higher = better."""
    w = dict(ACTION_WEIGHTS)

    if strategy == "gold_first":
        w["gold_gain"] = 0.5
        w["build_impact"] = 0.1
        w["progress_gain"] = 0.15
    elif strategy == "fastest":
        w["time_cost"] = -0.3
        w["gold_gain"] = 0.2
    elif strategy == "cheapest":
        w["gold_gain"] = 0.2
        w["risk"] = -0.2
    elif strategy == "build_first":
        w["build_impact"] = 0.4
        w["gold_gain"] = 0.1
    elif strategy == "low_effort":
        w["time_cost"] = -0.3
        w["gold_gain"] = 0.15

    score = (
        gold_gain * w["gold_gain"]
        + progress_gain * w["progress_gain"]
        + build_impact * w["build_impact"]
        + time_cost_minutes * w["time_cost"]
        + risk * w["risk"]
    )
    return round(score, 2)


async def _extract_account_state(api_key: str) -> dict:
    """Extract key account state from GW2 API."""
    from ..analyzer import fetch_all

    contents = await fetch_all(api_key)
    account_name = contents.account_name or "unknown"

    wallet_gold = 0
    for w in contents.wallet or []:
        if w.get("id") == 1:
            wallet_gold = w.get("value", 0)

    chars = contents.characters or []
    lvl80_count = sum(1 for c in chars if c.get("level") == 80)

    return {
        "account_name": account_name,
        "wallet_gold": wallet_gold,
        "characters": chars,
        "lvl80_count": lvl80_count,
        "materials": contents.materials or [],
        "bank": contents.bank or [],
        "wallet_currencies": contents.wallet or [],
        "contents": contents,
    }


async def _get_goal_progress(api_key: str, template_id: str) -> dict | None:
    """Get progress for a specific goal template."""
    from .progression_service import generate_goal_plan

    try:
        plan = await generate_goal_plan(api_key, template_id)
        return {
            "template_id": template_id,
            "completion_percent": plan.total_completion_percent,
            "missing_cost": plan.total_missing_cost,
            "owned_value": plan.total_owned_material_value,
        }
    except Exception as e:
        logger.warning("Goal progress failed for %s: %s", template_id, e)
        return None


async def generate_plan_from_goal(
    api_key: str,
    parsed: ParsedGoal,
    account_name: str | None = None,
) -> ProgressionPlan:
    """Generate a complete progression plan from a parsed goal."""
    state = await _extract_account_state(api_key)
    acct = account_name or state["account_name"]
    strategy = parsed.strategy

    actions: list[PlanAction] = []

    # Returning player detection (before goal type dispatch)
    raw = parsed.raw_text.lower()
    is_returning = any(kw in raw for kw in ["return", "back", "came", "after", "hiatus", "break", "old account", "long time"])
    if is_returning:
        actions = await _generate_returning_actions(api_key, state, parsed)
    elif parsed.goal_type == GoalType.FINISH_LEGENDARY:
        actions = await _generate_legendary_actions(api_key, state, parsed)
    elif parsed.goal_type == GoalType.MAKE_GOLD:
        actions = await _generate_gold_actions(state, parsed)
    elif parsed.goal_type == GoalType.PREPARE_BUILD:
        actions = await _generate_build_actions(api_key, state, parsed)
    elif parsed.goal_type == GoalType.OPTIMIZE_INVENTORY:
        actions = await _generate_inventory_actions(state, parsed)
    elif parsed.goal_type == GoalType.CRAFT_ITEM:
        actions = await _generate_craft_actions(api_key, state, parsed)
    elif parsed.goal_type == GoalType.WEEKLY_PLAN:
        actions = await _generate_weekly_actions(api_key, state, parsed)

    if not actions:
        actions = await _generate_fallback_actions(api_key, state, parsed)

    # Score and sort
    for a in actions:
        a.score = _score_action(a.action_type, a.reward_gold, 0, 0, a.time_cost_minutes, strategy=strategy)
    actions.sort(key=lambda x: x.score, reverse=True)

    # Assign priorities
    for i, a in enumerate(actions):
        a.priority = i + 1

    # Assign day indices for 7-day plan
    for i, a in enumerate(actions):
        a.day_index = min(i // 3, 6)

    actions = _with_action_confidence(actions, parsed)

    # Compute totals
    total_cost = sum(a.cost_gold for a in actions)
    estimated_days = max(1, min(max(a.day_index for a in actions) + 1, 30)) if actions else 7
    completion = _estimate_completion(state, parsed)

    now = datetime.now(timezone.utc).isoformat()
    plan_id = uuid.uuid4().hex[:12]

    insight = _generate_insight(state, parsed, actions, completion)
    for action in actions:
        action.plan_id = plan_id

    return ProgressionPlan(
        plan_id=plan_id,
        account_name=acct,
        strategy=strategy,
        total_cost_copper=total_cost,
        estimated_days=estimated_days,
        completion_percent=completion,
        status="active",
        actions=actions,
        insight=insight,
        created_at=now,
    )


async def _generate_returning_actions(
    api_key: str,
    state: dict,
    parsed: ParsedGoal,
) -> list[PlanAction]:
    """Generate actions for returning/lapsed players."""
    actions: list[PlanAction] = []
    wallet_gold = state["wallet_gold"]

    # Action 1: Assess current build(s)
    try:
        from .build_service import get_recommendations
        recs = await get_recommendations(api_key)
        if recs:
            best = recs[0]
            b_gm = best.game_mode if hasattr(best, 'game_mode') else 'general'
            actions.append(PlanAction(
                action_id=uuid.uuid4().hex[:12],
                action_type="IMPROVE_BUILD",
                title=f"Re-assess your build: {best.build_name}",
                reason=f"Source: SnowCrows/MetaBattle | Readiness: {best.readiness_score:.0%} | Missing {best.missing_items_count} items | Mode: {b_gm}",
                reward_gold=0,
                cost_gold=best.missing_cost,
                time_cost_minutes=60,
                priority=1,
                status="pending",
                tab="builds",
            ))
        else:
            actions.append(PlanAction(
                action_id=uuid.uuid4().hex[:12],
                action_type="IMPROVE_BUILD",
                title="Check current meta builds",
                reason="Your builds may be outdated. Review SnowCrows/MetaBattle for current meta.",
                reward_gold=0,
                cost_gold=0,
                time_cost_minutes=30,
                priority=1,
                status="pending",
                tab="builds",
            ))
    except Exception as e:
        logger.warning("Returning build check failed: %s", e)

    # Action 2: Inventory cleanup
    actions.append(PlanAction(
        action_id=uuid.uuid4().hex[:12],
        action_type="CLEAN_INVENTORY",
        title="Audit and clean inventory",
        reason="Returning players often have valuable old items. Check bank, materials, and bags.",
        reward_gold=50000,
        cost_gold=0,
        time_cost_minutes=45,
        priority=2,
        status="pending",
        tab="inventory",
    ))

    # Action 3: Gold assessment
    if wallet_gold < 50000:
        actions.append(PlanAction(
            action_id=uuid.uuid4().hex[:12],
            action_type="FARM_ACTIVITY",
            title="Rebuild liquid gold reserves",
            reason="Low wallet. Run T4 Fractals + daily achievements to build capital.",
            reward_gold=140000,
            cost_gold=0,
            time_cost_minutes=60,
            priority=3,
            status="pending",
            tab="activities",
        ))

    # Action 4: Identify most time-sensitive goals
    try:
        from .progression_service import CURATED_TEMPLATES, generate_goal_plan
        best_goal = None
        best_pct = 0
        for t in CURATED_TEMPLATES[:3]:
            try:
                gp = await generate_goal_plan(api_key, t.template_id)
                if gp.total_completion_percent > best_pct:
                    best_pct = gp.total_completion_percent
                    best_goal = gp
            except Exception:
                continue
        if best_goal:
            actions.append(PlanAction(
                action_id=uuid.uuid4().hex[:12],
                action_type="COMPLETE_ACHIEVEMENT",
                title=f"Resume closest goal: {best_goal.template_id} ({best_pct:.0f}%)",
                reason=f"You are already {best_pct:.0f}% done. ~{best_goal.total_missing_cost // 10000}g remaining to finish.",
                reward_gold=0,
                cost_gold=best_goal.total_missing_cost,
                time_cost_minutes=120,
                priority=4,
                status="pending",
                tab="goals",
            ))
    except Exception as e:
        logger.warning("Returning goal check failed: %s", e)

    return actions


def _generate_completion_breakdown(completion: float, state: dict) -> dict:
    """Generate 4-aspect completion breakdown for legendary goals."""
    return {
        "overall": round(completion, 1),
        "material": round(min(completion * 1.1, 100), 1),
        "currency": round(min(completion * 0.8, 100), 1),
        "achievement": round(min(completion * 1.2 if completion > 30 else completion * 0.5, 100), 1),
        "time_gated": round(min(completion * 0.6, 100), 1),
    }


def _generate_insight(state: dict, parsed: ParsedGoal, actions: list[PlanAction], completion: float) -> str:
    """Generate a human-readable insight summary."""
    wallet_gold = state.get("wallet_gold", 0) // 10000
    goal_name = parsed.target_item_name or "your goal"

    if parsed.goal_type == GoalType.FINISH_LEGENDARY:
        return (
            f"You are {completion:.0f}% toward {goal_name}. "
            f"Wallet: {wallet_gold}g. "
            f"Top action: {actions[0].title if actions else 'analyze your account'}."
        )
    if parsed.goal_type == GoalType.MAKE_GOLD:
        total_reward = sum(a.reward_gold for a in actions[:3])
        return (
            f"Total earning potential: ~{total_reward}g. "
            f"Wallet: {wallet_gold}g. "
            f"Best move: {actions[0].title if actions else 'start farming'}."
        )
    if parsed.goal_type == GoalType.PREPARE_BUILD:
        return (
            f"Build readiness analyzed. "
            f"Wallet: {wallet_gold}g. "
            f"Next step: {actions[0].title if actions else 'choose a build'}."
        )
    if parsed.goal_type == GoalType.GUILD_PREPARATION:
        return (
            f"Guild account analysis. {state.get('lvl80_count', 0)} lvl80 characters. "
            f"Wallet: {wallet_gold}g. "
            f"Next step: {actions[0].title if actions else 'add guild members'}."
        )
    if parsed.raw_text and "return" in parsed.raw_text.lower() and any(kw in parsed.raw_text.lower() for kw in ["back", "return", "came", "after", "break", "hiatus", "old"]):
        return (
            f"Welcome back! Your account is worth ~{wallet_gold * 3}g. "
            f"Wallet: {wallet_gold}g. Top priority: re-assess your build and clean inventory."
        )
    return (
        f"Plan generated for '{parsed.raw_text[:60]}'. "
        f"Wallet: {wallet_gold}g. "
        f"{len(actions)} actions recommended."
    )


def _estimate_completion(state: dict, parsed: ParsedGoal) -> float:
    """Estimate completion percentage based on goal type."""
    wallet_gold = state.get("wallet_gold", 0)

    if parsed.goal_type == GoalType.FINISH_LEGENDARY:
        if parsed.target_item_id and wallet_gold > 500000:
            return max(state.get("lvl80_count", 0) * 5, 30)
        if parsed.target_item_id:
            return max(state.get("lvl80_count", 0) * 3, 15)
        return 5

    if parsed.goal_type == GoalType.MAKE_GOLD:
        return min(wallet_gold / 100000, 100) if wallet_gold > 0 else 5

    if parsed.goal_type == GoalType.PREPARE_BUILD:
        return min(state.get("lvl80_count", 0) * 10, 80)

    return 10


async def _generate_legendary_actions(
    api_key: str,
    state: dict,
    parsed: ParsedGoal,
) -> list[PlanAction]:
    """Generate actions for finishing a legendary."""
    actions: list[PlanAction] = []
    wallet_gold = state["wallet_gold"]
    goal_name = parsed.target_item_name or "your legendary"

    # Check template progress
    goal_progress = None
    if parsed.target_item_id:
        templates = ["leg_greatsword_bolt", "leg_greatsword_twilight", "leg_greatsword_sunrise",
                      "leg_staff_nevermore", "leg_staff_bifrost", "leg_axe_astralaria",
                      "leg_axe_frostfang", "leg_dagger_incinerator", "leg_back_ad_infinitum",
                      "leg_trinket_aurora", "leg_ring_vision"]
        for tid in templates:
            gp = await _get_goal_progress(api_key, tid)
            if gp:
                goal_progress = gp
                break

    # Action 1: Sell high-value materials for gold
    actions.append(PlanAction(
        action_id=uuid.uuid4().hex[:12],
        action_type="SELL_ITEM",
        title=f"Sell excess materials for {goal_name} funding",
        reason=f"Generate liquid gold to buy missing {goal_name} materials",
        reward_gold=min(max(wallet_gold // 4, 5000), 500000),
        cost_gold=0,
        time_cost_minutes=30,
        priority=1,
        status="pending",
        tab="value",
    ))

    # Action 2: Farm time-gated materials
    actions.append(PlanAction(
        action_id=uuid.uuid4().hex[:12],
        action_type="FARM_ACTIVITY",
        title=f"Farm time-gated materials for {goal_name}",
        reason="Mystic Coins, Crystalline Ore, and map currencies are time-gated",
        reward_gold=0,
        cost_gold=0,
        time_cost_minutes=60,
        priority=2,
        status="pending",
        tab="goals",
    ))

    # Action 3: Check and craft Gift components
    actions.append(PlanAction(
        action_id=uuid.uuid4().hex[:12],
        action_type="CRAFT_ITEM",
        title=f"Assemble Gift components for {goal_name}",
        reason="Gift of Mastery, Gift of Might, Gift of Magic are the key precursors",
        reward_gold=0,
        cost_gold=max(30000, wallet_gold // 3),
        time_cost_minutes=120,
        priority=3,
        status="pending",
        tab="crafting",
    ))

    if goal_progress and goal_progress["completion_percent"] > 50:
        actions.append(PlanAction(
            action_id=uuid.uuid4().hex[:12],
            action_type="COMPLETE_ACHIEVEMENT",
            title=f"Finish remaining {goal_name} collection steps",
            reason=f"You are {goal_progress['completion_percent']:.0f}% done. Complete the final collection achievements",
            reward_gold=0,
            cost_gold=goal_progress["missing_cost"],
            time_cost_minutes=180,
            priority=4,
            status="pending",
            tab="goals",
        ))

    return actions


async def _generate_gold_actions(state: dict, parsed: ParsedGoal) -> list[PlanAction]:
    """Generate gold-making actions."""
    actions: list[PlanAction] = []
    lvl80 = state.get("lvl80_count", 0)

    # T4 Fractals
    if lvl80 > 0:
        actions.append(PlanAction(
            action_id=uuid.uuid4().hex[:12],
            action_type="FARM_ACTIVITY",
            title="Run T4 Fractals dailies + recs",
            reason="~20g/day from fractal encryptions, junk, and materia",
            reward_gold=140000,
            cost_gold=0,
            time_cost_minutes=60,
            priority=1,
            status="pending",
            tab="activities",
        ))

    # Daily achievements
    actions.append(PlanAction(
        action_id=uuid.uuid4().hex[:12],
        action_type="FARM_ACTIVITY",
        title="Complete daily achievements + world bosses",
        reason="~5-10g/day from dailies, boss drops, and event rewards",
        reward_gold=70000,
        cost_gold=0,
        time_cost_minutes=45,
        priority=2,
        status="pending",
        tab="activities",
    ))

    # TP flipping
    actions.append(PlanAction(
        action_id=uuid.uuid4().hex[:12],
        action_type="BUY_ITEM",
        title="Find and flip TP opportunities",
        reason="Low-effort gold through buy/sell spreads on high-volume items",
        reward_gold=50000,
        cost_gold=30000,
        time_cost_minutes=20,
        priority=3,
        status="pending",
        tab="market",
    ))

    # Sell excess
    actions.append(PlanAction(
        action_id=uuid.uuid4().hex[:12],
        action_type="SELL_ITEM",
        title="Sell excess materials from storage",
        reason="Clean out materials above 250 stack for immediate gold",
        reward_gold=50000,
        cost_gold=0,
        time_cost_minutes=15,
        priority=4,
        status="pending",
        tab="value",
    ))

    return actions


async def _generate_build_actions(api_key: str, state: dict, parsed: ParsedGoal) -> list[PlanAction]:
    """Generate build preparation actions."""
    actions: list[PlanAction] = []
    game_mode = parsed.game_mode or "general"

    try:
        from .build_service import get_recommendations

        recs = await get_recommendations(api_key)
        if recs:
            best = recs[0]
            actions.append(PlanAction(
                action_id=uuid.uuid4().hex[:12],
                action_type="IMPROVE_BUILD",
                title=f"Equip {best.build_name} ({game_mode})",
                reason=f"Readiness: {best.readiness_score:.0%}. Missing {best.missing_items_count} items.",
                reward_gold=0,
                cost_gold=best.missing_cost,
                time_cost_minutes=120,
                priority=1,
                status="pending",
                tab="builds",
                item_id=best.missing_items_count > 0,
            ))

            actions.append(PlanAction(
                action_id=uuid.uuid4().hex[:12],
                action_type="BUY_ITEM",
                title="Purchase missing build gear from TP",
                reason=f"Acquire remaining items for {best.build_name}",
                reward_gold=0,
                cost_gold=best.missing_cost,
                time_cost_minutes=30,
                priority=2,
                status="pending",
                tab="builds",
            ))
    except Exception as e:
        logger.warning("Build recommendations failed: %s", e)
        actions.append(PlanAction(
            action_id=uuid.uuid4().hex[:12],
            action_type="FARM_ACTIVITY",
            title=f"Farm {game_mode} for gear acquisition",
            reason=f"Run {game_mode} content to earn currencies for stat-selectable gear",
            reward_gold=100000,
            cost_gold=0,
            time_cost_minutes=120,
            priority=1,
            status="pending",
            tab="builds",
        ))

    return actions


async def _generate_inventory_actions(state: dict, parsed: ParsedGoal) -> list[PlanAction]:
    """Generate inventory optimization actions."""
    actions: list[PlanAction] = []

    actions.append(PlanAction(
        action_id=uuid.uuid4().hex[:12],
        action_type="CLEAN_INVENTORY",
        title="Salvage all masterwork/rare gear",
        reason="Clear inventory space and get crafting materials + luck",
        reward_gold=10000,
        cost_gold=0,
        time_cost_minutes=20,
        priority=1,
        status="pending",
        tab="inventory",
    ))

    actions.append(PlanAction(
        action_id=uuid.uuid4().hex[:12],
        action_type="SELL_ITEM",
        title="List excess materials on TP",
        reason="Sell materials above 250 stack threshold for immediate gold",
        reward_gold=30000,
        cost_gold=0,
        time_cost_minutes=15,
        priority=2,
        status="pending",
        tab="value",
    ))

    actions.append(PlanAction(
        action_id=uuid.uuid4().hex[:12],
        action_type="CLEAN_INVENTORY",
        title="Deposit all materials to material storage",
        reason="Free up bank and inventory space using 'Deposit Materials' button",
        reward_gold=0,
        cost_gold=0,
        time_cost_minutes=5,
        priority=3,
        status="pending",
        tab="inventory",
    ))

    return actions


async def _generate_craft_actions(api_key: str, state: dict, parsed: ParsedGoal) -> list[PlanAction]:
    """Generate item crafting actions."""
    actions: list[PlanAction] = []

    if parsed.target_item_id > 0:
        try:
            from .crafting_plan_service import create_plan

            plan = await create_plan(api_key, parsed.target_item_id, 1, True)
            actions.append(PlanAction(
                action_id=uuid.uuid4().hex[:12],
                action_type="CRAFT_ITEM",
                title=f"Craft {parsed.target_item_name}",
                reason=f"Missing cost: {plan.missing_material_cost // 10000}g, owned: {plan.owned_material_value_used // 10000}g",
                reward_gold=0,
                cost_gold=plan.missing_material_cost,
                time_cost_minutes=180,
                priority=1,
                status="pending",
                tab="crafting",
            ))

            # Shopping list
            missing_lines = [ln for ln in plan.lines if ln.missing_count > 0]
            if missing_lines:
                top_missing = missing_lines[0]
                actions.append(PlanAction(
                    action_id=uuid.uuid4().hex[:12],
                    action_type="BUY_ITEM",
                    title=f"Buy {top_missing.missing_count}x {top_missing.item_id} from TP",
                    reason=f"Missing material for {parsed.target_item_name}",
                    reward_gold=0,
                    cost_gold=top_missing.missing_buy_cost,
                    time_cost_minutes=10,
                    priority=2,
                    status="pending",
                    tab="crafting",
                ))
        except Exception as e:
            logger.warning("Craft plan failed: %s", e)

    return actions


async def _generate_weekly_actions(api_key: str, state: dict, parsed: ParsedGoal) -> list[PlanAction]:
    """Generate a weekly plan as actions."""
    actions: list[PlanAction] = []

    action_templates = [
        ("Sell & Liquidate", "Sell excess materials and consolidate gold for the week", "SELL_ITEM", 50000, 0, 30, 0),
        ("Goal Progress", "Farm time-gated materials, check legendary requirements", "FARM_ACTIVITY", 0, 0, 60, 1),
        ("Build Gear", "Run fractals/strikes for ascended gear drops", "FARM_ACTIVITY", 100000, 0, 90, 2),
        ("Map Completion", "Gather volatile magic and map currencies", "FARM_ACTIVITY", 0, 0, 60, 3),
        ("Fractal Push", "Complete T4 dailies + recs for gold + gear", "FARM_ACTIVITY", 140000, 0, 60, 4),
        ("WvW / PvP", "Earn skirmish tickets / pvp league rewards", "FARM_ACTIVITY", 30000, 0, 45, 5),
        ("Review & Plan", "Review weekly progress and plan next week", "COMPLETE_ACHIEVEMENT", 0, 0, 30, 6),
    ]

    for title, reason, action_type, reward, cost, time_cost, day_idx in action_templates:
        actions.append(PlanAction(
            action_id=uuid.uuid4().hex[:12],
            action_type=action_type,
            title=title,
            reason=reason,
            reward_gold=reward,
            cost_gold=cost,
            time_cost_minutes=time_cost,
            priority=day_idx + 1,
            status="pending",
            tab="activities",
            day_index=day_idx,
        ))

    return actions


async def _generate_fallback_actions(api_key: str, state: dict, parsed: ParsedGoal) -> list[PlanAction]:
    """Generate fallback actions when goal type is unclear."""
    actions: list[PlanAction] = []

    actions.append(PlanAction(
        action_id=uuid.uuid4().hex[:12],
        action_type="FARM_ACTIVITY",
        title="Complete daily achievements + T4 fractals",
        reason="Best consistent gold income. ~20g/day from dailies + fractals.",
        reward_gold=140000,
        cost_gold=0,
        time_cost_minutes=60,
        priority=1,
        status="pending",
        tab="activities",
    ))

    actions.append(PlanAction(
        action_id=uuid.uuid4().hex[:12],
        action_type="SELL_ITEM",
        title="Review and sell excess materials",
        reason="Clean material storage for immediate gold",
        reward_gold=30000,
        cost_gold=0,
        time_cost_minutes=15,
        priority=2,
        status="pending",
        tab="value",
    ))

    try:
        from .progression_service import CURATED_TEMPLATES, generate_goal_plan

        best_goal = None
        best_pct = 0
        for t in CURATED_TEMPLATES[:3]:
            try:
                gp = await generate_goal_plan(api_key, t.template_id)
                if gp.total_completion_percent > best_pct:
                    best_pct = gp.total_completion_percent
                    best_goal = gp
            except Exception:
                continue

        if best_goal:
            actions.append(PlanAction(
                action_id=uuid.uuid4().hex[:12],
                action_type="COMPLETE_ACHIEVEMENT",
                title=f"Work on {best_goal.template_id} ({best_goal.total_completion_percent:.0f}%)",
                reason=f"Closest goal. ~{best_goal.total_missing_cost // 10000}g remaining.",
                reward_gold=0,
                cost_gold=best_goal.total_missing_cost,
                time_cost_minutes=120,
                priority=3,
                status="pending",
                tab="goals",
            ))
    except Exception:
        pass

    return actions


async def revise_plan(
    plan: ProgressionPlan,
    revision_text: str,
    api_key: str | None = None,
) -> tuple[ProgressionPlan, str, list[str]]:
    """Revise an existing plan based on user feedback."""
    t = revision_text.lower()
    changed: list[str] = []
    delta_summary_parts: list[str] = []

    new_strategy = plan.strategy

    if any(kw in t for kw in ["cheap", "cheapest", "frugal", "budget", "economy"]):
        new_strategy = "cheapest"
        delta_summary_parts.append("Strategy changed to Frugal Path")
        delta_summary_parts.append("Reducing gold costs, increasing time")

    elif any(kw in t for kw in ["fast", "fastest", "rush", "speed"]):
        new_strategy = "fastest"
        delta_summary_parts.append("Strategy changed to Fast Path")
        delta_summary_parts.append("Increasing gold spend to save time")

    elif any(kw in t for kw in ["gold", "money", "profit"]):
        new_strategy = "gold_first"
        delta_summary_parts.append("Focus shifted to gold generation")
        delta_summary_parts.append("Prioritizing income actions")

    elif any(kw in t for kw in ["build", "gear"]):
        new_strategy = "build_first"
        delta_summary_parts.append("Focus shifted to build completion")
        delta_summary_parts.append("Prioritizing gear acquisition")

    # Exclusions
    for exclude_word in ["wvw", "pvp", "fractal", "raid", "strike", "open world", "tp", "trading"]:
        if f"no {exclude_word}" in t or f"avoid {exclude_word}" in t or f"without {exclude_word}" in t:
            removed = [a for a in plan.actions if exclude_word not in a.reason.lower() and exclude_word not in a.title.lower()]
            if len(removed) < len(plan.actions):
                changed.append(f"Removed {len(plan.actions) - len(removed)} action(s) involving {exclude_word}")
                plan.actions = removed
            break

    if delta_summary_parts:
        plan.strategy = new_strategy
        # Re-score actions with new strategy
        for a in plan.actions:
            a.score = _score_action(a.action_type, a.reward_gold, 0, 0, a.time_cost_minutes, strategy=new_strategy)
        plan.actions.sort(key=lambda x: x.score, reverse=True)
        for i, a in enumerate(plan.actions):
            a.priority = i + 1

        # Recompute total
        plan.total_cost_copper = sum(a.cost_gold for a in plan.actions)
        plan.estimated_days = max(1, min(max(a.day_index for a in plan.actions) + 1, 30)) if plan.actions else 7

    delta_summary = ". ".join(delta_summary_parts) if delta_summary_parts else "Plan adjusted based on your feedback."
    return plan, delta_summary, changed


async def generate_progressive_result(api_key: str) -> dict:
    """Generate progressive loading results (stage 1-4)."""
    from ..analyzer import fetch_all

    contents = await fetch_all(api_key)

    wallet_gold = 0
    for w in contents.wallet or []:
        if w.get("id") == 1:
            wallet_gold = w.get("value", 0)

    result = {
        "stage": 1,
        "account_name": contents.account_name or "unknown",
        "wallet_gold": wallet_gold,
        "character_count": len(contents.characters or []),
        "ready": True,
    }

    return result
