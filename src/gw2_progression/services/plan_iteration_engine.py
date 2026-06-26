"""Plan Iteration Engine — handles user revision requests on generated plans.

Supports strategy changes, constraint updates, and content exclusions
with delta summaries explaining what changed.
"""

import logging
import uuid
from datetime import datetime, timezone

from ..models import PlanRevision, ProgressionPlan

logger = logging.getLogger("gw2.plan_iteration")

REVISION_PATTERNS = {
    "change_strategy": [
        "cheaper", "cheapest", "frugal", "budget", "economy",
        "faster", "fastest", "rush", "speed", "quick",
        "gold", "money", "profit", "income",
        "build", "gear", "equip",
        "easier", "easier", "simple", "lazy", "casual",
    ],
    "change_time_budget": [
        r"(\d+)\s*hour",
        r"(\d+)\s*min",
        r"only\s+(\d+)",
        r"limited\s+time",
    ],
    "change_goal": [
        "ignore", "forget", "skip", "drop",
        "instead", "change", "switch", "different",
    ],
    "exclude_activity": [
        "no wvw", "avoid wvw", "without wvw",
        "no pvp", "avoid pvp",
        "no fractal", "avoid fractal",
        "no raid", "avoid raid",
        "no tp", "avoid tp", "no trading",
        "no strike", "avoid strike",
    ],
    "reduce_cost": [
        "too expensive", "too costly", "expensive",
        "save gold", "save money", "cheaper",
        "reduce cost", "lower cost", "cut cost",
    ],
    "reduce_complexity": [
        "too complex", "too complicated", "too many",
        "simplify", "easier", "simpler",
        "fewer steps", "less",
    ],
}


def classify_revision(text: str) -> list[str]:
    """Classify the type of revision requested."""
    t = text.lower()
    types: list[str] = []
    for rev_type, patterns in REVISION_PATTERNS.items():
        if rev_type == "change_time_budget":
            import re
            for p in patterns:
                if re.search(p, t):
                    types.append(rev_type)
                    break
        elif rev_type == "exclude_activity":
            if any(p in t for p in patterns):
                types.append(rev_type)
        else:
            if any(p in t for p in patterns):
                types.append(rev_type)
    return types if types else ["unknown"]


def _extract_time_budget(text: str) -> int:
    """Extract time budget from revision text in minutes."""
    import re
    t = text.lower()
    for pat, mult in [(r"(\d+)\s*hour", 60), (r"(\d+)\s*hr", 60), (r"(\d+)\s*min", 1)]:
        m = re.search(pat, t)
        if m:
            return int(m.group(1)) * mult
    return 0


