"""Account Dashboard API — structured data for the Account Overview page."""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from gw2_progression.analyzer import fetch_all
from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.services.auth_service import get_api_key
from gw2_progression.services.snapshot_service import derive_breakdown, derive_value, normalize_account

logger = logging.getLogger("gw2.api.account")

router = APIRouter(prefix="/api/account", tags=["account"])

# ── Per-key cache: avoid redundant fetch_all() across lite → full handshake ──
_fetch_cache: dict[str, tuple[datetime, Any]] = {}
_CACHE_TTL_S = 120

async def _cached_fetch(resolved_key: str, refresh: int = 0):
    now = datetime.now(timezone.utc)
    if not refresh and resolved_key in _fetch_cache:
        ts, contents = _fetch_cache[resolved_key]
        if (now - ts).total_seconds() < _CACHE_TTL_S:
            return contents
    contents = await fetch_all(resolved_key)
    _fetch_cache[resolved_key] = (now, contents)
    return contents


@router.get("/overview")
async def account_overview(api_key: str = Query(...), lite: bool = Query(False), refresh: int = Query(0)):
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
        if e.status_code == 429:
            raise HTTPException(status_code=429, detail="GW2 API rate limit reached. Please wait 60 seconds and try again.")
        raise HTTPException(status_code=e.status_code if e.status_code in (401, 403, 404) else 502, detail=e.message)

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
    graph_nodes, node_details = _build_account_graph_payload(normalized.assets, breakdown, object_graph)

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
            "count": b.item_count,
        } for b in breakdown],
        "graph_nodes": graph_nodes,
        "node_details": node_details,
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


def _asset_category(location: str) -> str:
    mapping = {
        "wallet": "Wallet",
        "material_storage": "Material Storage",
        "bank": "Bank",
        "character_equipment": "Equipment",
        "character": "Character Inventory",
        "shared_inventory": "Shared Inventory",
        "tradingpost": "Trading Post",
    }
    return mapping.get(location, location.replace("_", " ").title())


def _node_id(label: str) -> str:
    return label.lower().replace("&", "and").replace("/", "-").replace(" ", "-")


