"""AI Insight API — all derived intelligence from account data."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from gw2_progression.analyzer import fetch_all
from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.services.auth_service import get_api_key
from gw2_progression.services.holdings_service import (
    extract_bank_holdings,
    extract_character_equipment,
    extract_character_holdings,
    extract_material_holdings,
    extract_shared_inventory_holdings,
    extract_tradingpost_holdings,
    extract_wallet_holdings,
)
from gw2_progression.services.price_service import fetch_prices

logger = logging.getLogger("gw2.api.insight")

router = APIRouter(prefix="/api/insight", tags=["insight"])


@router.get("/data")
async def insight_data(api_key: str = Query(...)):
    """AI-derived intelligence: hidden wealth, build readiness, legendary progress."""
    resolved_key = await get_api_key(api_key)
    try:
        contents = await fetch_all(resolved_key)
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)

    account_name = contents.account_name or "unknown"
    wallet_gold = sum(w.get("value", 0) for w in (contents.wallet or []) if w.get("id") == 1)

    # Build holdings
    raw_holdings = []
    raw_holdings.extend(extract_wallet_holdings(contents.wallet))
    raw_holdings.extend(extract_material_holdings(contents.materials))
    raw_holdings.extend(extract_bank_holdings(contents.bank))
    raw_holdings.extend(extract_character_equipment(contents.characters))
    raw_holdings.extend(extract_character_holdings(contents.characters))
    raw_holdings.extend(extract_shared_inventory_holdings(contents.shared_inventory))
    raw_holdings.extend(extract_tradingpost_holdings(contents.tradingpost_buys, contents.tradingpost_sells))

    # Enrich with prices
    item_ids = list({h.item_id for h in raw_holdings if h.item_id != 1 and h.price_sell == 0})
    prices = {}
    if item_ids:
        try:
            prices = await fetch_prices(item_ids)
            for h in raw_holdings:
                p = prices.get(h.item_id)
                if p:
                    h.price_buy = p.buy_unit_price
                    h.price_sell = p.sell_unit_price
                    h.value_buy = h.count * p.buy_unit_price
                    h.value_sell = h.count * p.sell_unit_price
        except Exception as e:
            logger.warning("Price fetch failed: %s", e)

    # ── Compute AI-derived metrics ──

    # 1. Hidden Wealth: unpriced items that likely have value
    unpriced = [h for h in raw_holdings if h.valuation_status == "pending" and h.tradable and h.count > 0]
    hidden_wealth_count = len(unpriced)
    hidden_items_detail = []
    for h in sorted(unpriced, key=lambda x: x.count, reverse=True)[:10]:
        hidden_items_detail.append({
            "item_id": h.item_id,
            "count": h.count,
            "location": h.location_type,
        })

    # 2. Build readiness: character equipment analysis
    equipment_holdings = [h for h in raw_holdings if h.location_type == "character_equipment"]
    char_equip_map: dict[str, int] = {}
    for h in equipment_holdings:
        if h.location_ref:
            char_name = h.location_ref.split("/")[0]
            char_equip_map[char_name] = char_equip_map.get(char_name, 0) + 1

    build_ready_chars = len([
        ch for ch in (contents.characters or [])
        if ch.get("level", 0) == 80
    ])
    equipped_chars = len(char_equip_map)
    missing_gear_chars = build_ready_chars - equipped_chars

    # 3. Best value item
    priced_holdings = [h for h in raw_holdings if h.price_sell > 0 and h.location_type != "wallet"]
    best_items = sorted(priced_holdings, key=lambda h: h.value_sell, reverse=True)[:5]
    best_items_detail = [
        {"item_id": h.item_id, "count": h.count, "value_sell": h.value_sell, "location": h.location_type}
        for h in best_items
    ]

    # 4. Material surplus analysis
    materials = [h for h in raw_holdings if h.location_type == "material_storage" and h.price_sell > 0]
    top_materials = sorted(materials, key=lambda h: h.value_sell, reverse=True)[:5]
    material_detail = [
        {"item_id": h.item_id, "count": h.count, "value_sell": h.value_sell}
        for h in top_materials
    ]

    # 5. Legendary Progress — from tracked goals
    legendary_goals = []
    try:
        from gw2_progression.services.goal_service import get_goals
        tracked = await get_goals(account_name)
        for g in tracked:
            legendary_goals.append({
                "goal_id": g.goal_id,
                "target_item_id": g.target_item_id,
                "completion_percent": g.completion_percent,
                "status": g.status,
                "priority": g.priority,
            })
    except Exception as e:
        logger.warning("Goal fetch failed: %s", e)

    # 6. Market Insight — sell/buy candidates
    sell_candidates = []
    buy_opportunities = []
    try:
        from gw2_progression.services.listing_service import fetch_listings, analyze_depth
        sell_ids = [h.item_id for h in priced_holdings if h.tradable and h.location_type != "wallet"][:20]
        if sell_ids:
            listings = await fetch_listings(sell_ids)
            for iid, listing in listings.items():
                depth = analyze_depth(listing)
                if depth.get("liquidity_score") == "high":
                    sell_candidates.append({"item_id": iid, "spread_ratio": depth.get("spread_ratio")})
    except Exception as e:
        logger.warning("Market insight fetch failed: %s", e)

    return {
        "account_name": account_name,
        "hidden_wealth": {
            "item_count": hidden_wealth_count,
            "items": hidden_items_detail,
            "explanation": f"{hidden_wealth_count} items not yet priced — may hold significant value",
        },
        "build_readiness": {
            "total_chars": build_ready_chars,
            "equipped_chars": equipped_chars,
            "missing_gear_chars": max(0, missing_gear_chars),
            "summary": f"{equipped_chars}/{build_ready_chars} characters have equipment data",
        },
        "legendary_progress": {
            "active_goals": [g for g in legendary_goals if g["status"] == "active"],
            "total": len(legendary_goals),
            "summary": f"{len([g for g in legendary_goals if g['status'] == 'active'])} active goals" if legendary_goals else "No tracked goals",
        },
        "market_insight": {
            "sell_candidates": sell_candidates,
            "buy_opportunities": buy_opportunities,
            "summary": f"{len(sell_candidates)} high-liquidity sell candidates" if sell_candidates else "No market data",
        },
        "top_items": best_items_detail,
        "top_materials": material_detail,
        "wallet_gold": wallet_gold,
    }
