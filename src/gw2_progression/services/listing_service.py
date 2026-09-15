"""TP order book analysis via /v2/commerce/listings."""

import logging
import time
from collections import OrderedDict
from datetime import UTC, datetime

import httpx

logger = logging.getLogger("gw2.listing")

GW2_BASE = "https://api.guildwars2.com"
LISTING_CACHE_TTL = 300
LISTING_CACHE_MAX = 1000

_listing_cache: OrderedDict[int, dict] = OrderedDict()
_listing_cache_timestamps: dict[int, float] = {}


def _get_cached_listing(item_id: int) -> dict | None:
    if item_id in _listing_cache:
        ts = _listing_cache_timestamps.get(item_id, 0)
        if time.monotonic() - ts < LISTING_CACHE_TTL:
            return _listing_cache[item_id]
        del _listing_cache[item_id]
        del _listing_cache_timestamps[item_id]
    return None


def _set_cached_listing(item_id: int, data: dict):
    _listing_cache[item_id] = data
    _listing_cache_timestamps[item_id] = time.monotonic()
    if len(_listing_cache) > LISTING_CACHE_MAX:
        _listing_cache.popitem(last=False)
        if _listing_cache_timestamps:
            _listing_cache_timestamps.pop(next(iter(_listing_cache_timestamps)), None)


async def fetch_listings(item_ids: list[int]) -> dict[int, dict]:
    """Fetch full order book listings for items. Returns {item_id: listing_data}."""
    if not item_ids:
        return {}

    result: dict[int, dict] = {}
    missing: list[int] = []

    for iid in item_ids:
        cached = _get_cached_listing(iid)
        if cached is not None:
            result[iid] = cached
        else:
            missing.append(iid)

    if not missing:
        return result

    async with httpx.AsyncClient(timeout=30) as client:
        chunk_size = 100
        for start in range(0, len(missing), chunk_size):
            chunk = missing[start : start + chunk_size]
            ids_param = ",".join(str(i) for i in chunk)
            try:
                resp = await client.get(f"{GW2_BASE}/v2/commerce/listings?ids={ids_param}")
                if resp.is_success:
                    fetched_at = datetime.now(UTC).isoformat()
                    data = resp.json()
                    for entry in data if isinstance(data, list) else [data]:
                        item_id = entry.get("id")
                        if item_id:
                            buys = entry.get("buys", [])
                            sells = entry.get("sells", [])
                            listing_data = {
                                "item_id": item_id,
                                "buys": buys,  # sorted descending price
                                "sells": sells,  # sorted ascending price
                                "best_buy": buys[0]["unit_price"] if buys else 0,
                                "best_buy_qty": buys[0]["quantity"] if buys else 0,
                                "best_sell": sells[0]["unit_price"] if sells else 0,
                                "best_sell_qty": sells[0]["quantity"] if sells else 0,
                                "fetched_at": fetched_at,
                            }
                            _set_cached_listing(item_id, listing_data)
                            result[item_id] = listing_data
            except Exception as e:
                logger.warning("Failed to fetch listings chunk: %s", e)

    return result


def analyze_depth(listing: dict) -> dict:
    """Analyze order book depth for a single listing."""
    buys = listing.get("buys", [])
    sells = listing.get("sells", [])
    best_buy = listing.get("best_buy", 0)
    best_sell = listing.get("best_sell", 0)
    buy_depth_5 = sum(b.get("quantity", 0) for b in buys[:5])
    sell_depth_5 = sum(s.get("quantity", 0) for s in sells[:5])
    buy_depth_all = sum(b.get("quantity", 0) for b in buys)
    sell_depth_all = sum(s.get("quantity", 0) for s in sells)

    # Arbitrage: buy at best sell, sell at best buy, subtract 15% TP fees
    if best_sell > 0 and best_buy > 0:
        gross_profit = best_buy - best_sell
        tp_fee_buy = round(best_sell * 0.05)  # listing fee
        tp_fee_sell = round(best_buy * 0.10)  # exchange fee
        net_profit = best_buy - best_sell - tp_fee_buy - tp_fee_sell
        profit_margin = round(net_profit / best_sell * 100, 2) if best_sell > 0 else 0.0
    else:
        gross_profit = 0
        net_profit = 0
        profit_margin = 0.0

    spread = best_sell - best_buy
    spread_ratio = round(spread / best_sell, 4) if best_sell > 0 else 0.0
    total_depth = buy_depth_all + sell_depth_all

    if total_depth >= 5000:
        liquidity_score = "high"
        confidence = 0.92
        liquidity_reason = f"{total_depth} total visible orders across buy/sell depth."
    elif total_depth >= 500:
        liquidity_score = "medium"
        confidence = 0.82
        liquidity_reason = f"{total_depth} total visible orders across buy/sell depth."
    elif total_depth > 0:
        liquidity_score = "low"
        confidence = 0.58
        liquidity_reason = f"Only {total_depth} total visible orders; large trades may move price."
    else:
        liquidity_score = "illiquid"
        confidence = 0.20
        liquidity_reason = "No visible buy or sell order depth."

    if not best_buy or not best_sell:
        risk_reason = "Missing one side of the order book; TP signal is speculative."
        confidence = min(confidence, 0.45)
    elif spread_ratio > 0.2:
        risk_reason = "Wide spread between buy and sell orders; execution price may vary."
        confidence = min(confidence, 0.65)
    elif liquidity_score in ("low", "illiquid"):
        risk_reason = "Low order depth; liquidation may require price concessions."
    else:
        risk_reason = "Order book depth and spread support this TP estimate."

    return {
        "best_buy": best_buy,
        "best_sell": best_sell,
        "spread": spread,
        "spread_ratio": spread_ratio,
        "buy_depth_5": buy_depth_5,
        "sell_depth_5": sell_depth_5,
        "buy_depth_all": buy_depth_all,
        "sell_depth_all": sell_depth_all,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
        "profit_margin": profit_margin,
        "arbitrage_viable": net_profit > 0,
        "liquidity_score": liquidity_score,
        "liquidity_reason": liquidity_reason,
        "confidence": confidence,
        "data_sources": ["gw2_commerce_listings"],
        "price_timestamp": listing.get("fetched_at", ""),
        "risk_reason": risk_reason,
    }
