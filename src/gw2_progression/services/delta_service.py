"""Snapshot comparison and value change attribution."""

import logging
from collections import defaultdict

from ..database import get_db
from ..models import AccountValueDelta, ItemHolding, ItemValueDelta

logger = logging.getLogger("gw2.delta")


def _build_item_key(h: ItemHolding) -> tuple:
    return (h.item_id, h.location_type)


def _holdings_map(holdings: list[ItemHolding]) -> dict[tuple, ItemHolding]:
    return {_build_item_key(h): h for h in holdings}


async def compare_snapshots(account_name: str, from_id: int, to_id: int) -> AccountValueDelta:
    """Compare two snapshots and produce a delta with change attribution."""
    db = await get_db()
    try:
        from_raw: list[ItemHolding] = await _load_snapshot_holdings(db, from_id)
        to_raw: list[ItemHolding] = await _load_snapshot_holdings(db, to_id)
    finally:
        await db.close()

    from_map = _holdings_map(from_raw)
    to_map = _holdings_map(to_raw)
    all_keys = set(from_map.keys()) | set(to_map.keys())

    delta = AccountValueDelta(
        account_name=account_name,
        from_snapshot_id=from_id,
        to_snapshot_id=to_id,
    )

    item_deltas: list[ItemValueDelta] = []
    total_price_effect = 0
    total_qty_effect = 0

    loc_deltas: dict[str, int] = defaultdict(int)

    for key in all_keys:
        old = from_map.get(key)
        new = to_map.get(key)

        old_id, loc = key
        old_count = old.count if old else 0
        new_count = new.count if new else 0
        old_price = old.price_buy if old else 0
        new_price = new.price_buy if new else 0
        old_val = old.value_buy if old else 0
        new_val = new.value_buy if new else 0

        count_delta = new_count - old_count
        price_delta = new_price - old_price
        val_delta = new_val - old_val

        if val_delta == 0 and count_delta == 0 and price_delta == 0:
            continue

        # Determine primary cause
        if old is None:
            cause = "new_item"
        elif new is None:
            cause = "removed_item"
        elif count_delta != 0 and price_delta == 0:
            cause = "quantity_change"
        elif count_delta == 0 and price_delta != 0:
            cause = "price_change"
        elif abs(count_delta * old_price) > abs(old_count * price_delta):
            cause = "quantity_change"
        else:
            cause = "price_change"

        # Price effect = new_count * price_delta (revaluation of existing items)
        # Quantity effect = count_delta * old_price (items added/removed at old price)
        if cause == "price_change":
            price_effect = old_count * price_delta
            qty_effect = 0
        elif cause == "quantity_change":
            price_effect = 0
            qty_effect = count_delta * old_price
        elif cause == "new_item":
            price_effect = 0
            qty_effect = new_val
        elif cause == "removed_item":
            price_effect = 0
            qty_effect = -old_val
        else:
            price_effect = 0
            qty_effect = 0

        total_price_effect += price_effect
        total_qty_effect += qty_effect

        loc_deltas[loc] += val_delta

        item_deltas.append(
            ItemValueDelta(
                item_id=old_id,
                old_count=old_count,
                new_count=new_count,
                count_delta=count_delta,
                old_price_buy=old_price,
                new_price_buy=new_price,
                price_delta=price_delta,
                old_value_buy=old_val,
                new_value_buy=new_val,
                value_delta=val_delta,
                primary_cause=cause,
            )
        )

    item_deltas.sort(key=lambda x: abs(x.value_delta), reverse=True)

    total_delta_buy_val = sum(d.value_delta for d in item_deltas)
    delta.total_delta_buy = total_delta_buy_val
    delta.total_delta_sell = total_delta_buy_val
    delta.wallet_delta = loc_deltas.get("wallet", 0)
    delta.material_delta = loc_deltas.get("material_storage", 0)
    delta.bank_delta = loc_deltas.get("bank", 0)
    delta.inventory_delta = loc_deltas.get("character", 0) + loc_deltas.get("shared_inventory", 0)
    delta.tradingpost_delta = loc_deltas.get("tradingpost", 0)
    delta.price_effect_delta = total_price_effect
    delta.quantity_effect_delta = total_qty_effect

    delta.top_gainers = [d for d in item_deltas if d.value_delta > 0][:20]
    delta.top_decliners = [d for d in item_deltas if d.value_delta < 0][:20]

    return delta


async def _load_snapshot_holdings(db, snapshot_id: int) -> list[ItemHolding]:
    """Load holdings for a specific snapshot by ID."""
    cursor = await db.execute(
        """SELECT item_id, count, location_type, location_ref, binding_status,
           tradable, vendor_value, price_buy, price_sell, value_buy, value_sell, valuation_status
           FROM item_holdings WHERE snapshot_id = ?""",
        (snapshot_id,),
    )
    rows = await cursor.fetchall()
    return [
        ItemHolding(
            item_id=row["item_id"],
            count=row["count"],
            location_type=row["location_type"],
            location_ref=row["location_ref"],
            binding_status=row["binding_status"],
            tradable=bool(row["tradable"]),
            vendor_value=row["vendor_value"],
            price_buy=row["price_buy"],
            price_sell=row["price_sell"],
            value_buy=row["value_buy"],
            value_sell=row["value_sell"],
            valuation_status=row["valuation_status"],
        )
        for row in rows
    ]


async def get_latest_snapshots(db, account_name: str, limit: int = 2) -> list[dict]:
    """Get the most recent snapshot IDs for an account."""
    cursor = await db.execute(
        "SELECT id, created_at FROM account_snapshots WHERE account_name = ? ORDER BY id DESC LIMIT ?",
        (account_name, limit),
    )
    rows = await cursor.fetchall()
    return [{"id": row["id"], "created_at": row["created_at"]} for row in rows]
