"""Decision engine routes — /decide, /plan endpoints for the closed-loop system."""

from fastapi import APIRouter, Body, HTTPException

from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.services.decision_engine import decide, generate_plan

router = APIRouter(prefix="/engine", tags=["engine"])


@router.post("/decide")
async def post_decide(body: dict = Body(...)):
    """Generate ranked P0/P1/P2 actions from account state."""
    api_key = body.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key required")
    try:
        from gw2_progression.analyzer import fetch_all

        contents = await fetch_all(api_key)
        wallet_gold = sum(w.get("value", 0) for w in (contents.wallet or []) if w.get("id") == 1)

        from gw2_progression.services.build_service import get_recommendations

        builds_raw = await get_recommendations(api_key)
        builds = [{"build_id": b.build_id, "build_name": b.build_name, "readiness_score": b.readiness_score, "missing_items_count": b.missing_items_count} for b in builds_raw] if builds_raw else []

        goals = []

        result = await decide(
            account_name=contents.account_name or "unknown",
            wallet_gold=wallet_gold,
            characters=contents.characters or [],
            goals=goals,
            builds=builds,
            value_data={},
        )
        return result
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)


@router.post("/plan")
async def post_plan(body: dict = Body(...)):
    """Generate a 7-day plan from account state."""
    api_key = body.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key required")
    try:
        from gw2_progression.analyzer import fetch_all

        await fetch_all(api_key)

        from gw2_progression.services.build_service import get_recommendations

        builds_raw = await get_recommendations(api_key)
        builds = [{"build_id": b.build_id, "build_name": b.build_name, "readiness_score": b.readiness_score} for b in builds_raw] if builds_raw else []

        goals = []

        result = await generate_plan(goals=goals, builds=builds)
        return result
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)
