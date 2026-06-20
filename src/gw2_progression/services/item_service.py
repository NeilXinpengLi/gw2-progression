"""Fetch item details and flags from the GW2 API."""

import logging
from typing import Any

import httpx

from ..cache import get_cache

logger = logging.getLogger("gw2.item")

GW2_BASE = "https://api.guildwars2.com"
ITEM_CACHE_TTL = 86400
_cache = get_cache(ttl=ITEM_CACHE_TTL, maxsize=4096)

ACCOUNT_BOUND_FLAGS = {"AccountBound", "AccountBindOnUse", "SoulbindOnAcquire"}


async def _fetch_item_batch(item_ids: list[int]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    chunk_size = 200
    async with httpx.AsyncClient(timeout=15) as client:
        for start in range(0, len(item_ids), chunk_size):
            chunk = item_ids[start : start + chunk_size]
            ids_param = ",".join(str(i) for i in chunk)
            try:
                resp = await client.get(f"{GW2_BASE}/v2/items?ids={ids_param}")
                if resp.is_success:
                    data = resp.json()
                    for item in data if isinstance(data, list) else [data]:
                        item_id = item.get("id")
                        if item_id:
                            result[item_id] = item
            except Exception as e:
                logger.warning("Failed to fetch item batch: %s", e)
    return result


async def get_item_flags(item_ids: list[int]) -> dict[int, set[str]]:
    """Get flags for a list of item IDs. Returns {item_id: {flag1, flag2, ...}}."""
    if not item_ids:
        return {}

    result: dict[int, set[str]] = {}
    missing: list[int] = []

    for iid in item_ids:
        cached = _cache.get(f"item_flags:{iid}")
        if cached is not None:
            result[iid] = set(cached)
        else:
            missing.append(iid)

    if not missing:
        return result

    items_data = await _fetch_item_batch(missing)
    for iid, data in items_data.items():
        flags = set(data.get("flags", []))
        _cache.set(f"item_flags:{iid}", list(flags))
        result[iid] = flags

    # Items not returned by the API get empty flags set
    for iid in missing:
        if iid not in result:
            result[iid] = set()
            _cache.set(f"item_flags:{iid}", [])

    return result


async def is_account_bound(item_ids: list[int]) -> dict[int, bool]:
    """Check if each item ID is inherently account-bound (via flags, not binding field)."""
    flags_map = await get_item_flags(item_ids)
    return {iid: bool(flags & ACCOUNT_BOUND_FLAGS) for iid, flags in flags_map.items()}
