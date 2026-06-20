"""Backend proxy for public GW2 API static data + TTLCache integration."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gw2_progression.cache import get_cache

router = APIRouter(prefix="/resolve", tags=["resolve"])

GW2_BASE = "https://api.guildwars2.com"
_cache = get_cache(ttl=3600, maxsize=1024)


_resolve_endpoints = {
    "items": "/v2/items?ids={ids}",
    "currencies": "/v2/currencies?ids={ids}",
    "materials": "/v2/materials",
    "masteries": "/v2/masteries?ids={ids}",
    "maps": "/v2/maps?ids={ids}",
    "skins": "/v2/skins?ids={ids}",
    "colors": "/v2/colors?ids={ids}",
    "guild": "/v2/guild/{id}",
}


class ResolveRequest(BaseModel):
    type: str
    ids: list[str] | None = None
    id: str | None = None


async def _gw2_fetch(path: str) -> dict | list:
    import httpx

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{GW2_BASE}{path}")
    if not resp.is_success:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("")
async def resolve(req: ResolveRequest) -> dict | list:
    ep = _resolve_endpoints.get(req.type)
    if not ep:
        raise HTTPException(status_code=400, detail=f"Unknown resolve type: {req.type}")

    if req.type == "materials":
        cached = _cache.get("materials")
        if cached is not None:
            return cached
        data = await _gw2_fetch(ep)
        _cache.set("materials", data)
        return data

    if req.type == "guild":
        if not req.id:
            return {}
        key = f"guild:{req.id}"
        cached = _cache.get(key)
        if cached is not None:
            return cached
        data = await _gw2_fetch(ep.format(id=req.id))
        _cache.set(key, data)
        return data

    ids = req.ids or []
    if not ids:
        return []

    unique = sorted(set(ids))
    missing = [i for i in unique if _cache.get(f"{req.type}:{i}") is None]
    if missing:
        chunk_size = 200
        for start in range(0, len(missing), chunk_size):
            chunk = missing[start : start + chunk_size]
            try:
                data = await _gw2_fetch(ep.format(ids=",".join(chunk)))
                for item in data if isinstance(data, list) else [data]:
                    item_id = item.get("id")
                    if item_id is not None:
                        _cache.set(f"{req.type}:{item_id}", item)
            except HTTPException:
                continue

    result = []
    for i in unique:
        item = _cache.get(f"{req.type}:{i}")
        if item is not None:
            result.append(item)
    return result
