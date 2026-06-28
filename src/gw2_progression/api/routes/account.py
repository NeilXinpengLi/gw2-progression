"""Account Dashboard API — structured data for the Account Overview page."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

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

# ── Per-key cache: avoid redundant fetch_all() across lite → full handshake ──
_fetch_cache: dict[str, tuple[datetime, Any]] = {}
_CACHE_TTL_S = 120

async def _cached_fetch(resolved_key: str, refresh: bool = False):
    now = datetime.now(timezone.utc)
    if not refresh and resolved_key in _fetch_cache:
        ts, contents = _fetch_cache[resolved_key]
        if (now - ts).total_seconds() < _CACHE_TTL_S:
            return contents
    contents = await fetch_all(resolved_key)
    _fetch_cache[resolved_key] = (now, contents)
    return contents


@router.get("/overview")
async def account_overview(api_key: str = Query(...), lite: bool = Query(False), refresh: bool = Query(False)):
    """
    Structured account overview via three-layer pipeline.

    Query params:
    - `lite=true`:  account + KPIs only (skips price enrichment, object graph, normalization).
                    Returns in ~5ms after fetch_all. Frontend renders overview immediately.
    - `lite=false`: full data with prices, assets breakdown, character gear, object graph.
    """
    resolved_key = await get_api_key(api_key)
    try:
        contents = await _cached_fetch(resolved_key, refresh=refresh)
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)

    if lite:
        wallet_gold = 0
        for entry in (contents.wallet or []):
            if entry.get("id") == 1:
                wallet_gold = entry.get("value", 0) // 10000
        return {
            "account": {
                "name": contents.account_name or "unknown",
                "world": contents.account_world,
            },
            "kpis": {
                "character_count": len(contents.characters or []),
                "achievement_count": len(contents.achievements or []),
                "mastery_count": len(contents.masteries or []),
                "daily_ap": contents.daily_ap or 0,
                "monthly_ap": contents.monthly_ap or 0,
                "wvw_rank": contents.wvw_rank or 0,
                "fractal_level": contents.fractal_level or 0,
                "skin_count": contents.unlocked_skins_count or 0,
                "wallet_gold": wallet_gold * 10000,
            },
            "snapshot_time": "",
        }

    # Layer 1 → Layer 2: Normalize raw data
    raw_dict = {
        "account": {"name": contents.account_name, "world": contents.account_world, "created": contents.account_created, "age": 0},
        "wallet": contents.wallet or [],
        "characters": contents.characters or [],
        "materials": contents.materials or [],
        "bank": contents.bank or [],
        "shared_inventory": contents.shared_inventory or [],
        "tradingpost_buys": contents.tradingpost_buys or [],
        "tradingpost_sells": contents.tradingpost_sells or [],
    }
    if contents.account_created:
        raw_dict["account"]["created"] = contents.account_created
    if contents.account_age_hours:
        raw_dict["account"]["age"] = int(contents.account_age_hours * 3600)

    # Build object graph (gw2efficiency-level full data model)
    from gw2_progression.object_graph.mapper import map_to_graph
    object_graph = map_to_graph(contents)

    from gw2_progression.services.snapshot_service import create_snapshot, derive_value, derive_breakdown, normalize_account

    normalized = normalize_account(raw_dict)

    # Enrich with market prices
    from gw2_progression.services.price_service import fetch_prices

    prices: dict = {}
    item_ids = list({a.item_id for a in normalized.assets if a.item_id != 1 and a.price_sell == 0})
    if item_ids:
        try:
            prices = await fetch_prices(item_ids)
            for a in normalized.assets:
                price = prices.get(a.item_id)
                if price:
                    a.price_buy = price.buy_unit_price
                    a.price_sell = price.sell_unit_price
                    a.value_buy = a.count * price.buy_unit_price
                    a.value_sell = a.count * price.sell_unit_price
                    a.value_after_fee = int(a.value_sell * 0.85)
                    a.confidence = 0.8
        except Exception as e:
            logger.warning("Price enrichment failed: %s", e)

    # Layer 3: Derive intelligence
    value = await derive_value(normalized)
    breakdown = derive_breakdown(normalized.assets)

    # Character summary — compute gear value and build status from raw equipment
    char_rows = []
    for ch in (contents.characters or []):
        char_equip_list = ch.get("equipment") or []
        char_gear_value = 0
        for eq in char_equip_list:
            if isinstance(eq, dict) and eq.get("id"):
                eq_price = prices.get(eq["id"])
                if eq_price:
                    char_gear_value += eq_price.sell_unit_price
        prof = ch.get("profession", "")
        char_rows.append({
            "name": ch.get("name", "?"),
            "profession": _profession_name(prof),
            "level": ch.get("level", 0),
            "playtime": _fmt_duration(ch.get("age", 0)),
            "gear_value": char_gear_value,
            "build_status": f"{len(char_equip_list)} equipped" if char_equip_list else "",
            "last_login": _fmt_last_login(ch.get("created", "")),
        })

    # ── Additional raw data from GW2 API (not shown in asset table) ──
    wallet_currencies = [{"id": 1, "name": "Gold", "value": normalized.currencies.gold * 10000}]
    for entry in (contents.wallet or []):
        if entry.get("id") in (2, 3, 4):  # karma, laurels, spirit shards
            wallet_currencies.append({"id": entry["id"], "value": entry.get("value", 0)})

    # ── Enrich object graph with market prices ──
    for item in object_graph.items:
        price = prices.get(item.item_id)
        if price:
            item.price_buy = price.buy_unit_price
            item.price_sell = price.sell_unit_price
            item.value_buy = item.count * price.buy_unit_price
            item.value_sell = item.count * price.sell_unit_price
            item.value_after_fee = int(item.value_sell * 0.85)

    return {
        "account": {
            "name": contents.account_name or "unknown",
            "world": contents.account_world,
            "created": contents.account_created,
            "age_hours": contents.account_age_hours,
        },
        "kpis": {
            "account_value": value.total_value,
            "liquid_sell": value.liquid_value,
            "liquid_sell_after_fee": value.liquid_value,
            "liquid_buy": value.liquid_value_buy,
            "hidden_wealth": value.hidden_value,
            "wallet_gold": normalized.currencies.gold * 10000,
            "character_count": normalized.snapshot.character_count,
            "daily_ap": contents.daily_ap or 0,
            "monthly_ap": contents.monthly_ap or 0,
            "wvw_rank": contents.wvw_rank or 0,
            "fractal_level": contents.fractal_level or 0,
            "skin_count": contents.unlocked_skins_count or 0,
            "achievement_count": len(contents.achievements or []),
            "mastery_count": len(contents.masteries or []),
        },
        "assets": [{
            "category": b.category,
            "total_value": b.total_value,
            "liquid_sell": b.liquid_value,
            "liquid_buy": b.liquid_value,
            "percentage": b.percentage,
            "risk_flag": b.risk,
        } for b in breakdown],
        "object_graph": {
            "item_count": len(object_graph.items),
            "character_count": len(object_graph.characters),
            "currencies": {c.currency_id: c.value for c in [
                object_graph.currencies.gold,
                object_graph.currencies.karma,
                object_graph.currencies.laurels,
                object_graph.currencies.spirit_shards,
                object_graph.currencies.fractal_relics,
                object_graph.currencies.magnetite,
                object_graph.currencies.gaeting,
                object_graph.currencies.gems,
                object_graph.currencies.volatile_magic,
                object_graph.currencies.unbound_magic,
            ] if c.value > 0},
            "unlock_counts": {
                "skins": object_graph.unlocks.skin_count,
                "dyes": object_graph.unlocks.dye_count,
                "minis": object_graph.unlocks.mini_count,
                "finishers": object_graph.unlocks.finisher_count,
            },
            "progression": {
                "daily_ap": object_graph.progression.daily_ap,
                "monthly_ap": object_graph.progression.monthly_ap,
                "fractal_level": object_graph.progression.fractal_level,
                "wvw_rank": object_graph.progression.wvw_rank,
                "build_templates": object_graph.progression.build_count,
                "masteries": object_graph.progression.mastery_count,
            },
            "market_orders": {
                "buy_count": len(object_graph.market.buy_orders),
                "sell_count": len(object_graph.market.sell_orders),
                "total_buy_value": object_graph.market.total_buy_value,
                "total_sell_value": object_graph.market.total_sell_value,
            },
        },
        "additional_data": {
            "wallet_currencies": wallet_currencies,
            "build_storage_count": len(contents.builds or []),
            "pvp_rank": (contents.pvp_stats or {}).get("pvp_rank", 0),
            "unlocked_dyes": len(contents.unlocked_dyes or []),
            "unlocked_minis": len(contents.unlocked_minis or []),
            "guild_count": len(contents.guilds or []),
        },
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
