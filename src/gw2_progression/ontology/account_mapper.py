"""Account Mapper — maps raw account data into ontology objects and relations.

After fetching account data via the GW2 API, this mapper creates:
  - AccountSnapshot object
  - AccountAsset objects per holding (materials, bank, inventory)
  - "owns" relations from snapshot to each asset
"""

import logging

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

    for h in holdings:
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

    snapshot_props["snapshot_id"] = id(snapshot)
    store.update_object(snapshot.object_id, properties=snapshot_props)
    logger.info("Synced %d assets to ontology for %s", len(holdings), account_name)
    return created
