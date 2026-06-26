"""Account Mapper — maps raw account data into ontology objects and relations.

After fetching account data via the GW2 API, this mapper creates:
  - AccountSnapshot object
  - AccountAsset objects per holding (materials, bank, inventory)
  - "owns" relations from snapshot to each asset

Supports delta sync: reuses existing snapshot and only syncs assets whose
item_id or count changed since the last snapshot.
"""

import logging
from datetime import datetime, timezone

from ..database import load_latest_holdings, using_db
from . import object_store as store
from .models import OntologyObject

logger = logging.getLogger("gw2.ontology.account")


async def sync_account_to_ontology(api_key: str, account_name: str) -> list[OntologyObject]:
    created: list[OntologyObject] = []

    db = await using_db().__aenter__()
    try:
        holdings = await load_latest_holdings(db, account_name)
    finally:
        await db.close()

    # Delta: find existing snapshot and assets, update counts
    existing_snapshots = store.get_objects_by_account("account_snapshot", account_name)
    if existing_snapshots:
        latest = max(existing_snapshots, key=lambda o: o.created_at)
        now = datetime.now(timezone.utc).isoformat()
        store.update_object(latest.object_id, properties={
            **latest.properties,
            "total_holdings": len(holdings),
            "resync_at": now,
        })
        snapshot = latest
        created.append(snapshot)
    else:
        snapshot_props = {
            "account_name": account_name,
            "snapshot_id": 0,
            "total_holdings": len(holdings),
            "created_at": "",
        }
        snapshot = store.register_object(
            class_name="account_snapshot",
            account_name=account_name,
            properties=snapshot_props,
            privacy_scope="private",
        )
        created.append(snapshot)
        snapshot_props["snapshot_id"] = id(snapshot)
        store.update_object(snapshot.object_id, properties=snapshot_props)

    for h in holdings:
        existing_assets = [
            a for a in store.get_objects_by_account("account_asset", account_name)
            if a.properties.get("item_id") == h.item_id
            and a.properties.get("location") == h.location_type
        ]
        if existing_assets:
            existing = existing_assets[0]
            old_count = existing.properties.get("count", 0)
            if old_count != h.count:
                store.update_object(existing.object_id, properties={
                    **existing.properties,
                    "count": h.count,
                    "value_buy": h.value_buy,
                    "value_sell": h.value_sell,
                    "delta": h.count - old_count,
                })
                logger.debug("Delta asset %d: %d → %d", h.item_id, old_count, h.count)
        else:
            asset_props = {
                "item_id": h.item_id,
                "count": h.count,
                "location": h.location_type,
                "location_ref": h.location_ref or "",
                "tradable": h.tradable,
                "value_buy": h.value_buy,
                "value_sell": h.value_sell,
                "binding_status": h.binding_status or "",
                "confidence": h.confidence,
            }
            asset = store.register_object(
                class_name="account_asset",
                account_name=account_name,
                properties=asset_props,
                privacy_scope="private",
                source_object_id=snapshot.object_id,
            )
            created.append(asset)

            store.register_relation(
                source_id=snapshot.object_id,
                target_id=asset.object_id,
                relation_type="owns",
                confidence=0.95,
            )

    logger.info("Synced %d assets (%d delta) to ontology for %s", len(holdings), len(holdings) - sum(1 for h in holdings if any(
        a.properties.get("item_id") == h.item_id and a.properties.get("location") == h.location_type
        for a in store.get_objects_by_account("account_asset", account_name)
    )), account_name)
    return created
