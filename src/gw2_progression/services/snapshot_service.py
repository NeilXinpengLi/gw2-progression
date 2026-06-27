"""Snapshot Service — create, freeze, and derive from immutable account snapshots.

The foundation of the three-layer data architecture:
  Layer 1 (Raw):   GW2 API responses, stored as-is
  Layer 2 (Normalized):  gw2efficiency-aligned domain models
  Layer 3 (Derived):     AI/Decision intelligence from snapshot_id

All AI decisions MUST reference a snapshot_id. Snapshots are immutable
once created.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from ..database import get_db, using_db
from ..models_data import (
    AccountSnapshot,
    AccountValue,
    AssetBreakdown,
    AssetEntity,
    CharacterEntity,
    CurrencyEntity,
    DerivedAccountData,
    NormalizedAccountData,
    RawAccountData,
)
from .holdings_service import (
    extract_bank_holdings,
    extract_character_equipment,
    extract_character_holdings,
    extract_material_holdings,
    extract_shared_inventory_holdings,
    extract_tradingpost_holdings,
    extract_wallet_holdings,
)
from .price_service import compute_price_quality, fetch_prices

logger = logging.getLogger("gw2.snapshot")

TP_SELL_FEE = 0.85  # Trading post takes 15%


async def create_snapshot(api_key: str, raw_data: dict[str, Any]) -> str:
    """Create an immutable snapshot from raw GW2 API data.

    Returns snapshot_id (UUID). The raw data is stored for reproducibility.
    """
    snapshot_id = uuid.uuid4().hex[:16]
    timestamp = datetime.now(timezone.utc).isoformat()

    raw_account = raw_data.get("account", {})
    account_name = raw_account.get("name", "unknown")

    # Persist raw layer
    async with using_db() as db:
        await db.execute(
            """INSERT OR REPLACE INTO snapshot_registry
               (snapshot_id, account_name, raw_data, created_at)
               VALUES (?, ?, ?, ?)""",
            (snapshot_id, account_name, json.dumps(raw_data, default=str), timestamp),
        )

    logger.info("Snapshot %s created for %s", snapshot_id[:12], account_name)
    return snapshot_id


async def get_snapshot(snapshot_id: str) -> dict[str, Any] | None:
    """Load raw data for a snapshot_id."""
    async with using_db() as db:
        cursor = await db.execute(
            "SELECT raw_data FROM snapshot_registry WHERE snapshot_id = ?",
            (snapshot_id,),
        )
        row = await cursor.fetchone()
    if not row:
        return None
    return json.loads(row[0]) if isinstance(row[0], str) else row[0]


def normalize_account(raw: dict[str, Any]) -> NormalizedAccountData:
    """Layer 1 → Layer 2: Transform raw GW2 data into normalized domain models."""
    acct = raw.get("account", {})
    raw_wallet = raw.get("wallet", [])
    raw_chars = raw.get("characters", [])
    raw_materials = raw.get("materials", [])
    raw_bank = raw.get("bank", [])
    raw_shared = raw.get("shared_inventory", [])
    raw_tp_buys = raw.get("tradingpost_buys", [])
    raw_tp_sells = raw.get("tradingpost_sells", [])

    account_name = acct.get("name", "unknown")
    now = datetime.now(timezone.utc)

    # Snapshot metadata
    snapshot = AccountSnapshot(
        snapshot_id="",
        account_name=account_name,
        world=acct.get("world", 0),
        created_at=acct.get("created", ""),
        age_hours=round(acct.get("age", 0) / 3600, 1),
    )

    # Characters
    characters: list[CharacterEntity] = []
    for ch in raw_chars:
        created_str = ch.get("created", "")
        login_days = 0
        if created_str:
            try:
                created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                login_days = (now - created_dt).days
            except (ValueError, TypeError):
                pass
        characters.append(CharacterEntity(
            name=ch.get("name", "?"),
            profession=ch.get("profession", ""),
            level=ch.get("level", 0),
            playtime_hours=round(ch.get("age", 0) / 3600, 1),
            created=created_str,
            deaths=ch.get("deaths", 0),
            last_login_days=login_days,
        ))

    snapshot.character_count = len(characters)
    snapshot.total_levels = sum(c.level for c in characters)
    snapshot.max_level_count = sum(1 for c in characters if c.level == 80)

    # Assets from holdings extractors
    raw_holdings = []
    raw_holdings.extend(extract_wallet_holdings(raw_wallet))
    raw_holdings.extend(extract_material_holdings(raw_materials))
    raw_holdings.extend(extract_bank_holdings(raw_bank))
    raw_holdings.extend(extract_character_equipment(raw_chars))  # gear slot
    raw_holdings.extend(extract_character_holdings(raw_chars))   # bag items
    raw_holdings.extend(extract_shared_inventory_holdings(raw_shared))
    raw_holdings.extend(extract_tradingpost_holdings(raw_tp_buys, raw_tp_sells))

    assets: list[AssetEntity] = []
    for h in raw_holdings:
        assets.append(AssetEntity(
            item_id=h.item_id,
            count=h.count,
            location=h.location_type,
            location_ref=h.location_ref or "",
            binding=h.binding_status or "",
            tradable=h.tradable,
            price_buy=h.price_buy,
            price_sell=h.price_sell,
            value_buy=h.value_buy,
            value_sell=h.value_sell,
            value_after_fee=int(h.value_sell * TP_SELL_FEE),
            liquidity=h.liquidity_score or "unknown",
            confidence=h.confidence,
            data_source="gw2_api",
        ))

    # Currencies
    currencies = CurrencyEntity()
    for entry in raw_wallet if isinstance(raw_wallet, list) else []:
        cid = entry.get("id")
        val = entry.get("value", 0)
        if cid == 1:
            currencies.gold = val // 10000
            currencies.silver = (val // 100) % 100
            currencies.copper = val % 100
        elif cid == 2:
            currencies.karma = val
        elif cid == 3:
            currencies.laurels = val
        elif cid == 4:
            currencies.spirit_shards = val

    return NormalizedAccountData(
        snapshot=snapshot,
        characters=characters,
        assets=assets,
        currencies=currencies,
    )


async def derive_value(normalized: NormalizedAccountData) -> AccountValue:
    """Layer 2 → Layer 3: Compute AI-ready account value from normalized data."""
    assets = normalized.assets

    wallet_val = sum(a.value_sell for a in assets if a.location == "wallet")
    material_val = sum(a.value_sell for a in assets if a.location == "material_storage")
    bank_val = sum(a.value_sell for a in assets if a.location == "bank")
    char_val = sum(a.value_sell for a in assets if a.location == "character")
    shared_val = sum(a.value_sell for a in assets if a.location == "shared_inventory")
    tp_buy_val = sum(a.value_sell for a in assets if a.location == "tradingpost" and a.location_ref == "buy_order")
    tp_sell_val = sum(a.value_sell for a in assets if a.location == "tradingpost" and a.location_ref == "sell_order")

    total = wallet_val + material_val + bank_val + char_val + shared_val + tp_buy_val + tp_sell_val

    priced = [a for a in assets if a.price_sell > 0]
    confidence = min(sum(a.confidence for a in priced) / max(len(priced), 1), 1.0) if priced else 0.0

    return AccountValue(
        total_value=total,
        liquid_value=int(total * TP_SELL_FEE),
        liquid_value_buy=sum(a.value_buy for a in assets),
        wallet_gold=normalized.currencies.gold,
        material_value=material_val,
        bank_value=bank_val,
        character_value=char_val,
        shared_inventory_value=shared_val,
        tp_buy_value=tp_buy_val,
        tp_sell_value=tp_sell_val,
        confidence=round(confidence, 2),
    )


def derive_breakdown(assets: list[AssetEntity]) -> list[AssetBreakdown]:
    """Compute asset category breakdown by economic value source (gw2efficiency style).

    Categories reflect how value is held, not where items are stored:
      - Wallet:        liquid gold
      - Bank:           items in bank storage
      - Material Storage: crafting materials
      - Equipment:      gear equipped on characters (from equipment slots)
      - Character Inventory: items in character bags
      - Shared Inventory:   shared inventory slots
      - Trading Post:   active buy/sell orders
    """
    total = sum(a.value_sell for a in assets)
    cat_values: dict[str, int] = {}
    cat_items: dict[str, list[AssetEntity]] = {}

    for a in assets:
        if a.location == "wallet":
            label = "Wallet"
        elif a.location == "material_storage":
            label = "Material Storage"
        elif a.location == "bank":
            label = "Bank"
        elif a.location == "character_equipment":
            label = "Equipment"
        elif a.location == "character":
            label = "Character Inventory"
        elif a.location == "shared_inventory":
            label = "Shared Inventory"
        elif a.location == "tradingpost":
            label = "Trading Post"
        else:
            label = a.location.replace("_", " ").title()

        cat_values[label] = cat_values.get(label, 0) + a.value_after_fee
        cat_items.setdefault(label, []).append(a)

    order = ["Wallet", "Material Storage", "Bank", "Equipment", "Character Inventory", "Shared Inventory", "Trading Post"]
    breakdown = []
    for label in order:
        val = cat_values.get(label, 0)
        items = cat_items.get(label, [])
        low_liquidity = sum(1 for i in items if i.liquidity in ("low", "illiquid"))
        risk = "high" if len(items) > 0 and low_liquidity / len(items) > 0.5 else "medium" if low_liquidity > 0 else "low"
        breakdown.append(AssetBreakdown(
            category=label,
            total_value=val,
            liquid_value=val,
            percentage=round(val / max(total, 1) * 100, 1),
            risk=risk,
            item_count=len(items),
        ))
    return breakdown


# ── Legacy: run_full_analysis (used by /value/analyze) ──────────────


def _hash_key(api_key: str) -> str:
    import hashlib
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


async def run_full_analysis(api_key: str) -> Any:
    """Full account analysis — kept for /value/analyze backward compat."""
    from ..analyzer import fetch_all
    from ..database import get_db, save_account_snapshot
    from ..models import ValueAnalyzeResponse
    from .holdings_service import (
        extract_bank_holdings,
        extract_character_holdings,
        extract_material_holdings,
        extract_shared_inventory_holdings,
        extract_tradingpost_holdings,
        extract_wallet_holdings,
    )
    from .item_service import is_account_bound
    from .price_service import fetch_prices
    from .valuation_service import apply_prices, compute_summary

    contents = await fetch_all(api_key)
    account_name = contents.account_name or "unknown"

    holdings = []
    holdings.extend(extract_wallet_holdings(contents.wallet))
    holdings.extend(extract_material_holdings(contents.materials))
    holdings.extend(extract_bank_holdings(contents.bank))
    holdings.extend(extract_character_holdings(contents.characters))
    holdings.extend(extract_shared_inventory_holdings(contents.shared_inventory))
    holdings.extend(extract_tradingpost_holdings(contents.tradingpost_buys, contents.tradingpost_sells))

    unpriced_ids = list(set(
        h.item_id for h in holdings
        if h.valuation_status == "pending"
        and h.location_type not in ("wallet", "tradingpost")
        and h.binding_status is None
    ))

    prices = {}
    price_details = {}
    if unpriced_ids:
        price_data = await fetch_prices(unpriced_ids)
        prices = {item_id: (pd.buy_unit_price, pd.sell_unit_price) for item_id, pd in price_data.items()}
        price_details = {
            item_id: {
                "buy_quantity": pd.buy_quantity,
                "sell_quantity": pd.sell_quantity,
                "fetched_at": getattr(pd, "fetched_at", ""),
                "source": getattr(pd, "source", "gw2_commerce_prices"),
            }
            for item_id, pd in price_data.items()
        }

    all_holdings, warnings = apply_prices(holdings, prices, price_details)

    unpriced_ids = list(set(
        h.item_id for h in all_holdings
        if h.valuation_status in ("unpriced", "no_price") and h.binding_status is None
    ))
    if unpriced_ids:
        bound_flags = await is_account_bound(unpriced_ids)
        for h in all_holdings:
            if h.item_id in bound_flags and bound_flags[h.item_id] and h.valuation_status in ("unpriced", "no_price"):
                h.valuation_status = "account_bound"
                h.tradable = False
                h.confidence = 1.0
                h.data_sources = ["gw2_account_inventory", "gw2_items"]

    snapshot_id = 0
    db = await get_db()
    try:
        summary = compute_summary(all_holdings)
        snapshot_id = await save_account_snapshot(db, account_name, _hash_key(api_key), summary, all_holdings, warnings)
        await db.commit()
    finally:
        await db.close()

    result = ValueAnalyzeResponse(
        summary=summary,
        breakdown=summary.breakdown,
        top_items=sorted(all_holdings, key=lambda h: h.value_sell, reverse=True)[:20],
        holdings=all_holdings,
        warnings=[],
        history=[],
    )
    return result
