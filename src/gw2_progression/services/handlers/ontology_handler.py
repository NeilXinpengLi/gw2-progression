"""Event bus handler: ontology sync — account/asset/goal graph operations.

Runs asynchronously via event bus worker. Never blocks API requests.
"""

import logging
from typing import Any

from gw2_progression.database import _pool
from gw2_progression.services.event_bus import EventType, on

logger = logging.getLogger("gw2.event.ontology")


@on(EventType.ONTOLOGY)
async def handle_ontology_sync(event: Any) -> None:
    """Consumer: sync account data to ontology graph."""
    payload = event.payload
    api_key = payload.get("api_key", "")
    account_name = payload.get("account_name", "")
    if not account_name:
        return

    if _pool is None:
        logger.debug("Ontology sync skipped: DB pool not ready")
        return

    try:
        from gw2_progression.ontology.account_mapper import sync_account_to_ontology
        await sync_account_to_ontology(api_key, account_name)
        logger.debug("Ontology sync completed for %s", account_name)
    except Exception as e:
        logger.warning("Ontology sync failed for %s: %s", account_name, e)
