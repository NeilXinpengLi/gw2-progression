"""Training dataset pipeline for GW2 Expert AI."""

from __future__ import annotations

import uuid
from typing import Any


def build_training_example(state: dict[str, Any], reasoning_chain: list[dict[str, Any]], decision: dict[str, Any], label: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "state": state,
        "reasoning_chain": reasoning_chain,
        "decision": decision,
        "label": label or {"quality": "unlabeled"},
    }


def build_dataset(snapshot: dict[str, Any], dataset_type: str = "reasoning_graph") -> dict[str, Any]:
    graph = snapshot.get("graph", snapshot)
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    chain = [{"from": e.get("source"), "relation": e.get("relation_type"), "to": e.get("target")} for e in edges[:20]]
    decision = {
        "type": "training_label_candidate",
        "dataset_type": dataset_type,
        "status": "REVIEW",
        "node_count": len(nodes),
        "edge_count": len(edges),
    }
    return {
        "dataset_type": dataset_type,
        "examples": [build_training_example({"graph": graph}, chain, decision)],
        "format": {"state": {}, "reasoning_chain": [], "decision": {}, "label": {}},
    }

