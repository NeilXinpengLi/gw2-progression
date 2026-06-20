import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.services.recipe_service import calculate

router = APIRouter(prefix="/crafting", tags=["crafting"])

_KEY_PATTERN = re.compile(r"^[0-9A-Fa-f-]+$")


class CraftCalcRequest(BaseModel):
    api_key: str
    target_item_id: int
    quantity: int = 1
    use_owned: bool = True

    @field_validator("api_key")
    @classmethod
    def key_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 8:
            raise ValueError("API key must be at least 8 characters")
        if not _KEY_PATTERN.match(stripped):
            raise ValueError("API key contains invalid characters (expected hex + dashes)")
        return stripped

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        return v

    @field_validator("target_item_id")
    @classmethod
    def item_id_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Invalid item ID")
        return v


@router.post("/calculate")
async def post_crafting_calculate(request: CraftCalcRequest):
    try:
        result = await calculate(
            api_key=request.api_key,
            target_item_id=request.target_item_id,
            quantity=request.quantity,
            use_owned=request.use_owned,
        )
        return result.model_dump()
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)
