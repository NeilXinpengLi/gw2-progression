import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.services.goal_service import create_goal, delete_goal, get_goal, get_goals, refresh_goal

router = APIRouter(prefix="/goals", tags=["goals"])

_KEY_PATTERN = re.compile(r"^[0-9A-Fa-f-]+$")


class CreateGoalRequest(BaseModel):
    api_key: str
    target_item_id: int
    target_count: int = 1
    priority: str = "normal"

    @field_validator("api_key")
    @classmethod
    def key_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 8:
            raise ValueError("API key must be at least 8 characters")
        if not _KEY_PATTERN.match(stripped):
            raise ValueError("API key contains invalid characters (expected hex + dashes)")
        return stripped


class RefreshGoalRequest(BaseModel):
    api_key: str


@router.post("")
async def post_create_goal(request: CreateGoalRequest):
    try:
        goal = await create_goal(
            api_key=request.api_key,
            target_item_id=request.target_item_id,
            target_count=request.target_count,
            priority=request.priority,
        )
        return goal.model_dump()
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)


@router.get("")
async def get_all_goals(account_name: str = Query(...)):
    goals = await get_goals(account_name)
    return [g.model_dump() for g in goals]


@router.get("/{goal_id}")
async def get_goal_by_id(goal_id: str):
    goal = await get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal.model_dump()


@router.post("/{goal_id}/refresh")
async def post_refresh_goal(goal_id: str, request: RefreshGoalRequest):
    try:
        goal = await refresh_goal(api_key=request.api_key, goal_id=goal_id)
        return goal.model_dump()
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{goal_id}")
async def delete_goal_by_id(goal_id: str):
    deleted = await delete_goal(goal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"status": "deleted"}
