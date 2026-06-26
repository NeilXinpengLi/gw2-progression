"""Action Registry — controlled action execution with preconditions and effects.

Every operation that affects player plans, reports, recommendations,
do-not-sell, or build fit must pass through the Action Registry.  Each
action defines input_schema, preconditions, effects, affected objects,
rollback strategy, and privacy/freshness policies.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from .config import ACTION_DEFINITIONS
from .models import OntologyAction
from .object_store import persist_action

logger = logging.getLogger("gw2.ontology.action")

_registry: dict[str, Callable[..., Any]] = {}


def register_action(action_type: str, handler: Callable[..., Any]) -> None:
    _registry[action_type] = handler


def get_action_definition(action_type: str) -> dict | None:
    return ACTION_DEFINITIONS.get(action_type)


def list_action_types() -> list[str]:
    return list(ACTION_DEFINITIONS.keys())


async def execute_action(
    action_type: str,
    account_name: str = "",
    params: dict | None = None,
    force: bool = False,
) -> OntologyAction:
    definition = ACTION_DEFINITIONS.get(action_type)
    if not definition:
        raise ValueError(f"Unknown action type: {action_type}")

    now = datetime.now(timezone.utc).isoformat()
    action = OntologyAction(
        action_id=f"act_{uuid.uuid4().hex[:12]}",
        action_type=action_type,
        account_name=account_name,
        params=params or {},
        preconditions_met=False,
        rollback_strategy=definition.get("rollback_strategy", "manual"),
        privacy_policy=definition.get("privacy_policy", "private"),
        freshness_policy=definition.get("freshness_policy", "any"),
        created_at=now,
    )

    preconditions = definition.get("preconditions", [])
    if not force and preconditions:
        action.preconditions_met = False
        action.status = "failed"
        action.error = f"Preconditions not met: {preconditions}"
        await persist_action(action)
        logger.warning("Action %s blocked by preconditions: %s", action_type, preconditions)
        return action

    action.preconditions_met = True
    action.status = "completed"
    action.completed_at = datetime.now(timezone.utc).isoformat()
    action.qa_status = "pass"

    handler = _registry.get(action_type)
    if handler:
        try:
            result = await handler(action, **params)
            if isinstance(result, list):
                action.affected_object_ids = result
            elif isinstance(result, str):
                action.affected_object_ids = [result]
        except Exception as e:
            action.status = "failed"
            action.error = str(e)
            action.qa_status = "fail"
            logger.error("Action %s failed: %s", action_type, e)
    await persist_action(action)

    return action
