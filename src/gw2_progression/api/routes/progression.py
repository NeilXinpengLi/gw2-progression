import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.services.progression_service import (
    generate_goal_plan,
    get_requirements,
    get_templates,
)

router = APIRouter(prefix="/progression", tags=["progression"])

_KEY_PATTERN = re.compile(r"^[0-9A-Fa-f-]+$")


class GeneratePlanRequest(BaseModel):
    api_key: str
    template_id: str

    @field_validator("api_key")
    @classmethod
    def key_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 8:
            raise ValueError("API key must be at least 8 characters")
        if not _KEY_PATTERN.match(stripped):
            raise ValueError("API key contains invalid characters (expected hex + dashes)")
        return stripped


@router.get("/templates")
async def get_all_templates():
    templates = await get_templates()
    return [t.model_dump() for t in templates]


@router.get("/templates/{template_id}")
async def get_template_by_id(template_id: str):
    templates = [t for t in await get_templates() if t.template_id == template_id]
    if not templates:
        raise HTTPException(status_code=404, detail="Template not found")
    reqs = await get_requirements(template_id)
    return {"template": templates[0].model_dump(), "requirements": [r.model_dump() for r in reqs]}


@router.post("/plans")
async def post_generate_plan(request: GeneratePlanRequest):
    try:
        plan = await generate_goal_plan(api_key=request.api_key, template_id=request.template_id)
        return plan.model_dump()
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
