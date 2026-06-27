"""Account Dashboard API — structured data for the Account Overview page."""

import logging

from fastapi import APIRouter, HTTPException, Query

from gw2_progression.analyzer import fetch_all
from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.services.auth_service import get_api_key

logger = logging.getLogger("gw2.api.account")
from gw2_progression.services.holdings_service import (
    extract_bank_holdings,
    extract_character_holdings,
    extract_material_holdings,
    extract_shared_inventory_holdings,
    extract_tradingpost_holdings,
    extract_wallet_holdings,
)

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/overview")
async def account_overview(api_key: str = Query(...)):
    """Structured account overview data for the dashboard."""
    resolved_key = await get_api_key(api_key)
    try:
        contents = await fetch_all(resolved_key)
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)

    account_name = contents.account_name or "unknown"
    wallet_gold = sum(w.get("value", 0) for w in (contents.wallet or []) if w.get("id") == 1)

    # Build holdings from raw account data (no DB snapshot needed)
    raw_holdings = []
    raw_holdings.extend(extract_wallet_holdings(contents.wallet))
    raw_holdings.extend(extract_material_holdings(contents.materials))
    raw_holdings.extend(extract_bank_holdings(contents.bank))
    raw_holdings.extend(extract_character_holdings(contents.characters))
    raw_holdings.extend(extract_shared_inventory_holdings(contents.shared_inventory))
    raw_holdings.extend(extract_tradingpost_holdings(contents.tradingpost_buys, contents.tradingpost_sells))

    # Enrich holdings with market prices
    from gw2_progression.services.price_service import fetch_prices, compute_price_quality

    item_ids = list({h.item_id for h in raw_holdings if h.item_id != 1})
    if item_ids:
        try:
            prices = await fetch_prices(item_ids)
            for h in raw_holdings:
                price = prices.get(h.item_id)
                if price:
                    quality = compute_price_quality(price.buy_unit_price, price.sell_unit_price, price.buy_quantity, price.sell_quantity)
                    h.price_buy = price.buy_unit_price
                    h.price_sell = price.sell_unit_price
                    h.value_buy = h.count * price.buy_unit_price
                    h.value_sell = h.count * price.sell_unit_price
                    h.valuation_status = "priced"
                    h.liquidity_score = quality.get("liquidity_score", "unknown")
                    h.data_sources = ["gw2_commerce_prices"]
                    h.price_timestamp = price.fetched_at
                    h.confidence = quality.get("confidence", 0.5)
        except Exception as e:
            logger.warning("Price enrichment failed (continuing): %s", e)

    total_value_sell = sum(h.value_sell for h in raw_holdings)
    total_value_buy = sum(h.value_buy for h in raw_holdings)
    liquid_sell_after_fee = int(total_value_sell * 0.85)
    unpriced_holdings = [h for h in raw_holdings if h.valuation_status == "unpriced"]
    hidden_wealth = sum(h.count * (h.price_sell or 0) for h in unpriced_holdings)

    # Per-category breakdown from raw data
    categories = _categorize_holdings(raw_holdings)
    category_rows = []
    for cat_name, cat_holdings in categories:
        cat_sell = sum(h.value_sell for h in cat_holdings)
        cat_buy = sum(h.value_buy for h in cat_holdings)
        risk = _category_risk(cat_holdings)
        category_rows.append({
            "category": cat_name,
            "total_value": cat_sell,
            "liquid_sell": cat_sell,
            "liquid_buy": cat_buy,
            "percentage": round(cat_sell / max(total_value_sell, 1) * 100, 1),
            "risk_flag": risk,
        })

    # Character summary
    char_rows = []
    for ch in (contents.characters or []):
        char_rows.append({
            "name": ch.get("name", "?"),
            "profession": _profession_name(ch.get("profession", "")),
            "level": ch.get("level", 0),
            "playtime": _fmt_duration(ch.get("age", 0)),
            "gear_value": 0,
            "build_status": "",
            "last_login": _fmt_last_login(ch.get("created", "")),
        })

    return {
        "account": {
            "name": account_name,
            "world": contents.account_world,
            "created": contents.account_created,
            "age_hours": contents.account_age_hours,
        },
        "kpis": {
            "account_value": total_value_sell,
            "liquid_sell": total_value_sell,
            "liquid_sell_after_fee": liquid_sell_after_fee,
            "liquid_buy": total_value_buy,
            "hidden_wealth": hidden_wealth,
            "wallet_gold": wallet_gold,
            "character_count": len(contents.characters or []),
        },
        "assets": category_rows,
        "characters": char_rows,
        "snapshot_time": "",
    }


def _categorize_holdings(holdings) -> list[tuple[str, list]]:
    mapping: dict[str, list] = {}
    for h in holdings:
        loc = h.location_type or "other"
        if loc not in mapping:
            mapping[loc] = []
        mapping[loc].append(h)
    order = ["wallet", "material_storage", "bank", "character", "shared_inventory", "tradingpost", "other"]
    result = []
    for key in order:
        if key in mapping:
            label = {"wallet": "Wallet", "material_storage": "Materials", "bank": "Bank",
                     "character": "Characters", "shared_inventory": "Shared Inventory",
                     "tradingpost": "Trading Post", "other": "Other"}.get(key, key)
            result.append((label, mapping[key]))
    return result


def _category_risk(holdings) -> str:
    low_liquidity = sum(1 for h in holdings if h.liquidity_score in ("low", "illiquid"))
    total = len(holdings)
    if total == 0:
        return "none"
    ratio = low_liquidity / total
    if ratio > 0.5:
        return "high"
    if ratio > 0.2:
        return "medium"
    return "low"


def _profession_name(key: str) -> str:
    mapping = {
        "Guardian": "Guardian", "Dragonhunter": "Dragonhunter", "Firebrand": "Firebrand",
        "Warrior": "Warrior", "Berserker": "Berserker", "Spellbreaker": "Spellbreaker", "Bladesworn": "Bladesworn",
        "Revenant": "Revenant", "Herald": "Herald", "Renegade": "Renegade", "Vindicator": "Vindicator",
        "Ranger": "Ranger", "Druid": "Druid", "Soulbeast": "Soulbeast", "Untamed": "Untamed",
        "Thief": "Thief", "Daredevil": "Daredevil", "Deadeye": "Deadeye", "Specter": "Specter",
        "Elementalist": "Elementalist", "Tempest": "Tempest", "Weaver": "Weaver", "Catalyst": "Catalyst",
        "Mesmer": "Mesmer", "Chronomancer": "Chronomancer", "Mirage": "Mirage", "Virtuoso": "Virtuoso",
        "Necromancer": "Necromancer", "Reaper": "Reaper", "Scourge": "Scourge", "Harbinger": "Harbinger",
        "Engineer": "Engineer", "Scrapper": "Scrapper", "Holosmith": "Holosmith", "Mechanist": "Mechanist",
    }
    return mapping.get(key, key)


def _fmt_duration(seconds: int) -> str:
    hours = seconds // 3600
    return f"{hours}h" if hours > 0 else "<1h"


def _fmt_last_login(created: str) -> str:
    if not created:
        return "—"
    from datetime import datetime, timezone
    try:
        ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days = (now - ts).days
        if days == 0:
            return "today"
        if days == 1:
            return "yesterday"
        return f"{days} days ago"
    except (ValueError, TypeError):
        return "—"
