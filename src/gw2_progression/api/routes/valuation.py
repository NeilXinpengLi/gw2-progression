import re

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, field_validator

from gw2_progression.database import cleanup_old_data, get_db, search_latest_holdings
from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.models import ItemHolding, ItemLocationResponse, ItemSearchResult
from gw2_progression.services.delta_service import compare_snapshots, get_latest_snapshots
from gw2_progression.services.item_search_service import get_filtered_items, get_item_detail, search_items_by_name
from gw2_progression.services.listing_service import analyze_depth, fetch_listings
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
    q: str | None = Query(None, description="Search by item ID or name"),
    location: str | None = Query(None, description="Filter by location type"),
    status: str | None = Query(None, description="Filter by valuation status"),
    limit: int = Query(100, description="Max results"),
):
    try:
        if not q:
            return []
        items = await search_items_by_name(account_name, q, location, status, limit)
        return [_holding_to_search(h).model_dump() for h in items]
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


@router.get("/items/{item_id}/detail")
async def get_item_detail_endpoint(
    account_name: str = Query(..., description="Account name from /analyze response"),
    item_id: int = Path(..., description="Item ID"),
):
    try:
        return await get_item_detail(account_name, item_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/items/high-value")
async def get_high_value_items(
    account_name: str = Query(..., description="Account name from /analyze response"),
    limit: int = Query(100, description="Max results"),
):
    try:
        items = await get_filtered_items(account_name, "high_value", limit)
        return [_holding_to_search(h).model_dump() for h in items]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/items/unpriced")
async def get_unpriced_items(
    account_name: str = Query(..., description="Account name from /analyze response"),
    limit: int = Query(100, description="Max results"),
):
    try:
        items = await get_filtered_items(account_name, "unpriced", limit)
        return [_holding_to_search(h).model_dump() for h in items]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/items/account-bound")
async def get_account_bound_items(
    account_name: str = Query(..., description="Account name from /analyze response"),
    limit: int = Query(100, description="Max results"),
):
    try:
        items = await get_filtered_items(account_name, "account_bound", limit)
        return [_holding_to_search(h).model_dump() for h in items]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/delta")
async def get_value_delta(
    account_name: str = Query(..., description="Account name from /analyze response"),
    from_id: int | None = Query(None, description="From snapshot ID (auto: second-latest)"),
    to_id: int | None = Query(None, description="To snapshot ID (auto: latest)"),
):
    try:
        db = await get_db()
        try:
            snaps = await get_latest_snapshots(db, account_name, limit=2)
            if len(snaps) < 2:
                return {"error": "Need at least 2 snapshots to compare"}
            to_id = to_id or snaps[0]["id"]
            from_id = from_id or snaps[1]["id"]
            delta = await compare_snapshots(account_name, from_id, to_id)
            delta.from_time = snaps[1]["created_at"]
            delta.to_time = snaps[0]["created_at"]
            return delta.model_dump()
        finally:
            await db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-gainers")
async def get_top_gainers(
    account_name: str = Query(..., description="Account name from /analyze response"),
    limit: int = Query(20, description="Max results"),
):
    try:
        db = await get_db()
        try:
            snaps = await get_latest_snapshots(db, account_name, limit=2)
            if len(snaps) < 2:
                return []
            delta = await compare_snapshots(account_name, snaps[1]["id"], snaps[0]["id"])
            return [d.model_dump() for d in delta.top_gainers[:limit]]
        finally:
            await db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def post_cleanup(account_name: str | None = None):
    result = await cleanup_old_data(account_name)
    return result


@router.get("/listings/{item_id}")
async def get_listing_depth(item_id: int):
    try:
        listings = await fetch_listings([item_id])
        if item_id not in listings:
            return {"error": "No listing data", "item_id": item_id}
        depth = analyze_depth(listings[item_id])
        return depth
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/listings/batch")
async def get_listings_batch(item_ids: list[int]):
    try:
        listings = await fetch_listings(item_ids)
        return {str(iid): analyze_depth(data) for iid, data in listings.items()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-decliners")
async def get_top_decliners(
    account_name: str = Query(..., description="Account name from /analyze response"),
    limit: int = Query(20, description="Max results"),
):
    try:
        db = await get_db()
        try:
            snaps = await get_latest_snapshots(db, account_name, limit=2)
            if len(snaps) < 2:
                return []
            delta = await compare_snapshots(account_name, snaps[1]["id"], snaps[0]["id"])
            return [d.model_dump() for d in delta.top_decliners[:limit]]
        finally:
            await db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
