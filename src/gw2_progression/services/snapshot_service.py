"""Orchestrates the full value analysis pipeline."""

import hashlib
import logging

from ..analyzer import fetch_all
from ..database import get_db, load_value_history, save_account_snapshot
from ..models import (
    ValueAnalyzeResponse,
)
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
from .valuation_service import (
    apply_prices,
    compute_breakdown,
    compute_summary,
    compute_top_items,
)

logger = logging.getLogger("gw2.snapshot")


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


async def run_full_analysis(api_key: str) -> ValueAnalyzeResponse:
    contents = await fetch_all(api_key)
    account_name = contents.account_name or "unknown"

    holdings = []
    holdings.extend(extract_wallet_holdings(contents.wallet))
    holdings.extend(extract_material_holdings(contents.materials))
    holdings.extend(extract_bank_holdings(contents.bank))
    holdings.extend(extract_character_holdings(contents.characters))
    holdings.extend(extract_shared_inventory_holdings(contents.shared_inventory))
    holdings.extend(extract_tradingpost_holdings(contents.tradingpost_buys, contents.tradingpost_sells))

    unpriced_ids = list(set(h.item_id for h in holdings if h.valuation_status == "pending" and h.location_type not in ("wallet", "tradingpost") and h.binding_status is None))

    prices = {}
    if unpriced_ids:
        price_data = await fetch_prices(unpriced_ids)
        prices = {item_id: (pd.buy_unit_price, pd.sell_unit_price) for item_id, pd in price_data.items()}

    all_holdings, warnings = apply_prices(holdings, prices)

    # Refine: check item flags for unpriced items (may be account-bound without binding field)
    unpriced_ids = list(set(h.item_id for h in all_holdings if h.valuation_status in ("unpriced", "no_price") and h.binding_status is None))
    if unpriced_ids:
        bound_flags = await is_account_bound(unpriced_ids)
        for h in all_holdings:
            if h.item_id in bound_flags and bound_flags[h.item_id] and h.valuation_status in ("unpriced", "no_price"):
                h.valuation_status = "account_bound"
                h.tradable = False
                warnings.append(
                    type(
                        "W",
                        (),
                        {"warning_type": "account_bound", "message": f"Item #{h.item_id} is account-bound by item flags", "item_id": h.item_id},
                    )()
                )

    summary = compute_summary(all_holdings)
    breakdown = compute_breakdown(summary, all_holdings)
    top_items = compute_top_items(all_holdings)

    missing_perms = []
    if contents.bank is None:
        missing_perms.append("inventories")
    if contents.characters is None:
        missing_perms.append("characters")
    if contents.tradingpost_buys is None:
        missing_perms.append("tradingpost")
    if missing_perms:
        warnings.insert(
            0,
            type(
                "W",
                (),
                {
                    "warning_type": "missing_permissions",
                    "message": f"Missing API permissions: {', '.join(missing_perms)}. Value may be incomplete.",
                    "item_id": None,
                },
            )(),
        )

    snapshot_id = None
    api_key_hash = _hash_key(api_key)

    try:
        db = await get_db()
        try:
            snapshot_id = await save_account_snapshot(db, account_name, api_key_hash, summary, all_holdings, warnings)
        finally:
            await db.close()
    except Exception as e:
        logger.warning("Failed to save snapshot (continuing): %s", e)

    history = []
    try:
        db = await get_db()
        try:
            history = await load_value_history(db, account_name)
        finally:
            await db.close()
    except Exception as e:
        logger.warning("Failed to load history (continuing): %s", e)

    summary.snapshot_id = snapshot_id
    summary.snapshot_time = history[0].snapshot_time if history else ""

    return ValueAnalyzeResponse(
        summary=summary,
        breakdown=breakdown,
        top_items=top_items,
        holdings=all_holdings,
        warnings=[{"warning_type": w.warning_type, "message": w.message, "item_id": w.item_id} for w in warnings],
        history=history,
    )