async def apply_revision(
    plan: ProgressionPlan,
    revision_text: str,
    api_key: str | None = None,
) -> tuple[ProgressionPlan, PlanRevision]:
    """Apply a revision to a plan and return the updated plan + revision record."""
    revision_types = classify_revision(revision_text)
    now = datetime.now(timezone.utc).isoformat()
    old_strategy = plan.strategy
    changed_actions: list[str] = []
    delta_parts: list[str] = []

    # Handle strategy changes
    if "change_strategy" in revision_types:
        t = revision_text.lower()
        if any(kw in t for kw in ["cheap", "frugal", "budget", "economy"]):
            plan.strategy = "cheapest"
            delta_parts.append("Strategy changed from Balanced to Frugal")
            delta_parts.append("Actions reordered to minimize gold spend")
        elif any(kw in t for kw in ["fast", "rush", "speed"]):
            plan.strategy = "fastest"
            delta_parts.append("Strategy changed from Balanced to Fast")
            delta_parts.append("Actions reordered to minimize time")
        elif any(kw in t for kw in ["gold", "money", "profit", "income"]):
            plan.strategy = "gold_first"
            delta_parts.append("Focus shifted to gold generation")
        elif any(kw in t for kw in ["build", "gear", "equip"]):
            plan.strategy = "build_first"
            delta_parts.append("Focus shifted to build preparation")

    # Handle time budget changes
    if "change_time_budget" in revision_types:
        minutes = _extract_time_budget(revision_text)
        if minutes > 0:
            # Filter actions that fit within time budget
            fitting = [a for a in plan.actions if a.time_cost_minutes <= minutes]
            if fitting:
                removed_count = len(plan.actions) - len(fitting)
                delta_parts.append(f"Time budget: {minutes}min/day. {removed_count} longer actions removed.")
                plan.actions = fitting
            else:
                # Keep the shortest actions
                sorted_actions = sorted(plan.actions, key=lambda x: x.time_cost_minutes)
                plan.actions = sorted_actions[:3]
                delta_parts.append(f"Time budget: {minutes}min/day. Reduced to {len(plan.actions)} shortest actions.")

    # Handle exclusions
    if "exclude_activity" in revision_types:
        t = revision_text.lower()
        excluded_activities = []
        if "no wvw" in t or "avoid wvw" in t or "without wvw" in t:
            excluded_activities.append("wvw")
        if "no pvp" in t or "avoid pvp" in t:
            excluded_activities.append("pvp")
        if "no fractal" in t or "avoid fractal" in t:
            excluded_activities.append("fractal")
        if "no raid" in t or "avoid raid" in t:
            excluded_activities.append("raid")
        if "no tp" in t or "avoid tp" in t or "no trading" in t:
            excluded_activities.append("tp")

        for excluded in excluded_activities:
            before = len(plan.actions)
            plan.actions = [
                a for a in plan.actions
                if excluded not in a.title.lower() and excluded not in a.reason.lower()
            ]
            removed = before - len(plan.actions)
            if removed > 0:
                changed_actions.append(f"{excluded}")
                delta_parts.append(f"Removed {removed} action(s) involving {excluded.upper()}.")

    # Handle cost reduction
    if "reduce_cost" in revision_types or "reduce_complexity" in revision_types:
        # Remove highest-cost actions, keep lowest
        sorted_by_cost = sorted(plan.actions, key=lambda x: x.cost_gold)
        if plan.actions and sorted_by_cost[0].cost_gold < plan.actions[-1].cost_gold:
            keep_count = max(len(plan.actions) // 2, 3)
            removed = len(plan.actions) - keep_count
            old_cost = sum(a.cost_gold for a in plan.actions)
            plan.actions = sorted_by_cost[:keep_count]
            new_cost = sum(a.cost_gold for a in plan.actions)
            delta_parts.append(f"Removed {removed} most expensive actions. Cost reduced from {old_cost // 10000}g to {new_cost // 10000}g.")

    # Re-score with new strategy
    from .goal_driven_engine import _score_action
    for a in plan.actions:
        a.score = _score_action(a.action_type, a.reward_gold, 0, 0, a.time_cost_minutes, strategy=plan.strategy)
    plan.actions.sort(key=lambda x: x.score, reverse=True)
    for i, a in enumerate(plan.actions):
        a.priority = i + 1
        a.day_index = min(i // 3, 6)

    # Recompute totals
    plan.total_cost_copper = sum(a.cost_gold for a in plan.actions)
    plan.estimated_days = max(1, min(max(a.day_index for a in plan.actions) + 1, 30)) if plan.actions else 7

    delta_summary = " ".join(delta_parts) if delta_parts else "Plan adjusted based on your feedback."

    try:
        from ..ontology.goal_mapper import sync_goal_reservations
        await sync_goal_reservations(plan.account_name)
    except Exception as e:
        logger.debug("Ontology reservation sync on revision skipped (non-blocking): %s", e)

    revision = PlanRevision(
        revision_id=uuid.uuid4().hex[:12],
        plan_id=plan.plan_id,
        user_request=revision_text,
        previous_strategy=old_strategy,
        new_strategy=plan.strategy,
        delta_summary=delta_summary,
        created_at=now,
    )

    return plan, revision
