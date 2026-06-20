from fastapi import APIRouter, HTTPException, Query

from gw2_progression.services.tp_strategy_service import (
    generate_signals,
    get_protected_assets,
    protect_asset,
    unprotect_asset,
)

router = APIRouter(prefix="/tp", tags=["tp"])


@router.get("/signals")
async def get_signals(account_name: str = Query(...)):
    signals = await generate_signals(account_name)
    return [s.model_dump() for s in signals]


@router.get("/sell-candidates")
async def get_sell_candidates(account_name: str = Query(...)):
    signals = await generate_signals(account_name)
    return [s.model_dump() for s in signals if s.signal_type == "sell_candidate"]


@router.get("/buy-candidates")
async def get_buy_candidates(account_name: str = Query(...)):
    signals = await generate_signals(account_name)
    return [s.model_dump() for s in signals if s.signal_type == "buy_candidate"]


@router.get("/protected-assets")
async def get_protected(account_name: str = Query(...)):
    assets = await get_protected_assets(account_name)
    return [a.model_dump() for a in assets]


@router.post("/protected-assets")
async def add_protected(account_name: str = Query(...), item_id: int = Query(...), reason: str = "manual_lock"):
    asset = await protect_asset(account_name, item_id, reason)
    return asset.model_dump()


@router.delete("/protected-assets/{item_id}")
async def remove_protected(account_name: str = Query(...), item_id: int = 0):
    deleted = await unprotect_asset(account_name, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Protected asset not found")
    return {"status": "deleted"}
