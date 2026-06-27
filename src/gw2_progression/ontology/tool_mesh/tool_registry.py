"""ToolRegistry — register and execute tools with input schema validation."""

import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger("gw2.ontology.tool")

_tools: dict[str, dict] = {}
_execution_history: list[dict] = []


@dataclass
class ToolDef:
    tool_id: str
    description: str = ""
    input_schema: dict | None = None
    handler: Callable[..., Any] | None = None
    timeout_seconds: float = 30.0
    require_auth: bool = True
    tags: list[str] = field(default_factory=list)


def register(tool: ToolDef) -> None:
    _tools[tool.tool_id] = {
        "def": tool,
        "call_count": 0,
        "success_count": 0,
        "last_call_at": None,
    }


def get(tool_id: str) -> ToolDef | None:
    entry = _tools.get(tool_id)
    return entry["def"] if entry else None


def list_tools(tag: str | None = None) -> list[ToolDef]:
    if tag:
        return [e["def"] for e in _tools.values() if tag in e["def"].tags]
    return [e["def"] for e in _tools.values()]


async def execute(tool_id: str, payload: dict | None = None, caller: str = "") -> dict:
    """Execute a registered tool with input validation and history tracking."""
    entry = _tools.get(tool_id)
    if not entry:
        raise ValueError(f"Unknown tool: {tool_id}")

    tool = entry["def"]
    entry["call_count"] += 1
    entry["last_call_at"] = datetime.now(timezone.utc).isoformat()
    payload = payload or {}

    # Input validation
    if tool.input_schema:
        errors = _validate(payload, tool.input_schema)
        if errors:
            raise ValueError(f"Tool '{tool_id}' input validation failed: {', '.join(errors)}")

    # Execute
    start = datetime.now(timezone.utc)
    try:
        if tool.handler is None:
            raise ValueError(f"Tool '{tool_id}' has no handler registered")
        if inspect.iscoroutinefunction(tool.handler):
            result = await tool.handler(**payload)
        else:
            result = tool.handler(**payload)
        entry["success_count"] += 1
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        _execution_history.append({
            "tool_id": tool_id,
            "caller": caller,
            "success": True,
            "duration_ms": round(duration * 1000),
            "timestamp": start.isoformat(),
        })
        return {"success": True, "result": result, "tool_id": tool_id, "duration_ms": round(duration * 1000)}
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        _execution_history.append({
            "tool_id": tool_id,
            "caller": caller,
            "success": False,
            "error": str(e),
            "duration_ms": round(duration * 1000),
            "timestamp": start.isoformat(),
        })
        logger.error("Tool %s failed: %s", tool_id, e)
        return {"success": False, "error": str(e), "tool_id": tool_id, "duration_ms": round(duration * 1000)}


def history(limit: int = 100) -> list[dict]:
    return _execution_history[-limit:]


def stats() -> dict:
    result = {}
    for tid, entry in _tools.items():
        d = entry["def"]
        result[tid] = {
            "description": d.description,
            "call_count": entry["call_count"],
            "success_count": entry["success_count"],
            "last_call_at": entry["last_call_at"],
            "tags": d.tags,
        }
    return result


def _validate(payload: dict, schema: dict) -> list[str]:
    errors = []
    for key, expected_type in schema.items():
        if key not in payload:
            errors.append(f"missing '{key}'")
            continue
        val = payload[key]
        if expected_type == "string" and not isinstance(val, str):
            errors.append(f"'{key}' must be string, got {type(val).__name__}")
        elif expected_type == "int" and not isinstance(val, int):
            errors.append(f"'{key}' must be int, got {type(val).__name__}")
        elif expected_type == "float" and not isinstance(val, (int, float)):
            errors.append(f"'{key}' must be number, got {type(val).__name__}")
        elif expected_type == "bool" and not isinstance(val, bool):
            errors.append(f"'{key}' must be bool, got {type(val).__name__}")
        elif expected_type == "list" and not isinstance(val, list):
            errors.append(f"'{key}' must be list, got {type(val).__name__}")
        elif expected_type == "dict" and not isinstance(val, dict):
            errors.append(f"'{key}' must be dict, got {type(val).__name__}")
    return errors
