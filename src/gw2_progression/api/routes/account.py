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
    """Structured account overview via three-layer pipeline (Raw → Normalized → Derived)."""
    resolved_key = await get_api_key(api_key)
    try:
        contents = await fetch_all(resolved_key)
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)

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

    from gw2_progression.services.snapshot_service import create_snapshot, derive_value, derive_breakdown, normalize_account

    normalized = normalize_account(raw_dict)

    # Enrich with market prices
    from gw2_progression.services.price_service import fetch_prices

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
        },
        "assets": [{
            "category": b.category,
            "total_value": b.total_value,
            "liquid_sell": b.liquid_value,
            "liquid_buy": b.liquid_value,
            "percentage": b.percentage,
            "risk_flag": b.risk,
        } for b in breakdown],
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
