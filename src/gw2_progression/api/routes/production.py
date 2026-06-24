"""Production API — single unified endpoint for all decisions."""

from fastapi import APIRouter, Body, HTTPException

router = APIRouter(prefix="/api/v1", tags=["production"])


@router.post("/decide")
async def api_decide(body: dict = Body(...)):
    """Unified decision endpoint. Call this for everything."""
    from gw2_progression.services.production_engine import decide

    api_key = body.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key required")

    try:
        result = await decide(
            api_key=api_key,
            account_name=body.get("account_name"),
            strategy=body.get("strategy"),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def api_feedback(body: dict = Body(...)):
    """Record user action feedback for the learning loop."""
    from gw2_progression.services.production_engine import record_feedback

    account_name = body.get("account_name", "")
    action_key = body.get("action_key", "")
    if not account_name or not action_key:
        raise HTTPException(status_code=422, detail="account_name and action_key required")

    result = await record_feedback(
        account_name=account_name,
        action_key=action_key,
        action_label=body.get("action_label", ""),
        gold_impact=body.get("gold_impact", 0),
        build_impact=body.get("build_impact", 0.0),
        legendary_impact=body.get("legendary_impact", 0.0),
        time_spent_minutes=body.get("time_spent_minutes", 0),
        success=body.get("success", True),
    )
    return result


@router.get("/strategies")
async def api_strategies():
    """List all available strategies."""
    from gw2_progression.services.v4_economic_model import STRATEGIES

    return {"strategies": [{"id": k, "name": v["name"], "desc": v["desc"], "weights": v["weights"]} for k, v in STRATEGIES.items()]}


@router.get("/health")
async def api_health():
    """Production health check."""
    return {"status": "ok", "version": "production-v1", "engine": "decision-engine"}
