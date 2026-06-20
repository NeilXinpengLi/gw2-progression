"""Valuation engine: apply prices to holdings and compute account value."""

from ..models import (
    ItemHolding,
    LocationBreakdown,
    StatusBreakdown,
    TopItem,
    ValuationWarningModel,
    ValueBreakdown,
    ValueSummary,
)
from .price_service import compute_price_quality

TP_LISTING_FEE_RATE = 0.05
TP_EXCHANGE_FEE_RATE = 0.10
TP_TOTAL_FEE_RATE = 0.15

RELIABLE_STATUSES = {"reliable"}
RISKY_STATUSES = {"low_liquidity", "wide_spread", "missing_buy", "missing_sell", "illiquid"}


def apply_prices(
    holdings: list[ItemHolding],
    prices: dict[int, tuple[int, int]],
    price_details: dict[int, dict] | None = None,
) -> tuple[list[ItemHolding], list[ValuationWarningModel]]:
    """Apply market prices to holdings. Returns (enriched_holdings, warnings)."""
    warnings: list[ValuationWarningModel] = []

    for h in holdings:
        if h.valuation_status == "priced":
            continue

        if h.location_type == "wallet":
            h.valuation_status = "priced"
            h.value_buy = h.count
            h.value_sell = h.count
            h.price_buy = 1
            h.price_sell = 1
            h.quality_status = "reliable"
            h.liquidity_score = "high"
            continue

        if h.location_type == "tradingpost":
            h.valuation_status = "priced"
            h.quality_status = "reliable"
            continue

        if h.binding_status is not None:
            h.valuation_status = "account_bound"
            h.tradable = False
            warnings.append(
                ValuationWarningModel(
                    warning_type="account_bound",
                    message=f"Item #{h.item_id} is account-bound, no market value estimated",
                    item_id=h.item_id,
                )
            )
            continue

        price = prices.get(h.item_id)
        if price is None:
            h.valuation_status = "unpriced"
            h.tradable = False
            warnings.append(
                ValuationWarningModel(
                    warning_type="unpriced",
                    message=f"Item #{h.item_id} has no market price data",
                    item_id=h.item_id,
                )
            )
            continue

        buy_price, sell_price = price
        if buy_price == 0 and sell_price == 0:
            h.valuation_status = "unpriced"
            h.tradable = False
            warnings.append(
                ValuationWarningModel(
                    warning_type="no_price",
                    message=f"Item #{h.item_id} has zero buy and sell price (likely untradable)",
                    item_id=h.item_id,
                )
            )
            continue

        h.price_buy = buy_price
        h.price_sell = sell_price
        h.value_buy = h.count * buy_price
        h.value_sell = h.count * sell_price
        h.valuation_status = "priced"

        # Apply price quality
        details = (price_details or {}).get(h.item_id, {})
        quality = compute_price_quality(
            buy_price=buy_price,
            sell_price=sell_price,
            buy_qty=details.get("buy_quantity", 0),
            sell_qty=details.get("sell_quantity", 0),
        )
        h.quality_status = quality["quality_status"]
        h.liquidity_score = quality["liquidity_score"]
        h.spread = quality["spread"]
        h.spread_ratio = quality["spread_ratio"]
        h.buy_quantity = details.get("buy_quantity", 0)
        h.sell_quantity = details.get("sell_quantity", 0)

        if h.quality_status == "illiquid":
            warnings.append(
                ValuationWarningModel(
                    warning_type="illiquid",
                    message=f"Item #{h.item_id} has no buy/sell volume, value is speculative",
                    item_id=h.item_id,
                )
            )

    return holdings, warnings