def _build_account_graph_payload(assets, breakdown, object_graph) -> tuple[list[dict], dict]:
    """Build a compact graph navigator payload for the Account Raw UI."""
    by_category: dict[str, list] = {}
    for asset in assets:
        by_category.setdefault(_asset_category(asset.location), []).append(asset)

    nodes: list[dict] = [{
        "id": "overview",
        "group": "snapshot",
        "label": "Account Snapshot",
        "kind": "snapshot",
        "count": len(assets),
        "value": sum(a.value_after_fee for a in assets),
        "risk": "low",
    }]
    details: dict[str, dict] = {
        "overview": {
            "title": "Account Snapshot",
            "subtitle": "Raw account data normalized into asset, character, unlock, market, and progression nodes.",
            "metrics": [
                {"label": "Asset stacks", "value": len(assets)},
                {"label": "Characters", "value": len(object_graph.characters)},
                {"label": "Currencies", "value": len([v for v in object_graph.currencies.__dict__.values() if getattr(v, "value", 0) > 0])},
                {"label": "Market orders", "value": len(object_graph.market.buy_orders) + len(object_graph.market.sell_orders)},
            ],
            "breakdown": [],
            "items": [],
            "insight": "Start from Assets to inspect value quality, or Characters to inspect ownership by character.",
        }
    }

    for b in breakdown:
        node_id = f"asset:{_node_id(b.category)}"
        cat_assets = by_category.get(b.category, [])
        priced = sum(1 for a in cat_assets if a.price_sell > 0 or a.location == "wallet")
        unpriced = max(len(cat_assets) - priced, 0)
        bound = sum(1 for a in cat_assets if a.binding or not a.tradable)
        low_liquidity = sum(1 for a in cat_assets if a.liquidity in ("low", "illiquid", "unknown"))
        top_items = sorted(cat_assets, key=lambda a: a.value_after_fee or a.value_sell or a.value_buy, reverse=True)[:8]

        nodes.append({
            "id": node_id,
            "group": "assets",
            "label": b.category,
            "kind": "asset_category",
            "count": b.item_count,
            "value": b.total_value,
            "percentage": b.percentage,
            "risk": b.risk,
        })
        details[node_id] = {
            "title": b.category,
            "subtitle": "Value grouped by where the account holds this asset class.",
            "metrics": [
                {"label": "Net value", "value": b.total_value, "format": "coin"},
                {"label": "Stacks", "value": b.item_count},
                {"label": "Priced", "value": priced},
                {"label": "Unpriced", "value": unpriced},
            ],
            "breakdown": [
                {"label": "Account-bound / locked", "value": bound},
                {"label": "Low or unknown liquidity", "value": low_liquidity},
                {"label": "Share of account value", "value": f"{b.percentage}%"},
                {"label": "Risk", "value": b.risk.upper()},
            ],
            "items": [{
                "item_id": a.item_id,
                "count": a.count,
                "location": a.location,
                "location_ref": a.location_ref,
                "binding": a.binding or ("Tradable" if a.tradable else "Locked"),
                "liquidity": a.liquidity,
                "value": a.value_after_fee or a.value_sell or a.value_buy,
            } for a in top_items],
            "insight": _asset_insight(b.category, b.risk, unpriced, low_liquidity),
        }

    nodes.extend([
        {"id": "progression", "group": "progression", "label": "Progression", "kind": "progression", "count": object_graph.progression.mastery_count, "value": 0, "risk": "low"},
        {"id": "unlocks", "group": "unlocks", "label": "Unlocks", "kind": "unlocks", "count": object_graph.unlocks.skin_count, "value": 0, "risk": "low"},
        {
            "id": "market",
            "group": "market",
            "label": "Trading Post Orders",
            "kind": "market",
            "count": len(object_graph.market.buy_orders) + len(object_graph.market.sell_orders),
            "value": object_graph.market.total_buy_value + object_graph.market.total_sell_value,
            "risk": "medium" if object_graph.market.buy_orders or object_graph.market.sell_orders else "low",
        },
    ])

    details["progression"] = {
        "title": "Progression",
        "subtitle": "Account-level progression signals from GW2 account endpoints.",
        "metrics": [
            {"label": "Fractal", "value": object_graph.progression.fractal_level},
            {"label": "WvW rank", "value": object_graph.progression.wvw_rank},
            {"label": "Masteries", "value": object_graph.progression.mastery_count},
            {"label": "Build templates", "value": object_graph.progression.build_count},
        ],
        "breakdown": [],
        "items": [],
        "insight": "Use this area to connect raw progress to build readiness and weekly plan priorities.",
    }
    details["unlocks"] = {
        "title": "Unlocks",
        "subtitle": "Collections unlocked on the account.",
        "metrics": [
            {"label": "Skins", "value": object_graph.unlocks.skin_count},
            {"label": "Dyes", "value": object_graph.unlocks.dye_count},
            {"label": "Minis", "value": object_graph.unlocks.mini_count},
            {"label": "Finishers", "value": object_graph.unlocks.finisher_count},
        ],
        "breakdown": [],
        "items": [],
        "insight": "Unlock counts are useful context, but should stay secondary to wealth, goals, and build readiness.",
    }
    details["market"] = {
        "title": "Trading Post Orders",
        "subtitle": "Open buy and sell orders that affect liquid value and future cash flow.",
        "metrics": [
            {"label": "Buy orders", "value": len(object_graph.market.buy_orders)},
            {"label": "Sell orders", "value": len(object_graph.market.sell_orders)},
            {"label": "Buy value", "value": object_graph.market.total_buy_value, "format": "coin"},
            {"label": "Sell value", "value": object_graph.market.total_sell_value, "format": "coin"},
        ],
        "breakdown": [],
        "items": [],
        "insight": "Separate active orders from owned inventory so liquidity and pending commitments do not blur together.",
    }

    for ch in object_graph.characters:
        node_id = f"char:{_node_id(ch.name)}"
        nodes.append({"id": node_id, "group": "characters", "label": ch.name, "kind": "character", "count": len(ch.bag_items) + len(ch.equipment), "value": ch.equipment_value, "risk": "low"})
        details[node_id] = {
            "title": ch.name,
            "subtitle": f"{ch.profession or 'Unknown profession'} level {ch.level}",
            "metrics": [
                {"label": "Playtime", "value": f"{round(ch.playtime_hours)}h"},
                {"label": "Equipment", "value": len(ch.equipment)},
                {"label": "Bag items", "value": len(ch.bag_items)},
                {"label": "Build tabs", "value": ch.build_tabs},
            ],
            "breakdown": [
                {"label": "Race", "value": ch.race or "Unknown"},
                {"label": "Deaths", "value": ch.deaths},
                {"label": "Last login age", "value": f"{ch.last_login_days} days"},
            ],
            "items": [{
                "item_id": item.item_id,
                "count": item.count,
                "location": item.location,
                "location_ref": item.location_ref,
                "binding": item.binding or ("Tradable" if item.tradable else "Locked"),
                "value": item.value_after_fee or item.value_sell or item.value_buy,
            } for item in sorted(ch.bag_items, key=lambda item: item.value_after_fee or item.value_sell or item.value_buy, reverse=True)[:8]],
            "insight": "Character nodes should connect equipment and inventory to build readiness, not just show roster facts.",
        }

    return nodes, details


def _asset_insight(category: str, risk: str, unpriced: int, low_liquidity: int) -> str:
    if category == "Wallet":
        return "Wallet is immediately spendable and should anchor liquid-value decisions."
    if category == "Trading Post":
        return "Trading Post orders should be separated into pending buys and pending sells before action recommendations."
    if unpriced > 0:
        return f"{unpriced} stacks lack sell prices; treat this as hidden or uncertain value before recommending liquidation."
    if low_liquidity > 0 or risk != "low":
        return "Some value may be hard to convert quickly; show price quality before suggesting sales."
    return "This category is mostly priced and low-risk; expose top contributors and safe surplus next."


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
