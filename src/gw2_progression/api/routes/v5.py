"""v5 Self-Evolving API — experience recording, personalized weights, learning."""

from fastapi import APIRouter, Body, HTTPException

from gw2_progression.services.v4_economic_model import STRATEGIES
from gw2_progression.services.v4_optimizer import generate_explainable_actions
from gw2_progression.services.v5_learning import (
    get_personalized_weights,
    get_recent_experiences,
    get_user_model,
    record_experience,
    update_preferred_strategy,
)

router = APIRouter(prefix="/v5", tags=["v5"])


@router.post("/experience")
async def post_experience(body: dict = Body(...)):
    """Record a user action and its outcome for learning."""
    account_name = body.get("account_name", "")
    action_key = body.get("action_key", "")
    if not account_name or not action_key:
        raise HTTPException(status_code=422, detail="account_name and action_key required")

    result = await record_experience(
        account_name=account_name,
        action_key=action_key,
        action_label=body.get("action_label", ""),
        strategy=body.get("strategy", "hybrid"),
        gold_impact=body.get("gold_impact", 0),
        build_impact=body.get("build_impact", 0.0),
        legendary_impact=body.get("legendary_impact", 0.0),
        time_spent_minutes=body.get("time_spent_minutes", 0),
        success=body.get("success", True),
    )
    return result


@router.get("/model/{account_name}")
async def get_model(account_name: str):
    """Get personalized user model with learned weights."""
    return await get_user_model(account_name)


@router.get("/weights/{account_name}")
async def get_weights(account_name: str):
    """Get personalized decision weights for a user."""
    weights = await get_personalized_weights(account_name)
    default_w = {"gold_weight": 0.3, "build_weight": 0.3, "legendary_weight": 0.3, "time_weight": -0.2, "risk_weight": -0.05}
    source = "learned" if weights != default_w else "default"
    return {"account_name": account_name, "weights": weights, "source": source}


@router.get("/experiences/{account_name}")
async def get_experiences(account_name: str, limit: int = 20):
    """Get recent experiences for a user."""
    return await get_recent_experiences(account_name, limit)


@router.post("/decide")
async def v5_decide(body: dict = Body(...)):
    """Personalized decision — uses learned weights from user history."""
    api_key = body.get("api_key", "")
    account_name = body.get("account_name", "")
    strategy = body.get("strategy", "")
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key required")

    try:
        from gw2_progression.analyzer import fetch_all

        contents = await fetch_all(api_key)
        name = account_name or contents.account_name or "unknown"

        from gw2_progression.services.build_service import get_recommendations

        builds_raw = await get_recommendations(api_key)
        builds = [{"build_id": b.build_id, "build_name": b.build_name, "readiness_score": b.readiness_score, "missing_items_count": b.missing_items_count} for b in builds_raw] if builds_raw else []

        # If no strategy specified, use user's preferred strategy
        if not strategy:
            model = await get_user_model(name)
            strategy = model.get("preferred_strategy", "hybrid")

        account_data = {
            "wallet": [{"id": 1, "value": sum(w.get("value", 0) for w in (contents.wallet or []) if w.get("id") == 1)}],
            "characters": contents.characters or [],
        }

        result = generate_explainable_actions(
            account_data=account_data,
            value_data={},
            builds=builds,
            goals=[],
            strategy=strategy,
        )

        # Attach personalized weights
        weights = await get_personalized_weights(name)
        result["personalized_weights"] = weights
        result["account_name"] = name
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy/evolve")
async def evolve_strategy(body: dict = Body(...)):
    """Auto-evolve strategy based on user's experience history."""
    account_name = body.get("account_name", "")
    if not account_name:
        raise HTTPException(status_code=422, detail="account_name required")

    model = await get_user_model(account_name)
    weights = model

    # Determine best strategy from weights
    gold_aff = weights.get("gold_weight", 0.3)
    build_aff = weights.get("build_weight", 0.3)
    leg_aff = weights.get("legendary_weight", 0.3)

    if gold_aff > build_aff and gold_aff > leg_aff:
        best = "gold"
    elif build_aff > gold_aff and build_aff > leg_aff:
        best = "build"
    elif leg_aff > gold_aff and leg_aff > build_aff:
        best = "legendary"
    else:
        best = "hybrid"

    await update_preferred_strategy(account_name, best)

    return {
        "account_name": account_name,
        "evolved_strategy": best,
        "strategy_name": STRATEGIES.get(best, {}).get("name", "Balanced"),
        "weights": {k: v for k, v in weights.items() if k.endswith("_weight")},
    }
