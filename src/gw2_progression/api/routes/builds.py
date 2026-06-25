import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.models import AccountBuildReadiness, BuildTemplate
from gw2_progression.services.build_service import (
    calculate_readiness,
    get_all_builds,
    get_build,
    get_recommendations,
)

router = APIRouter(prefix="/builds", tags=["builds"])

_KEY_PATTERN = re.compile(r"^[0-9A-Fa-f-]+$")


class ReadinessRequest(BaseModel):
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


@router.get("/templates", response_model=list[BuildTemplate])
async def get_builds():
    builds = get_all_builds()
    return [b.model_dump() for b in builds]


@router.get("/templates/{build_id}", response_model=BuildTemplate)
async def get_build_by_id(build_id: str):
    build = get_build(build_id)
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    return build.model_dump()


@router.post("/recommendations", response_model=list[AccountBuildReadiness])
async def post_recommendations(request: ReadinessRequest):
    try:
        recommendations = await get_recommendations(request.api_key)
        return [r.model_dump() for r in recommendations]
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)


@router.post("/readiness/{build_id}", response_model=AccountBuildReadiness)
async def post_readiness(build_id: str, request: ReadinessRequest):
    try:
        readiness = await calculate_readiness(request.api_key, build_id)
        return readiness.model_dump()
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
