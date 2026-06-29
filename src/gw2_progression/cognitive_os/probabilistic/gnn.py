from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class RuleEmbedding:
    """Embedding vector for a graph rule/relation."""
    source_type: str
    target_type: str
    relation: str
    embedding: list[float]
    strength: float
    confidence: float


@dataclass
class InducedRule:
    """A rule induced from graph patterns."""
    antecedent: str
    consequent: str
    relation: str
    confidence: float
    support: int
    lift: float


class RuleGNN:
    """Lightweight GNN for rule induction from the graph structure.

    Uses a simplified message-passing scheme to produce:
      - Node embeddings (structural + attributive)
      - Edge strength predictions
      - Induced rules (frequent subgraph patterns)

    This is NOT a full GNN implementation — it uses statistical
    co-occurrence and structural features to approximate GNN behavior
    without requiring a deep learning framework.
    """

    def __init__(self, embedding_dim: int = 8, min_support: int = 2) -> None:
        self.embedding_dim = embedding_dim
        self.min_support = min_support
        self._embeddings: dict[str, RuleEmbedding] = {}
        self._node_embeddings: dict[str, list[float]] = {}

    def compute_node_embeddings(self, graph: dict[str, Any]) -> dict[str, list[float]]:
        """Compute structural embeddings for each node.

        Uses degree features and neighbor-type signatures as embedding.
        """
        nodes = graph.get("nodes", {})
        edges = graph.get("edges", [])
        d = self.embedding_dim

        embeddings: dict[str, list[float]] = {}
        for nid, ndata in nodes.items():
            ntype = ndata.get("type", "unknown")
            out_edges = [e for e in edges if e.get("source") == nid]
            in_edges = [e for e in edges if e.get("target") == nid]

            out_types = [e.get("relation", "") for e in out_edges]
            in_types = [e.get("relation", "") for e in in_edges]

            emb = [0.0] * d
            degree = len(out_edges) + len(in_edges)
            emb[0] = min(1.0, degree / 10.0)
            emb[1] = 1.0 if out_edges else 0.0
            emb[2] = 1.0 if in_edges else 0.0
            emb[3] = min(1.0, len(out_types) / 5.0) if out_types else 0.0
            emb[4] = min(1.0, len(in_types) / 5.0) if in_types else 0.0

            degree_centrality = degree / max(len(nodes), 1)
            emb[5] = degree_centrality

            if edge_weights := [abs(e.get("strength", 1.0)) for e in out_edges + in_edges]:
                emb[6] = min(1.0, sum(edge_weights) / max(len(edge_weights), 1))
            else:
                emb[6] = 0.0

            emb[7] = hash(ntype) % 100 / 100.0 if d > 7 else 0.0

            embeddings[nid] = emb

        self._node_embeddings = embeddings
        return embeddings

    def message_passing(self, embeddings: dict[str, list[float]], edges: list[dict[str, Any]], steps: int = 2) -> dict[str, list[float]]:
        """Simplified message passing: average neighbor embeddings."""
        result: dict[str, list[float]] = {k: list(v) for k, v in embeddings.items()}

        for _ in range(steps):
            new_emb: dict[str, list[float]] = {k: list(v) for k, v in result.items()}
            for edge in edges:
                src = edge.get("source", "")
                tgt = edge.get("target", "")
                strength = abs(edge.get("strength", 1.0))
                if src in result and tgt in result:
                    d = len(result[src])
                    for i in range(d):
                        new_emb[src][i] += result[tgt][i] * strength * 0.1
                        new_emb[tgt][i] += result[src][i] * strength * 0.1

            for nid in result:
                norm = math.sqrt(sum(v * v for v in new_emb[nid])) or 1.0
                new_emb[nid] = [v / norm for v in new_emb[nid]]
            result = new_emb

        self._node_embeddings = dict(result)
        return result

    def predict_relation_strength(self, source_id: str, target_id: str) -> float:
        """Predict the strength of a relation between two nodes from embeddings."""
        emb_s = self._node_embeddings.get(source_id, [0.0])
        emb_t = self._node_embeddings.get(target_id, [0.0])
        if not emb_s or not emb_t:
            return 0.0
        dot = sum(a * b for a, b in zip(emb_s, emb_t))
        n1 = math.sqrt(sum(v * v for v in emb_s)) or 1.0
        n2 = math.sqrt(sum(v * v for v in emb_t)) or 1.0
        return max(0.0, min(1.0, dot / (n1 * n2)))

    def find_similar_nodes(self, node_id: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Find structurally similar nodes using embedding cosine similarity."""
        query = self._node_embeddings.get(node_id)
        if not query:
            return []
        scores: list[tuple[str, float]] = []
        for nid, emb in self._node_embeddings.items():
            if nid == node_id:
                continue
            dot = sum(a * b for a, b in zip(query, emb))
            n1 = math.sqrt(sum(v * v for v in query)) or 1.0
            n2 = math.sqrt(sum(v * v for v in emb)) or 1.0
            score = dot / (n1 * n2)
            scores.append((nid, score))
        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]

    def induce_rules(self, graph: dict[str, Any]) -> list[InducedRule]:
        """Induce rules from graph patterns using co-occurrence statistics.

        For each pair of relation types, compute how often they co-occur
        on the same node (confidence, support, lift).
        """
        edges = graph.get("edges", [])
        nodes = graph.get("nodes", {})

        relation_pairs: dict[tuple[str, str], int] = {}
        relation_counts: dict[str, int] = {}
        total_nodes_with_edges = 0

        for nid in nodes:
            n_edges = [e for e in edges if e.get("source") == nid or e.get("target") == nid]
            n_relations = [e.get("relation", "") for e in n_edges]
            if len(n_relations) >= 2:
                total_nodes_with_edges += 1
                for i in range(len(n_relations)):
                    for j in range(i + 1, len(n_relations)):
                        key = tuple(sorted([n_relations[i], n_relations[j]]))
                        relation_pairs[key] = relation_pairs.get(key, 0) + 1
                for r in n_relations:
                    relation_counts[r] = relation_counts.get(r, 0) + 1

        rules: list[InducedRule] = []
        for (r1, r2), count in relation_pairs.items():
            if count < self.min_support:
                continue
            c1 = relation_counts.get(r1, 1)
            c2 = relation_counts.get(r2, 1)
            confidence_12 = count / max(c1, 1)
            confidence_21 = count / max(c2, 1)
            expected = (c1 / max(total_nodes_with_edges, 1)) * (c2 / max(total_nodes_with_edges, 1))
            lift = (count / max(total_nodes_with_edges, 1)) / max(expected, 0.001)

            rules.append(InducedRule(
                antecedent=r1,
                consequent=r2,
                relation="co_occurs_with",
                confidence=max(confidence_12, confidence_21),
                support=count,
                lift=round(lift, 3),
            ))

        rules.sort(key=lambda r: -r.confidence)
        return rules

    def forward(self, graph: dict[str, Any], message_passing_steps: int = 2) -> dict[str, Any]:
        """Full forward pass: embeddings → message passing → rule induction."""
        embeddings = self.compute_node_embeddings(graph)
        embeddings = self.message_passing(embeddings, graph.get("edges", []), steps=message_passing_steps)
        rules = self.induce_rules(graph)

        edge_predictions: list[dict[str, Any]] = []
        nodes = graph.get("nodes", {})
        for src in nodes:
            for tgt in nodes:
                if src < tgt:
                    strength = self.predict_relation_strength(src, tgt)
                    if strength > 0.3:
                        edge_predictions.append({
                            "source": src,
                            "target": tgt,
                            "predicted_strength": round(strength, 4),
                        })

        return {
            "node_embeddings": {k: [round(v, 4) for v in emb] for k, emb in embeddings.items()},
            "induced_rules": [
                {
                    "antecedent": r.antecedent,
                    "consequent": r.consequent,
                    "confidence": round(r.confidence, 4),
                    "support": r.support,
                    "lift": r.lift,
                }
                for r in rules
            ],
            "predicted_edges": sorted(edge_predictions, key=lambda x: -x["predicted_strength"])[:10],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "embedding_dim": self.embedding_dim,
            "min_support": self.min_support,
            "node_embedding_count": len(self._node_embeddings),
        }
