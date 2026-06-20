import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

from gw2_progression.database import get_db, search_latest_holdings
from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.models import ItemHolding, ItemLocationResponse, ItemSearchResult
from gw2_progression.services.snapshot_service import run_full_analysis

router = APIRouter(prefix="/value", tags=["value"])

_KEY_PATTERN = re.compile(r"^[0-9A-Fa-f-]+$")


class ValueRequest(BaseModel):
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


def _holding_to_search(h: ItemHolding, snapshot_time: str = "") -> ItemSearchResult:
    return ItemSearchResult(
        item_id=h.item_id,
        count=h.count,
        location_type=h.location_type,
        location_ref=h.location_ref,
        binding_status=h.binding_status,
        tradable=h.tradable,
        price_buy=h.price_buy,
        price_sell=h.price_sell,
        value_buy=h.value_buy,
        value_sell=h.value_sell,
        valuation_status=h.valuation_status,
        snapshot_time=snapshot_time,
    )


@router.post("/analyze")
async def post_value_analyze(request: ValueRequest):
    try:
        result = await run_full_analysis(request.api_key)
        return result.model_dump()
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)


@router.get("/items/search")
async def get_items_search(
    account_name: str = Query(..., description="Account name from /analyze response"),
    q: str | None = Query(None, description="Search by item ID"),
    location: str | None = Query(None, description="Filter: bank, material_storage, character, shared_inventory, tradingpost, wallet"),
    status: str | None = Query(None, description="Filter: priced, unpriced, account_bound"),
    limit: int = Query(100, description="Max results"),
):
    try:
        db = await get_db()
        try:
            items = await search_latest_holdings(db, account_name, query=q, location_type=location, valuation_status=status, limit=limit)
            return [_holding_to_search(h).model_dump() for h in items]
        finally:
            await db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/items/locations")
async def get_item_locations(
    account_name: str = Query(..., description="Account name from /analyze response"),
    item_id: int = Query(..., description="Item ID to locate"),
):
    try:
        db = await get_db()
        try:
            items = await search_latest_holdings(db, account_name, query=str(item_id), limit=200)
            item_hits = [h for h in items if h.item_id == item_id]
            total_count = sum(h.count for h in item_hits)
            return ItemLocationResponse(
                item_id=item_id,
                total_count=total_count,
                locations=[_holding_to_search(h) for h in item_hits],
            ).model_dump()
        finally:
            await db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