def compute_summary(holdings: list[ItemHolding]) -> ValueSummary:
    by_location: dict[str, dict[str, int]] = {}
    for h in holdings:
        loc = h.location_type
        if loc not in by_location:
            by_location[loc] = {"buy": 0, "sell": 0, "count": 0, "unpriced": 0}
        by_location[loc]["buy"] += h.value_buy
        by_location[loc]["sell"] += h.value_sell
        by_location[loc]["count"] += 1
        if h.valuation_status == "unpriced":
            by_location[loc]["unpriced"] += 1

    priced = [h for h in holdings if h.valuation_status == "priced"]
    unpriced = [h for h in holdings if h.valuation_status == "unpriced" or h.valuation_status == "no_price"]
    account_bound = [h for h in holdings if h.valuation_status == "account_bound"]

    wl = by_location.get("wallet", {})
    mm = by_location.get("material_storage", {})
    bk = by_location.get("bank", {})
    ci = by_location.get("character", {})
    si = by_location.get("shared_inventory", {})
    tp = by_location.get("tradingpost", {})

    total_buy = sum(h.value_buy for h in priced)
    total_sell = sum(h.value_sell for h in priced)

    reliable = [h for h in priced if h.quality_status in RELIABLE_STATUSES]
    risky = [h for h in priced if h.quality_status in RISKY_STATUSES]
    low_liq = [h for h in priced if h.liquidity_score in ("low", "illiquid")]

    return ValueSummary(
        total_value_buy=total_buy,
        total_value_sell=total_sell,
        net_sell_value=int(total_sell * (1 - TP_TOTAL_FEE_RATE)),
        wallet_value=wl.get("buy", 0),
        material_value_buy=mm.get("buy", 0),
        material_value_sell=mm.get("sell", 0),
        bank_value_buy=bk.get("buy", 0),
        bank_value_sell=bk.get("sell", 0),
        character_inventory_value_buy=ci.get("buy", 0),
        character_inventory_value_sell=ci.get("sell", 0),
        shared_inventory_value_buy=si.get("buy", 0),
        shared_inventory_value_sell=si.get("sell", 0),
        tradingpost_value=tp.get("buy", 0) + tp.get("sell", 0),
        tradingpost_buy_value=tp.get("buy", 0),
        tradingpost_sell_value=tp.get("sell", 0),
        priced_item_count=len(priced),
        unpriced_item_count=len(unpriced),
        account_bound_count=len(account_bound),
        reliable_value=sum(h.value_buy for h in reliable),
        risky_value=sum(h.value_buy for h in risky),
        low_liquidity_count=len(low_liq),
        stale_price_count=0,
    )


def compute_breakdown(summary: ValueSummary, holdings: list[ItemHolding]) -> ValueBreakdown:
    total_buy = summary.total_value_buy or 1

    by_location = sorted(
        [
            LocationBreakdown(
                location="material_storage",
                label="Material Storage",
                value_buy=summary.material_value_buy,
                value_sell=summary.material_value_sell,
                percentage=round(summary.material_value_buy / total_buy * 100, 1),
            ),
            LocationBreakdown(
                location="bank",
                label="Bank",
                value_buy=summary.bank_value_buy,
                value_sell=summary.bank_value_sell,
                percentage=round(summary.bank_value_buy / total_buy * 100, 1),
            ),
            LocationBreakdown(
                location="character",
                label="Character Inventory",
                value_buy=summary.character_inventory_value_buy,
                value_sell=summary.character_inventory_value_sell,
                percentage=round(summary.character_inventory_value_buy / total_buy * 100, 1),
            ),
            LocationBreakdown(
                location="wallet",
                label="Wallet Gold",
                value_buy=summary.wallet_value,
                value_sell=summary.wallet_value,
                percentage=round(summary.wallet_value / total_buy * 100, 1),
            ),
            LocationBreakdown(
                location="tradingpost",
                label="Trading Post",
                value_buy=summary.tradingpost_value,
                value_sell=summary.tradingpost_value,
                percentage=round(summary.tradingpost_value / total_buy * 100, 1),
            ),
            LocationBreakdown(
                location="shared_inventory",
                label="Shared Inventory",
                value_buy=summary.shared_inventory_value_buy,
                value_sell=summary.shared_inventory_value_sell,
                percentage=round(summary.shared_inventory_value_buy / total_buy * 100, 1),
            ),
        ],
        key=lambda x: x.value_buy,
        reverse=True,
    )

    priced = [h for h in holdings if h.valuation_status == "priced"]
    unpriced = [h for h in holdings if h.valuation_status in ("unpriced", "no_price")]
    bound = [h for h in holdings if h.valuation_status == "account_bound"]

    by_status = [
        StatusBreakdown(status="priced", count=len(priced), value_buy=sum(h.value_buy for h in priced)),
        StatusBreakdown(status="unpriced", count=len(unpriced)),
        StatusBreakdown(status="account_bound", count=len(bound)),
    ]

    return ValueBreakdown(by_location=by_location, by_status=by_status)


def compute_top_items(holdings: list[ItemHolding], limit: int = 20) -> list[TopItem]:
    priced = [h for h in holdings if h.valuation_status == "priced" and h.location_type != "wallet"]
    priced.sort(key=lambda x: x.value_buy, reverse=True)
    return [
        TopItem(
            item_id=h.item_id,
            count=h.count,
            location_type=h.location_type,
            location_ref=h.location_ref,
            price_buy=h.price_buy,
            price_sell=h.price_sell,
            value_buy=h.value_buy,
            value_sell=h.value_sell,
            tradable=h.tradable,
            valuation_status=h.valuation_status,
        )
        for h in priced[:limit]
    ]
