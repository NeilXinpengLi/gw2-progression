"""Production Decision Engine — single source of truth for all decisions.
Converges v1-v5 into one unified endpoint."""

from gw2_progression.services.v4_economic_model import STRATEGIES
from gw2_progression.services.v4_optimizer import generate_explainable_actions
from gw2_progression.services.v5_learning import get_personalized_weights, record_experience

DEFAULT_STRATEGY = "hybrid"


async def decide(
    api_key: str,
    account_name: str | None = None,
    strategy: str | None = None,
) -> dict:
    """Unified decision endpoint — single source of truth."""
    from gw2_progression.analyzer import fetch_all
    from gw2_progression.services.build_service import get_recommendations

    contents = await fetch_all(api_key)
    name = account_name or contents.account_name or "unknown"

    # Get personalized weights
    weights = await get_personalized_weights(name)
    effective_strategy = strategy or "hybrid"

    # Get builds
    builds_raw = await get_recommendations(api_key)
    builds = (
        [
            {
                "build_id": b.build_id,
                "build_name": b.build_name,
                "readiness_score": b.readiness_score,
                "missing_items_count": b.missing_items_count,
            }
            for b in builds_raw
        ]
        if builds_raw
        else []
    )

    # Compute account state
    wallet_gold = sum(w.get("value", 0) for w in (contents.wallet or []) if w.get("id") == 1)
    account_data = {
        "wallet": [{"id": 1, "value": wallet_gold}],
        "characters": contents.characters or [],
    }

    # Generate actions via v4 engine
    actions = generate_explainable_actions(
        account_data=account_data,
        value_data={},
        builds=builds,
        goals=[],
        strategy=effective_strategy,
    )

    # Attach metadata
    actions["account_name"] = name
    actions["personalized_weights"] = weights
    actions["strategy_name"] = STRATEGIES.get(effective_strategy, {}).get("name", "Balanced")

    return actions


async def record_feedback(
    account_name: str,
    action_key: str,
    action_label: str = "",
    gold_impact: int = 0,
    build_impact: float = 0.0,
    legendary_impact: float = 0.0,
    time_spent_minutes: int = 0,
    success: bool = True,
) -> dict:
    """Record user action feedback for the learning loop."""
    return await record_experience(
        account_name=account_name,
        action_key=action_key,
        action_label=action_label,
        gold_impact=gold_impact,
        build_impact=build_impact,
        legendary_impact=legendary_impact,
        time_spent_minutes=time_spent_minutes,
        success=success,
    )
