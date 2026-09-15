"""Trading Post Strategy Engine — sell/buy signals, protected assets."""

import logging

from ..database import get_db
from ..models import ProtectedAsset, TradingPostSignal
from .listing_service import analyze_depth, fetch_listings

logger = logging.getLogger("gw2.tp")


def _signal_metadata(
    signal_type: str,
    holding_confidence: float = 0.0,
    depth: dict | None = None,
) -> dict:
    depth_confidence = float((depth or {}).get("confidence", 0.0))
    confidence = max(holding_confidence, depth_confidence)
    if signal_type == "protected_asset":
        confidence = max(confidence, 0.90)
        risk_reason = "Item is protected by an active goal, so selling should be avoided."
    elif signal_type == "high_spread":
        confidence = min(max(confidence, 0.60), 0.70)
        risk_reason = (depth or {}).get("risk_reason", "Wide spread makes execution price uncertain.")
    elif signal_type == "low_liquidity":
        confidence = min(max(confidence, 0.50), 0.65)
        risk_reason = (depth or {}).get("risk_reason", "Low order depth may make this hard to liquidate.")
    else:
        confidence = min(max(confidence, 0.70), 0.88)
        risk_reason = (depth or {}).get("risk_reason", "Sell candidate uses current account valuation and TP listing depth.")

    return {
        "confidence": round(confidence, 2),
        "data_sources": sorted({"gw2_account_holdings", "gw2_commerce_listings", *((depth or {}).get("data_sources", []))}),
        "price_timestamp": (depth or {}).get("price_timestamp", ""),
        "liquidity_reason": (depth or {}).get("liquidity_reason", ""),
        "risk_reason": risk_reason,
    }


async def generate_signals(account_name: str) -> list[TradingPostSignal]:
    """Generate TP signals for an account based on holdings and market data."""
    from ..database import load_latest_holdings

    db = await get_db()
    try:
        holdings = await load_latest_holdings(db, account_name)
    finally:
        await db.close()

    if not holdings:
        return []

    # Get goals to detect protected assets
    goal_protected: set[int] = set()
    try:
        db2 = await get_db()
        try:
            cursor = await db2.execute("SELECT target_item_id FROM tracked_goals WHERE account_name = ? AND status = 'active'", (account_name,))
            for row in await cursor.fetchall():
                goal_protected.add(row["target_item_id"])
        finally:
            await db2.close()
    except Exception:
        pass

    # Get manual protected assets
    manual_protected: set[int] = set()
    try:
        cursor = await (await get_db()).execute("SELECT item_id FROM protected_assets WHERE account_name = ?", (account_name,))
        for row in await cursor.fetchall():
            manual_protected.add(row["item_id"])
    except Exception:
        pass

    signals: list[TradingPostSignal] = []
    priced_holdings = [h for h in holdings if h.valuation_status == "priced" and h.location_type != "wallet" and h.tradable]

    # Fetch listings for high-value items
    high_value = sorted(priced_holdings, key=lambda h: h.value_buy, reverse=True)[:100]
    listing_ids = list(set(h.item_id for h in high_value if h.item_id > 0))
    listings = await fetch_listings(listing_ids)

    for h in high_value:
        is_goal_item = h.item_id in goal_protected
        is_manual = h.item_id in manual_protected
        listing = listings.get(h.item_id)
        depth = analyze_depth(listing) if listing else None

        # Goal-protected
        if is_goal_item:
            signals.append(
                TradingPostSignal(
                    item_id=h.item_id,
                    signal_type="protected_asset",
                    severity="info",
                    reason="Protected by active tracked goal",
                    quantity_owned=h.count,
                    value_owned=h.value_buy,
                    **_signal_metadata("protected_asset", h.confidence, depth),
                )
            )
            continue

        if is_manual:
            continue

        # High spread
        if depth and depth["spread_ratio"] > 0.2:
            signals.append(
                TradingPostSignal(
                    item_id=h.item_id,
                    signal_type="high_spread",
                    severity="warning",
                    reason=f"High spread: {(depth['spread_ratio'] * 100):.0f}%",
                    spread_ratio=depth["spread_ratio"],
                    quantity_owned=h.count,
                    value_owned=h.value_buy,
                    **_signal_metadata("high_spread", h.confidence, depth),
                )
            )

        # Low liquidity
        if depth and depth.get("liquidity_score") in ("low", "illiquid"):
            signals.append(
                TradingPostSignal(
                    item_id=h.item_id,
                    signal_type="low_liquidity",
                    severity="warning",
                    reason=f"Low liquidity: {depth.get('liquidity_score', 'unknown')}",
                    quantity_owned=h.count,
                    value_owned=h.value_buy,
                    **_signal_metadata("low_liquidity", h.confidence, depth),
                )
            )

        # Sell candidate: not goal-protected, high value, not time-gated
        if not is_goal_item and h.value_buy >= 50000 and h.count >= 10:
            signals.append(
                TradingPostSignal(
                    item_id=h.item_id,
                    signal_type="sell_candidate",
                    severity="info",
                    reason=f"Sell candidate: {h.count}x valued at {h.value_buy // 10000}g",
                    current_buy_price=h.price_buy,
                    current_sell_price=h.price_sell,
                    quantity_owned=h.count,
                    value_owned=h.value_buy,
                    **_signal_metadata("sell_candidate", h.confidence, depth),
                )
            )

    return signals


async def get_protected_assets(account_name: str) -> list[ProtectedAsset]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM protected_assets WHERE account_name = ?", (account_name,))
        rows = await cursor.fetchall()
        return [ProtectedAsset(**dict(r)) for r in rows]
    finally:
        await db.close()


async def protect_asset(account_name: str, item_id: int, reason: str = "manual_lock", linked_goal_id: str = "") -> ProtectedAsset:
    asset = ProtectedAsset(account_name=account_name, item_id=item_id, reason=reason, linked_goal_id=linked_goal_id)
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO protected_assets (account_name, item_id, protected_count, reason, linked_goal_id) VALUES (?, ?, 1, ?, ?)",
            (account_name, item_id, reason, linked_goal_id),
        )
        await db.commit()
    finally:
        await db.close()
    return asset


async def unprotect_asset(account_name: str, item_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM protected_assets WHERE account_name = ? AND item_id = ?", (account_name, item_id))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
