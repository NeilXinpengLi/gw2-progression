import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.models import CoachPlanResponse, ProgressionAdvice
from gw2_progression.services.agent_service import generate_advice, generate_coach_plan, generate_weekly_plan

router = APIRouter(prefix="/agent", tags=["agent"])

_KEY_PATTERN = re.compile(r"^[0-9A-Fa-f-]+$")


class AgentRequest(BaseModel):
    api_key: str

    @field_validator("api_key")
    @classmethod
    def key_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 8:
            raise ValueError("API key must be at least 8 characters")
        if not _KEY_PATTERN.match(stripped):
            raise ValueError("API key contains invalid characters (expected hex + dashes)")
        return stripped


@router.post("/progression/advice", response_model=ProgressionAdvice)
async def post_advice(request: AgentRequest):
    try:
        advice = await generate_advice(request.api_key)
        return advice.model_dump()
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)


@router.post("/progression/weekly-plan")
async def post_weekly_plan(request: AgentRequest):
    try:
        plan = await generate_weekly_plan(request.api_key)
        return {"weekly_plan": plan}
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)


@router.post("/coach-plan", response_model=CoachPlanResponse)
async def post_coach_plan(request: AgentRequest):
    """Generate a prioritized, behavior-driven coach plan (P0/P1/P2 + daily plan)."""
    try:
        plan = await generate_coach_plan(request.api_key)
        return plan
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)
