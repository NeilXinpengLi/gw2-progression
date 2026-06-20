"""Item search across the latest snapshot holdings."""

import logging

import httpx

from ..database import get_db, search_latest_holdings
from ..models import ItemHolding

logger = logging.getLogger("gw2.search")

GW2_BASE = "https://api.guildwars2.com"


async def _search_gw2_items(query: str) -> list[int]:
    """Search GW2 API for item IDs matching a name query."""
    from urllib.parse import quote

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{GW2_BASE}/v2/search?text={quote(query)}&type=item")
    if not resp.is_success:
        return []
    data = resp.json()
    return data if isinstance(data, list) else [data]


async def search_items_by_name(
    account_name: str,
    query: str,
    location: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[ItemHolding]:
    """Search latest snapshot holdings by item name or ID."""
    # Try direct ID match first
    try:
        item_id = int(query)
        return await search_latest_holdings(
            await get_db(),
            account_name,
            query=str(item_id),
            location_type=location,
            valuation_status=status,
            limit=limit,
        )
    except (ValueError, TypeError):
        pass

    # Name search via GW2 API
    ids = await _search_gw2_items(query)
    if not ids:
        return []

    db = await get_db()
    try:
        result = []
        for iid in ids[:20]:
            items = await search_latest_holdings(
                db,
                account_name,
                query=str(iid),
                location_type=location,
                valuation_status=status,
                limit=50,
            )
            result.extend(items)
        return result
    finally:
        await db.close()


async def get_item_detail(account_name: str, item_id: int) -> dict:
    """Get full detail for a specific item across all locations."""
    db = await get_db()
    try:
        raw = await search_latest_holdings(db, account_name, query=str(item_id), limit=200)
    finally:
        await db.close()

    holdings = [h for h in raw if h.item_id == item_id]
    total_count = sum(h.count for h in holdings)
    total_value_buy = sum(h.value_buy for h in holdings)
    total_value_sell = sum(h.value_sell for h in holdings)

    by_location: dict[str, list[dict]] = {}
    for h in holdings:
        loc = h.location_type
        if loc not in by_location:
            by_location[loc] = []
        by_location[loc].append(
            {
                "count": h.count,
                "location_ref": h.location_ref,
                "binding_status": h.binding_status,
                "tradable": h.tradable,
                "price_buy": h.price_buy,
                "price_sell": h.price_sell,
                "value_buy": h.value_buy,
                "value_sell": h.value_sell,
                "valuation_status": h.valuation_status,
            }
        )

    return {
        "item_id": item_id,
        "total_count": total_count,
        "total_value_buy": total_value_buy,
        "total_value_sell": total_value_sell,
        "locations": by_location,
        "valuation_status": holdings[0].valuation_status if holdings else "unknown",
        "tradable": any(h.tradable for h in holdings),
    }


async def get_filtered_items(
    account_name: str,
    filter_type: str,
    limit: int = 100,
) -> list[ItemHolding]:
    """Get items filtered by special criteria: high_value, unpriced, account_bound."""
    db = await get_db()
    try:
        status_map = {
            "unpriced": "unpriced",
            "account_bound": "account_bound",
        }
        status_filter = status_map.get(filter_type)
        items = await search_latest_holdings(
            db,
            account_name,
            valuation_status=status_filter,
            limit=limit,
        )

        if filter_type == "high_value":
            all_items = await search_latest_holdings(db, account_name, limit=500)
            items = sorted(all_items, key=lambda h: h.value_buy, reverse=True)[:limit]

        return items
    finally:
        await db.close()
