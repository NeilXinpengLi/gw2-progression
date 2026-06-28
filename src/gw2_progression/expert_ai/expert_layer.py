"""Read-only expert reasoning layer for GW2 Expert AI."""

from __future__ import annotations

from typing import Any


class LLMExpertLayer:
    """Deterministic provider-compatible expert layer.

    The class intentionally does not mutate runtime state. A future hosted LLM
    provider can replace the deterministic text generation behind this facade.
    """

    def explain_decision(self, decision: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        factors = decision.get("factors", [])
        strongest = sorted(factors, key=lambda factor: abs(float(factor.get("value", 0)) * float(factor.get("weight", 1))), reverse=True)[:3]
        explanation = {
            "decision": decision.get("decision", "REVIEW"),
            "summary": decision.get("reason", "Decision requires expert review."),
            "key_factors": [factor.get("name", "factor") for factor in strongest],
            "context_keys": sorted(context.keys()),
        }
        return {"provider": "deterministic_expert", "mode": "read_only", "explanation": explanation}

    def generate_counterfactuals(self, decision: dict[str, Any], limit: int = 3) -> dict[str, Any]:
        factors = decision.get("factors", [])[:limit]
        counterfactuals = []
        for factor in factors:
            impact = factor.get("impact", "")
            direction = "reduce" if impact == "negative" else "increase"
            counterfactuals.append({
                "factor": factor.get("name", "factor"),
                "change": f"{direction} signal strength",
                "expected_effect": "decision confidence improves",
            })
        return {"counterfactuals": counterfactuals, "mutates_state": False}

    def interpret_graph(self, graph: dict[str, Any]) -> dict[str, Any]:
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        relation_counts: dict[str, int] = {}
        for edge in edges:
            relation_counts[edge.get("relation_type", "related_to")] = relation_counts.get(edge.get("relation_type", "related_to"), 0) + 1
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "relation_counts": relation_counts,
            "summary": f"Graph contains {len(nodes)} entities and {len(edges)} relations.",
            "mutates_state": False,
        }

    def simulate_expert_thinking(self, prompt: str, graph: dict[str, Any] | None = None) -> dict[str, Any]:
        graph_summary = self.interpret_graph(graph or {"nodes": [], "edges": []})
        return {
            "prompt": prompt,
            "reasoning_style": "guild_wars_2_progression_expert",
            "steps": [
                "Identify account state and goal constraints.",
                "Check wealth, liquidity, build readiness, and blocking risks.",
                "Prefer reversible, high-confidence progression actions.",
            ],
            "graph_summary": graph_summary,
            "mutates_state": False,
        }
