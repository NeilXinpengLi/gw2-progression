import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from gw2_progression.analyzer import AccountContents, fetch_all
from gw2_progression.gw2_client import Gw2ApiError

router = APIRouter(prefix="/analyze", tags=["analyze"])

_KEY_PATTERN = re.compile(r"^[0-9A-Fa-f-]+$")


class AnalyzeRequest(BaseModel):
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


@router.post("", response_model=AccountContents)
async def post_analyze(request: AnalyzeRequest) -> AccountContents:
    try:
        return await fetch_all(request.api_key)
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)
