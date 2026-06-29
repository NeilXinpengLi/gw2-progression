from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CausalChain:
    """A causal explanation chain: A → B → C."""
    chain_id: str
    chain: list[str]
    confidence: float
    evidence: list[str] = field(default_factory=list)


@dataclass
class CounterfactualResult:
    """Result of a counterfactual query: what if X instead of Y?"""
    question: str
    actual_outcome: dict[str, Any]
    counterfactual_outcome: dict[str, Any]
    delta: dict[str, float]
    confidence: float


class CausalReasoningLayer:
    """Simulated LLM causal reasoning layer.

    Provides:
      - Causal chain inference from graph structure
      - Counterfactual simulation (what-if analysis)
      - Explanation generation from causal paths
      - Confidence-weighted reasoning

    This is a rule-based simulation of LLM causal reasoning.
    A real LLM integration would replace the rule engine with
    transformer-based causal inference.
    """

    def __init__(self) -> None:
        self.causal_chains: dict[str, CausalChain] = {}

    def infer_causal_chain(
        self,
        graph_data: dict[str, Any],
        target_node: str,
        max_depth: int = 3,
    ) -> list[CausalChain]:
        """Infer causal chains leading to a target node from the graph.

        Uses graph edges to trace causal paths: A → B → C → target.
        """
        nodes = graph_data.get("nodes", {})
        edges = graph_data.get("edges", [])

        def reverse_trace(current: str, depth: int, visited: set[str]) -> list[list[str]]:
            if depth >= max_depth:
                return [[current]]
            chains: list[list[str]] = []
            for edge in edges:
                if edge.get("target") == current:
                    src = edge.get("source", "")
                    if src and src not in visited:
                        sub_chains = reverse_trace(src, depth + 1, visited | {src})
                        for chain in sub_chains:
                            chains.append(chain + [current])
            if not chains:
                chains.append([current])
            return chains

        raw_chains = reverse_trace(target_node, 0, {target_node})
        results: list[CausalChain] = []
        for i, chain_nodes in enumerate(raw_chains):
            confidence = self._estimate_chain_confidence(chain_nodes, edges)
            evidence = self._generate_evidence(chain_nodes, nodes, edges)
            chain = CausalChain(
                chain_id=f"causal_{target_node}_{i}",
                chain=chain_nodes,
                confidence=round(confidence, 3),
                evidence=evidence,
            )
            results.append(chain)
            self.causal_chains[chain.chain_id] = chain

        results.sort(key=lambda c: -c.confidence)
        return results

    def _estimate_chain_confidence(self, chain_nodes: list[str], edges: list[dict[str, Any]]) -> float:
        """Estimate confidence in a causal chain from edge strengths."""
        if len(chain_nodes) < 2:
            return 0.5
        conf = 1.0
        for i in range(len(chain_nodes) - 1):
            found = False
            for edge in edges:
                if edge.get("source") == chain_nodes[i] and edge.get("target") == chain_nodes[i + 1]:
                    conf *= abs(edge.get("strength", 1.0))
                    found = True
                    break
            if not found:
                conf *= 0.5
        return conf

    def _generate_evidence(self, chain_nodes: list[str], nodes: dict[str, Any], edges: list[dict[str, Any]]) -> list[str]:
        evidence = []
        for i in range(len(chain_nodes) - 1):
            src = chain_nodes[i]
            tgt = chain_nodes[i + 1]
            src_type = nodes.get(src, {}).get("type", "node")
            tgt_type = nodes.get(tgt, {}).get("type", "node")
            for edge in edges:
                if edge.get("source") == src and edge.get("target") == tgt:
                    rel = edge.get("relation", "influences")
                    evidence.append(f"{src} ({src_type}) --[{rel}]--> {tgt} ({tgt_type})")
                    break
        return evidence

    def counterfactual(
        self,
        original_state: dict[str, Any],
        original_action: dict[str, Any],
        alternative_action: dict[str, Any],
        simulator: Any,
        num_samples: int = 5,
    ) -> CounterfactualResult:
        """What if the player chose alternative_action instead of original_action?"""
        actual_outcomes: list[dict[str, Any]] = []
        counterfactual_outcomes: list[dict[str, Any]] = []

        for _ in range(num_samples):
            actual = simulator(dict(original_state), dict(original_action))
            cf = simulator(dict(original_state), dict(alternative_action))
            actual_outcomes.append(actual)
            counterfactual_outcomes.append(cf)

        avg_actual = self._average_states(actual_outcomes)
        avg_cf = self._average_states(counterfactual_outcomes)

        delta: dict[str, float] = {}
        for key in ("gold",):
            if key in avg_actual and key in avg_cf:
                delta[key] = round(float(avg_cf.get(key, 0)) - float(avg_actual.get(key, 0)), 2)

        for key in ("inventory_size", "achievement_count"):
            a_val = len(avg_actual.get("inventory", {})) if key == "inventory_size" else len(avg_actual.get("achievements", []))
            c_val = len(avg_cf.get("inventory", {})) if key == "inventory_size" else len(avg_cf.get("achievements", []))
            delta[key] = float(c_val - a_val)

        return CounterfactualResult(
            question=f"What if {alternative_action.get('type')}({alternative_action.get('item_id', '')}) instead of {original_action.get('type')}({original_action.get('item_id', '')})?",
            actual_outcome=avg_actual,
            counterfactual_outcome=avg_cf,
            delta=delta,
            confidence=0.7,
        )

    def _average_states(self, states: list[dict[str, Any]]) -> dict[str, Any]:
        if not states:
            return {}
        avg: dict[str, Any] = {}
        gold_vals = [s.get("gold", 0) for s in states if isinstance(s.get("gold", 0), (int, float))]
        if gold_vals:
            avg["gold"] = sum(gold_vals) / len(gold_vals)
        inv_count = [len(s.get("inventory", {}) or {}) for s in states]
        if inv_count:
            avg["inventory"] = {"_avg_count": sum(inv_count) / len(inv_count)}
        ach_count = [len(s.get("achievements", []) or []) for s in states]
        if ach_count:
            avg["achievements"] = ["_avg_" + str(sum(ach_count) / len(ach_count))]
        return avg

    def explain(self, chain_id: str) -> str:
        """Generate a human-readable explanation from a causal chain."""
        chain = self.causal_chains.get(chain_id)
        if not chain:
            return f"Unknown chain: {chain_id}"

        lines = [f"Causal Chain (confidence: {chain.confidence:.1%})"]
        for i, node in enumerate(chain.chain):
            prefix = "  " * i + ("└─ " if i == len(chain.chain) - 1 else "├─ ")
            lines.append(f"{prefix}{node}")
        if chain.evidence:
            lines.append("\nEvidence:")
            for ev in chain.evidence:
                lines.append(f"  • {ev}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "causal_chain_count": len(self.causal_chains),
            "chains": [
                {
                    "chain_id": c.chain_id,
                    "chain": c.chain,
                    "confidence": c.confidence,
                }
                for c in self.causal_chains.values()
            ],
        }
