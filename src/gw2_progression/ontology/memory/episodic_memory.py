"""EpisodicMemory — agent action pattern detection."""

import time
from collections import defaultdict
from typing import Any

_episodes: list[dict] = []


def record(agent: str, action: str, success: bool, detail: str = "") -> None:
    _episodes.append({
        "agent": agent,
        "action": action,
        "success": success,
        "detail": detail,
        "timestamp": time.time(),
    })


def get_history(agent: str, limit: int = 100) -> list[dict]:
    relevant = [e for e in _episodes if e["agent"] == agent]
    return relevant[-limit:]


def detect_patterns(agent: str, window: int = 10) -> list[dict]:
    """Detect repeating patterns in the agent's action sequence.

    Returns top patterns as {pattern, count, success_rate, example}.
    """
    history = get_history(agent, limit=200)
    if len(history) < window:
        return []

    sequences: dict[str, list[bool]] = defaultdict(list)
    for i in range(len(history) - window + 1):
        seq_actions = tuple(e["action"] for e in history[i : i + window])
        seq_key = " -> ".join(seq_actions)
        outcomes = [e["success"] for e in history[i : i + window]]
        sequences[seq_key] = outcomes

    patterns = []
    for seq_key, outcomes in sequences.items():
        if len(outcomes) < 2:
            continue
        patterns.append({
            "pattern": seq_key,
            "count": len(outcomes),
            "success_rate": round(sum(outcomes) / len(outcomes), 3),
            "example": seq_key,
        })

    patterns.sort(key=lambda p: (-p["count"], -p["success_rate"]))
    return patterns[:10]


def success_rate(agent: str, action: str | None = None) -> float:
    relevant = [e for e in _episodes if e["agent"] == agent]
    if action:
        relevant = [e for e in relevant if e["action"] == action]
    if not relevant:
        return 0.0
    return sum(1 for e in relevant if e["success"]) / len(relevant)
