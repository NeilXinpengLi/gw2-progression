import logging
import time
from collections import OrderedDict
from typing import Any

import httpx

from ..database import get_db, save_price_snapshot
from ..models import PriceData

logger = logging.getLogger("gw2.price")

GW2_BASE = "https://api.guildwars2.com"
PRICE_CACHE_TTL = 900
PRICE_CACHE_MAX = 2000

_price_cache: OrderedDict[int, PriceData] = OrderedDict()
_price_cache_timestamps: dict[int, float] = {}
_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30)
    return _client


async def close_client():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _get_cached_price(item_id: int) -> PriceData | None:
    if item_id in _price_cache:
        ts = _price_cache_timestamps.get(item_id, 0)
        if time.monotonic() - ts < PRICE_CACHE_TTL:
            return _price_cache[item_id]
        del _price_cache[item_id]
        del _price_cache_timestamps[item_id]
    return None


def _set_cached_price(data: PriceData):
    _price_cache[data.item_id] = data
    _price_cache_timestamps[data.item_id] = time.monotonic()
    if len(_price_cache) > PRICE_CACHE_MAX:
        _price_cache.popitem(last=False)
        if _price_cache_timestamps:
            _price_cache_timestamps.pop(next(iter(_price_cache_timestamps)), None)


async def warmup_price_cache(max_items: int = 500):
    """Load recently fetched prices from the database into the in-memory cache."""
    try:
        from ..database import get_db

        db = await get_db()
        try:
            cursor = await db.execute(
                """SELECT item_id, buy_unit_price, buy_quantity, sell_unit_price, sell_quantity
                   FROM price_snapshots
                   WHERE id IN (SELECT MAX(id) FROM price_snapshots GROUP BY item_id)
                   ORDER BY id DESC LIMIT ?""",
                (max_items,),
            )
            rows = await cursor.fetchall()
            count = 0
            for row in rows:
                pd = PriceData(
                    item_id=row["item_id"],
                    buy_unit_price=row["buy_unit_price"],
                    buy_quantity=row["buy_quantity"],
                    sell_unit_price=row["sell_unit_price"],
                    sell_quantity=row["sell_quantity"],
                    fetched_at="",
                )
                _set_cached_price(pd)
                count += 1
            if count:
                logger.info("Warmed up price cache with %d items from database", count)
        finally:
            await db.close()
    except Exception as e:
        logger.warning("Price cache warmup failed (continuing): %s", e)


async def fetch_prices(item_ids: list[int]) -> dict[int, PriceData]:
    if not item_ids:
        return {}

    result: dict[int, PriceData] = {}

    missing = []
    for iid in item_ids:
        cached = _get_cached_price(iid)
        if cached is not None:
            result[iid] = cached
        else:
            missing.append(iid)

    if not missing:
        return result

    client = await _get_client()

    try:
        db = await get_db()
        try:
            chunk_size = 200
            for start in range(0, len(missing), chunk_size):
                chunk = missing[start : start + chunk_size]
                ids_param = ",".join(str(i) for i in chunk)
                try:
                    resp = await client.get(f"{GW2_BASE}/v2/commerce/prices?ids={ids_param}")
                    if resp.is_success:
                        data: list[dict[str, Any]] = resp.json()
                        for entry in data:
                            item_id = entry.get("id")
                            buys = entry.get("buys", {})
                            sells = entry.get("sells", {})
                            pd = PriceData(
                                item_id=item_id,
                                buy_unit_price=buys.get("unit_price", 0),
                                buy_quantity=buys.get("quantity", 0),
                                sell_unit_price=sells.get("unit_price", 0),
                                sell_quantity=sells.get("quantity", 0),
                                fetched_at="",
                            )
                            _set_cached_price(pd)
                            result[item_id] = pd

                            await save_price_snapshot(
                                db,
                                item_id,
                                pd.buy_unit_price,
                                pd.buy_quantity,
                                pd.sell_unit_price,
                                pd.sell_quantity,
                            )
                    elif resp.status_code != 404:
                        logger.warning("Failed to fetch prices chunk: HTTP %d", resp.status_code)
                except Exception as e:
                    logger.warning("Error fetching prices chunk: %s", e)

            await db.commit()
        finally:
            await db.close()
    except Exception as e:
        logger.warning("Database error in price fetch (continuing): %s", e)

    return result
