from fastapi import HTTPException
from fastapi import APIRouter
from pydantic import BaseModel

from gw2_progression.analyzer import AccountContents, fetch_all
from gw2_progression.gw2_client import Gw2ApiError

router = APIRouter(prefix="/analyze", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    api_key: str


@router.post("", response_model=AccountContents)
def post_analyze(request: AnalyzeRequest) -> AccountContents:
    try:
        return fetch_all(request.api_key)
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)
