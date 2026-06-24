"""v4 API routes — explainable optimization engine endpoints."""

from fastapi import APIRouter, Body, HTTPException

from gw2_progression.services.v4_economic_model import STRATEGIES
from gw2_progression.services.v4_optimizer import generate_explainable_actions, optimize_paths

router = APIRouter(prefix="/v4", tags=["v4"])


@router.get("/strategies")
def list_strategies():
    """List all available optimization strategies with weights."""
    return {"strategies": [{"id": k, "name": v["name"], "desc": v["desc"], "weights": v["weights"]} for k, v in STRATEGIES.items()]}


@router.get("/strategy/{strategy_id}")
def get_strategy(strategy_id: str):
    if strategy_id not in STRATEGIES:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")
    s = STRATEGIES[strategy_id]
    return {"id": strategy_id, "name": s["name"], "desc": s["desc"], "weights": s["weights"]}


@router.post("/decide")
async def v4_decide(body: dict = Body(...)):
    """Explainable decision — returns scored, ranked actions with breakdown."""
    api_key = body.get("api_key", "")
    strategy = body.get("strategy", "hybrid")
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key required")
    if strategy not in STRATEGIES:
        raise HTTPException(status_code=422, detail=f"Invalid strategy '{strategy}'")

    try:
        from gw2_progression.analyzer import fetch_all

        contents = await fetch_all(api_key)

        from gw2_progression.services.build_service import get_recommendations

        builds_raw = await get_recommendations(api_key)
        builds = [{"build_id": b.build_id, "build_name": b.build_name, "readiness_score": b.readiness_score, "missing_items_count": b.missing_items_count} for b in builds_raw] if builds_raw else []

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
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain")
async def v4_explain(body: dict = Body(...)):
    """Explain a specific action's score breakdown."""
    from gw2_progression.services.v4_economic_model import PricePoint, score_action

    action = body.get("action", {})
    strategy = body.get("strategy", "hybrid")
    if not action:
        raise HTTPException(status_code=422, detail="action required")

    price = PricePoint(
        buy_price=body.get("buy_price", 0),
        sell_price=body.get("sell_price", 0),
        buy_qty=body.get("buy_qty", 0),
        sell_qty=body.get("sell_qty", 0),
    )

    result = score_action(action, price, strategy)
    return {
        "action": action.get("action", "unknown"),
        "explanation": result,
        "strategy": strategy,
        "strategy_name": STRATEGIES.get(strategy, {}).get("name", "Unknown"),
    }


@router.post("/optimize")
async def v4_optimize(body: dict = Body(...)):
    """Generate multiple optimized paths to a goal."""
    api_key = body.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key required")

    try:
        from gw2_progression.services.build_service import get_recommendations

        builds_raw = await get_recommendations(api_key)
        builds = [{"build_id": b.build_id, "build_name": b.build_name, "readiness_score": b.readiness_score} for b in builds_raw] if builds_raw else []

        goals = [{"name": b.get("build_name", "Build"), "progress": b.get("readiness_score", 0) * 100} for b in builds[:3]]

        return optimize_paths(goals=goals)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
