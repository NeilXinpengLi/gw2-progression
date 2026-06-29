from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProbabilisticNode:
    id: str
    node_type: str
    attributes: dict[str, Any] = field(default_factory=dict)
    exists_probability: float = 1.0


@dataclass
class ProbabilisticEdge:
    source: str
    target: str
    relation: str
    probability: float = 1.0
    strength: float = 1.0
    uncertainty: float = 0.0


class ProbabilisticDGSK:
    """Probabilistic DGSK — graph with uncertainty weights.

    Instead of deterministic edges (exists/doesn't exist), each edge has:
      - probability: P(edge exists in the real world)
      - strength: expected weight if edge exists
      - uncertainty: variance of the edge weight

    This enables probabilistic graph sampling for multi-world simulation.
    """

    def __init__(self, default_uncertainty: float = 0.1) -> None:
        self.nodes: dict[str, ProbabilisticNode] = {}
        self.edges: list[ProbabilisticEdge] = []
        self.default_uncertainty = default_uncertainty

    def add_node(self, node_id: str, node_type: str, attributes: dict[str, Any] | None = None, exists_probability: float = 1.0) -> ProbabilisticNode:
        node = ProbabilisticNode(
            id=node_id,
            node_type=node_type,
            attributes=attributes or {},
            exists_probability=exists_probability,
        )
        self.nodes[node_id] = node
        return node

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        probability: float = 1.0,
        strength: float = 1.0,
        uncertainty: float | None = None,
    ) -> ProbabilisticEdge:
        edge = ProbabilisticEdge(
            source=source,
            target=target,
            relation=relation,
            probability=probability,
            strength=strength,
            uncertainty=uncertainty if uncertainty is not None else self.default_uncertainty,
        )
        self.edges.append(edge)
        return edge

    def get_edge(self, source: str, target: str, relation: str) -> ProbabilisticEdge | None:
        for e in self.edges:
            if e.source == source and e.target == target and e.relation == relation:
                return e
        return None

    def get_edges(self, node_id: str) -> list[ProbabilisticEdge]:
        return [e for e in self.edges if e.source == node_id or e.target == node_id]

    def outgoing_edges(self, source: str) -> list[ProbabilisticEdge]:
        return [e for e in self.edges if e.source == source]

    def incoming_edges(self, target: str) -> list[ProbabilisticEdge]:
        return [e for e in self.edges if e.target == target]

    # ─── Probability Operations ─────────────────────────────────────

    def sample_graph(self, rng: random.Random | None = None) -> dict[str, Any]:
        """Sample a deterministic graph from the probabilistic distribution."""
        rng = rng or random.Random()
        sampled: dict[str, Any] = {
            "nodes": {},
            "edges": [],
        }
        for nid, node in self.nodes.items():
            if rng.random() < node.exists_probability:
                sampled["nodes"][nid] = {
                    "type": node.node_type,
                    "attributes": dict(node.attributes),
                }
        for edge in self.edges:
            if edge.source in sampled["nodes"] and edge.target in sampled["nodes"]:
                if rng.random() < edge.probability:
                    noise = rng.gauss(0, edge.uncertainty)
                    effective_strength = max(0.0, edge.strength + noise)
                    sampled["edges"].append({
                        "source": edge.source,
                        "target": edge.target,
                        "relation": edge.relation,
                        "strength": round(effective_strength, 4),
                    })
        return sampled

    def edge_entropy(self) -> float:
        """Shannon entropy across all edge probabilities — higher = more uncertain."""
        if not self.edges:
            return 0.0
        h = 0.0
        for e in self.edges:
            p = e.probability
            p = max(1e-10, min(1 - 1e-10, p))
            h -= p * math.log2(p) + (1 - p) * math.log2(1 - p)
        return h / len(self.edges)

    def graph_uncertainty(self) -> float:
        if not self.edges:
            return 0.0
        return sum(e.uncertainty for e in self.edges) / len(self.edges)

    def merge_with_cognition_graph(self, cognition_graph: Any) -> None:
        """Import edges from the deterministic CognitionGraph as probability=1 edges."""
        data = cognition_graph.to_dict() if hasattr(cognition_graph, 'to_dict') else {}

        for edge in data.get("edges", []):
            src = edge.get("source_id") or edge.get("source", "")
            tgt = edge.get("target_id") or edge.get("target", "")
            rel = edge.get("edge_type") or edge.get("relation") or edge.get("type", "unknown")
            w = edge.get("weight", 1.0)
            self.add_edge(
                source=src,
                target=tgt,
                relation=rel,
                probability=1.0,
                strength=w,
                uncertainty=self.default_uncertainty,
            )

        for node_id, node_data in data.get("nodes", {}).items():
            if isinstance(node_data, dict):
                nid = node_data.get("node_id", node_id)
                nt = node_data.get("node_type", "unknown")
                attrs = node_data.get("properties", {})
                if nid and nid not in self.nodes:
                    self.add_node(nid, nt, dict(attrs))
            elif isinstance(node_data, str):
                pass

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "graph_uncertainty": round(self.graph_uncertainty(), 4),
            "edge_entropy": round(self.edge_entropy(), 4),
            "nodes": {
                nid: {
                    "type": n.node_type,
                    "exists_p": round(n.exists_probability, 3),
                }
                for nid, n in self.nodes.items()
            },
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "relation": e.relation,
                    "p": round(e.probability, 3),
                    "strength": round(e.strength, 3),
                    "uncertainty": round(e.uncertainty, 3),
                }
                for e in self.edges
            ],
        }
