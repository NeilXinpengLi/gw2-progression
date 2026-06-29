"""Collates raw training events into feature vectors and labels for sklearn training.

Transforms the DGSK graph state + BORS decision factors + outcome labels
into structured numpy arrays suitable for statistical learning.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np


def extract_features(event: dict[str, Any]) -> list[float]:
    """Extract a flat feature vector from a training event.

    Input event format (published by Expert AI system):
      {
        "id": "uuid",
        "state": {"nodes": [...], "edges": [...]},
        "decision": {"decision": "APPROVE"|"REJECT", "score": 0.8, "confidence": 0.7},
        "outcome": {"success": True, "value_delta": 5000},
        "factors": [{"name": "wealth", "value": 0.8, "weight": 0.6}, ...],
        "agent_type": "expert_reasoner",
        "graph_layer": "personal_intelligence",
        "timestamp": 1234567890,
      }
    """
    features: list[float] = []

    state = event.get("state", {})
    nodes = state.get("nodes", [])
    edges = state.get("edges", [])
    features.append(float(len(nodes)))
    features.append(float(len(edges)))

    factors = event.get("factors", [])
    factor_values = {f.get("name", f"f{i}"): float(f.get("value", 0)) for i, f in enumerate(factors)}
    features.append(factor_values.get("liquid_wealth", 0.0))
    features.append(factor_values.get("asset_risk", 0.0))
    features.append(factor_values.get("market_volatility", 0.0))
    features.append(factor_values.get("goal_progress", 0.0))
    features.append(factor_values.get("crafting_complexity", 0.0))
    features.append(factor_values.get("seasonal_velocity", 0.0))

    decision = event.get("decision", {})
    features.append(float(decision.get("score", 0.5)))
    features.append(float(decision.get("confidence", 0.5)))

    outcome = event.get("outcome", {})
    features.append(float(outcome.get("value_delta", 0)))
    features.append(float(outcome.get("time_saved_hours", 0)))
    features.append(1.0 if outcome.get("success", False) else 0.0)

    return features


def extract_label(event: dict[str, Any]) -> int:
    """Extract numeric label from a training event.

    Returns:
      0 = REJECT / negative outcome
      1 = REVIEW / neutral
      2 = APPROVE / positive outcome
    """
    decision = event.get("decision", {}).get("decision", "REVIEW")
    outcome = event.get("outcome", {})
    success = outcome.get("success", False)

    if decision == "APPROVE" and success:
        return 2
    elif decision == "REJECT":
        return 0
    else:
        return 1


class DatasetCollator:
    """Accumulates training events, collates into numpy arrays for sklearn."""

    def __init__(self, max_samples: int = 10000):
        self.events: list[dict[str, Any]] = []
        self.max_samples = max_samples

    def add_event(self, event: dict[str, Any]) -> int:
        self.events.append(event)
        if len(self.events) > self.max_samples:
            self.events.pop(0)
        return len(self.events)

    def add_events(self, events: list[dict[str, Any]]) -> int:
        for e in events:
            self.add_event(e)
        return len(self.events)

    def collate(self) -> tuple[np.ndarray, np.ndarray]:
        if not self.events:
            return np.empty((0, 13)), np.empty((0,), dtype=int)
        X = np.array([extract_features(e) for e in self.events], dtype=np.float32)
        y = np.array([extract_label(e) for e in self.events], dtype=np.int32)
        return X, y

    def save(self, path: str | Path) -> str:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        X, y = self.collate()
        np.savez(str(path), X=X, y=y, metadata=json.dumps({
            "event_count": len(self.events),
            "label_distribution": {str(k): int(v) for k, v in zip(*np.unique(y, return_counts=True))} if len(y) > 0 else {},
            "created_at": time.time(),
        }))
        return str(path)

    @classmethod
    def load(cls, path: str | Path) -> tuple[np.ndarray, np.ndarray, dict]:
        data = np.load(str(path), allow_pickle=True)
        metadata = json.loads(str(data.get("metadata", b"{}")))
        return data["X"], data["y"], metadata

    @property
    def count(self) -> int:
        return len(self.events)
