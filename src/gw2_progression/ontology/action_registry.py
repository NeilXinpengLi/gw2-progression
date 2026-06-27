"""Action Registry — controlled action execution with preconditions, rollback, and QA hooks.

Every operation that affects player plans, reports, recommendations,
do-not-sell, or build fit must pass through the Action Registry.  Each
action defines input_schema, preconditions, effects, affected objects,
rollback strategy, privacy/freshness policies, and optional QA hooks.
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
_qa_hooks: dict[str, list[Callable[..., Any]]] = {}
_rollback_handlers: dict[str, Callable[..., Any]] = {}


def register_action(action_type: str, handler: Callable[..., Any]) -> None:
    _registry[action_type] = handler


def register_qa_hook(action_type: str, hook: Callable[..., Any]) -> None:
    """Register a post-execution QA hook for an action type."""
    _qa_hooks.setdefault(action_type, []).append(hook)


def register_rollback(action_type: str, handler: Callable[..., Any]) -> None:
    """Register a rollback handler for an action type."""
    _rollback_handlers[action_type] = handler


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

    # 1. Check preconditions
    preconditions = definition.get("preconditions", [])
    if not force and preconditions:
        action.preconditions_met = False
        action.status = "failed"
        action.error = f"Preconditions not met: {preconditions}"
        await persist_action(action)
        logger.warning("Action %s blocked by preconditions: %s", action_type, preconditions)
        return action

    action.preconditions_met = True

    # 2. Execute handler
    handler = _registry.get(action_type)
    if handler:
        try:
            result = await handler(action, **(params or {}))
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
            # Auto-rollback on failure if rollback_strategy != "manual"
            await _auto_rollback(action)
            return action

    # 3. Run QA hooks
    action.qa_status = "pass"
    hooks = _qa_hooks.get(action_type, [])
    hook_errors: list[str] = []
    for hook in hooks:
        try:
            hook_result = await hook(action, **(params or {}))
            if isinstance(hook_result, str) and hook_result:
                hook_errors.append(hook_result)
        except Exception as e:
            hook_errors.append(str(e))
    if hook_errors:
        action.qa_status = "fail"
        action.error = "; ".join(hook_errors)
        logger.warning("Action %s QA hooks failed: %s", action_type, hook_errors)

    action.status = "completed" if action.qa_status == "pass" else "failed"
    action.completed_at = datetime.now(timezone.utc).isoformat()
    await persist_action(action)

    return action


async def rollback_action(action: OntologyAction) -> bool:
    """Execute rollback for a previously completed action."""
    handler = _rollback_handlers.get(action.action_type)
    if not handler:
        logger.warning("No rollback handler for action type: %s", action.action_type)
        return False
    try:
        await handler(action, **(action.params or {}))
        action.status = "rolled_back"
        action.error = ""
        await persist_action(action)
        logger.info("Rollback succeeded for action %s", action.action_id)
        return True
    except Exception as e:
        action.error = f"Rollback failed: {e}"
        await persist_action(action)
        logger.error("Rollback failed for action %s: %s", action.action_id, e)
        return False


async def _auto_rollback(action: OntologyAction) -> None:
    """Auto-rollback when strategy is not 'manual' or 'none'."""
    strategy = action.rollback_strategy
    if strategy in ("manual", "none"):
        return
    await rollback_action(action)
