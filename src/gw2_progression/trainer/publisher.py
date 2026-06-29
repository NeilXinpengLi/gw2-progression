"""Publishes training events to Redis stream for the trainer worker.

Wired into the Expert AI system: when a training pipeline runs or a decision
is made with an outcome, a structured training event is published.

Usage (inside ExpertAISystem):
  from gw2_progression.trainer.publisher import publish_training_event
  publish_training_event(system, event)
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

_HAS_REDIS = False
_redis_client = None


def _get_redis():
    global _redis_client, _HAS_REDIS
    if _redis_client is None:
        url = os.environ.get("EXPERT_AI_REDIS_URL", "")
        if url:
            try:
                import redis as r
                _redis_client = r.Redis.from_url(url)
                _redis_client.ping()
                _HAS_REDIS = True
            except Exception:
                _redis_client = None
    return _redis_client if _HAS_REDIS else None


def publish_training_event(event: dict[str, Any], stream: str = "training:events") -> bool:
    """Publish a structured training event to Redis stream."""
    client = _get_redis()
    if not client:
        return False
    try:
        client.xadd(stream, {"payload": json.dumps(event, default=str)}, maxlen=10000)
        return True
    except Exception:
        return False


def publish_from_training_pipeline(result: dict[str, Any], system: Any = None) -> bool:
    """Publish training pipeline result as a training event."""
    event = {
        "id": result.get("run_id", str(time.time())),
        "state": {"nodes": result.get("etl", {}).get("node_count", 0), "edges": result.get("etl", {}).get("edge_count", 0)},
        "decision": result.get("label", {}).get("decision", {"decision": "REVIEW"}),
        "outcome": {"success": result.get("status") == "completed", "quality": result.get("metrics", {}).get("estimated_quality", 0)},
        "factors": [
            {"name": "quality", "value": result.get("metrics", {}).get("estimated_quality", 0), "weight": 0.5},
            {"name": "coverage", "value": result.get("metrics", {}).get("label_coverage", 0), "weight": 0.3},
            {"name": "samples", "value": result.get("metrics", {}).get("example_count", 1), "weight": 0.2},
        ],
        "agent_type": "expert_reasoner",
        "timestamp": time.time(),
    }
    return publish_training_event(event)


def publish_from_decision(name: str, decision: dict[str, Any], outcome: dict[str, Any]) -> bool:
    """Publish a decision+outcome as a training event."""
    event = {
        "id": f"{name}-{int(time.time())}",
        "decision": decision,
        "outcome": outcome,
        "factors": decision.get("factors", []),
        "agent_type": "bors_decision_v1",
        "timestamp": time.time(),
    }
    return publish_training_event(event)
