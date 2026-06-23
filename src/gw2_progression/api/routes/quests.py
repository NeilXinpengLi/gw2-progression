from fastapi import APIRouter, Body, HTTPException

from gw2_progression.services.quest_service import get_week_summary, toggle_quest

router = APIRouter(prefix="/quests", tags=["quests"])


@router.get("/{account_name}")
async def get_quests(account_name: str):
    return await get_week_summary(account_name)


@router.post("/{account_name}/toggle")
async def post_toggle_quest(account_name: str, body: dict = Body(...)):
    quest_key = body.get("quest_key", "")
    completed = body.get("completed", False)
    day_index = body.get("day_index", -1)
    if not quest_key:
        raise HTTPException(status_code=422, detail="quest_key required")
    return await toggle_quest(account_name, quest_key, completed, day_index)
