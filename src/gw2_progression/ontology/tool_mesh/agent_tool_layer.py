"""AgentToolLayer — agent-facing interface with governance.

Controls what tools an agent can call:
  1. Forbidden operation interception
  2. ActionRegistry bridge for governed actions
  3. QA post-validation
  4. Tool call recording to ToolMemory
"""

import logging
from typing import Any

from ..action_registry import execute_action as registry_execute
from ..policy_engine import PolicyLevel, evaluate as evaluate_policies, PolicyResult
from .tool_registry import execute as tool_execute

logger = logging.getLogger("gw2.ontology.agent_tool")

FORBIDDEN_OPERATIONS: list[str] = [
    "delete_account_data",
    "modify_api_key",
    "publish_unchecked",
    "override_qa_gate",
]

ALLOWED_WITH_OVERRIDE: list[str] = [
    "delete_snapshot",
    "delete_goal",
]


async def call(
    tool_name: str,
    arguments: dict | None = None,
    agent_name: str = "",
    bypass_policies: bool = False,
) -> dict:
    """Agent-facing tool call with governance.

    1. Check forbidden operations
    2. Evaluate runtime policies
    3. Execute tool via ToolRegistry
    4. Record to ToolMemory (if available)
    """
    arguments = arguments or {}

    # 1. Forbidden operation check
    if tool_name in FORBIDDEN_OPERATIONS:
        return {
            "success": False,
            "error": f"Operation '{tool_name}' is forbidden for agents",
            "tool_id": tool_name,
        }

    if tool_name in ALLOWED_WITH_OVERRIDE and not bypass_policies:
        return {
            "success": False,
            "error": f"Operation '{tool_name}' requires bypass_policies=True",
            "tool_id": tool_name,
        }

    # 2. Policy evaluation (L2_RUNTIME)
    if not bypass_policies:
        policy_results = await evaluate_policies(
            context={"tool": tool_name, "params": arguments, "agent": agent_name},
            level=PolicyLevel.L2_RUNTIME,
        )
        failures = [r for r in policy_results if not r.passed and r.blocking]
        if failures:
            return {
                "success": False,
                "error": f"Policy blocked: {failures[0].policy_name}: {failures[0].detail}",
                "policy_results": [{"name": r.policy_name, "passed": r.passed, "detail": r.detail} for r in policy_results],
                "tool_id": tool_name,
            }

    # 3. Execute
    result = await tool_execute(tool_name, arguments, caller=agent_name)

    # 4. Record to ToolMemory (fire-and-forget)
    try:
        from ..memory.tool_memory import record as mem_record
        mem_record(
            tool=tool_name,
            success=result.get("success", False),
            duration_ms=result.get("duration_ms", 0),
        )
    except ImportError:
        pass

    return result


async def call_governed_action(
    action_type: str,
    account_name: str = "",
    params: dict | None = None,
    agent_name: str = "",
) -> dict:
    """Bridge to ActionRegistry for governed actions.

    Actions defined in ontology/config.py go through the full
    ActionRegistry pipeline (preconditions -> handler -> QA hooks -> rollback).
    """
    if not bypass_policies:
        eval_result = await evaluate_policies(
            context={"action": action_type, "params": params, "agent": agent_name},
            level=PolicyLevel.L3_GOVERNANCE,
        )
        blocking = [r for r in eval_result if not r.passed and r.blocking]
        if blocking:
            return {
                "success": False,
                "action_type": action_type,
                "error": f"Governance policy blocked: {blocking[0].policy_name}: {blocking[0].detail}",
                "policy_results": [{"name": r.policy_name, "passed": r.passed} for r in eval_result],
            }

    action = await registry_execute(
        action_type=action_type,
        account_name=account_name,
        params=params,
    )
    return {
        "success": action.status == "completed",
        "action_type": action_type,
        "status": action.status,
        "error": action.error,
        "action_id": action.action_id,
        "qa_status": action.qa_status,
    }
