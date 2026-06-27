"""ToolMemory — tool call history and success rate tracking."""

import time
from collections import defaultdict
from typing import Any

_records: list[dict] = []


def record(tool: str, success: bool, duration_ms: float = 0) -> None:
    _records.append({
        "tool": tool,
        "success": success,
        "duration_ms": duration_ms,
        "timestamp": time.time(),
    })


def success_rate(tool: str, window_minutes: float = 0) -> float:
    """Success rate for a tool. Optionally limited to a time window."""
    relevant = _filter(tool=tool, window_minutes=window_minutes)
    if not relevant:
        return 0.0
    successes = sum(1 for r in relevant if r["success"])
    return successes / len(relevant)


def call_count(tool: str, window_minutes: float = 0) -> int:
    return len(_filter(tool=tool, window_minutes=window_minutes))


def average_duration(tool: str, window_minutes: float = 0) -> float:
    relevant = _filter(tool=tool, window_minutes=window_minutes)
    if not relevant:
        return 0.0
    return sum(r["duration_ms"] for r in relevant) / len(relevant)


def stats(tool: str | None = None) -> dict[str, Any]:
    """Aggregate stats per tool or for all tools."""
    if tool:
        return {
            "tool": tool,
            "call_count": call_count(tool),
            "success_rate": round(success_rate(tool), 3),
            "avg_duration_ms": round(average_duration(tool), 1),
        }

    tools = set(r["tool"] for r in _records)
    return {t: stats(t) for t in sorted(tools)}


def _filter(tool: str | None = None, window_minutes: float = 0) -> list[dict]:
    filtered = _records
    if tool:
        filtered = [r for r in filtered if r["tool"] == tool]
    if window_minutes > 0:
        cutoff = time.time() - window_minutes * 60
        filtered = [r for r in filtered if r["timestamp"] >= cutoff]
    return filtered
