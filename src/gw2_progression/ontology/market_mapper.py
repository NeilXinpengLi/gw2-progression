"""Market Domain — maps TP signals, price data, and sell/hold candidates into ontology.

Provides planning signals only. No auto-trading, no profit guarantees.
Low-liquidity items are down-weighted. Stale prices block strong signals.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from ..models import TradingPostSignal
from . import object_store as store
from .models import OntologyObject

logger = logging.getLogger("gw2.ontology.market")

STALE_PRICE_HOURS = 24


def map_signal_to_ontology(
    signal: TradingPostSignal,
    account_name: str,
) -> OntologyObject:
    signal_props = {
        "signal_type": signal.signal_type,
        "item_id": signal.item_id,
        "severity": signal.severity,
        "reason": signal.reason,
        "current_buy_price": signal.current_buy_price,
        "current_sell_price": signal.current_sell_price,
        "spread_ratio": signal.spread_ratio,
        "quantity_owned": signal.quantity_owned,
        "value_owned": signal.value_owned,
        "linked_goal_id": signal.linked_goal_id or "",
        "confidence": signal.confidence,
        "data_sources": signal.data_sources,
        "price_timestamp": signal.price_timestamp,
        "liquidity_reason": signal.liquidity_reason,
        "risk_reason": signal.risk_reason,
        "price_stale": False,
    }

    if signal.price_timestamp:
        try:
            ts = datetime.fromisoformat(signal.price_timestamp.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            signal_props["price_stale"] = age > STALE_PRICE_HOURS
        except (ValueError, TypeError):
            signal_props["price_stale"] = True

    class_name = _signal_class(signal.signal_type)
    obj = store.register_object(
        class_name=class_name,
        account_name=account_name,
        properties=signal_props,
        privacy_scope="private",
    )

    snapshot_objs = store.get_objects_by_account("account_snapshot", account_name)
    if snapshot_objs:
        latest = max(snapshot_objs, key=lambda o: o.created_at)
        store.register_relation(
            source_id=obj.object_id,
            target_id=latest.object_id,
            relation_type="generated_from",
            confidence=signal.confidence,
        )

    return obj


def _signal_class(signal_type: str) -> str:
    mapping = {
        "sell_candidate": "sell_candidate",
        "buy_candidate": "buy_candidate",
        "protected_asset": "protected_market_asset",
        "low_liquidity": "low_liquidity_warning",
        "high_spread": "high_spread_warning",
        "price_anomaly": "price_anomaly",
    }
    return mapping.get(signal_type, "market_signal")


def get_active_sell_candidates(account_name: str) -> list[OntologyObject]:
    return [
        o for o in store.get_objects_by_account("sell_candidate", account_name)
        if o.properties.get("signal_type") == "sell_candidate"
    ]


def get_active_buy_candidates(account_name: str) -> list[OntologyObject]:
    return [
        o for o in store.get_objects_by_account("buy_candidate", account_name)
        if o.properties.get("signal_type") == "buy_candidate"
    ]


def get_protected_market_assets(account_name: str) -> list[OntologyObject]:
    return store.get_objects_by_account("protected_market_asset", account_name)


def check_price_freshness(item_id: int, account_name: str) -> dict[str, Any]:
    signal_classes = {"sell_candidate", "buy_candidate", "protected_market_asset", "low_liquidity_warning", "high_spread_warning", "price_anomaly", "market_signal"}
    for class_name in signal_classes:
        for obj in store.get_objects_by_account(class_name, account_name):
            if obj.properties.get("item_id") == item_id:
                stale = obj.properties.get("price_stale", True)
                return {
                    "item_id": item_id,
                    "is_stale": stale,
                    "price_timestamp": obj.properties.get("price_timestamp", ""),
                    "source": "ontology_market_mapper",
                }
    return {"item_id": item_id, "is_stale": True, "source": "not_found"}
