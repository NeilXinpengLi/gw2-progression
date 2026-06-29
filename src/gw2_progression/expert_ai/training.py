"""Training dataset pipeline for GW2 Expert AI."""

from __future__ import annotations

import time
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
        "id": str(uuid.uuid4()),
        "dataset_type": dataset_type,
        "version": _dataset_version(dataset_type, graph),
        "created_at": time.time(),
        "examples": [build_training_example({"graph": graph}, chain, decision)],
        "format": {"state": {}, "reasoning_chain": [], "decision": {}, "label": {}},
    }


class TrainingPipeline:
    """Deterministic ETL -> simulation -> labeling -> dataset -> train loop."""

    def __init__(self, system: Any) -> None:
        self.system = system

    def run(self, body: dict[str, Any]) -> dict[str, Any]:
        graph = self._etl_graph(body)
        simulation = self._simulate(body)
        reasoning = self._reasoning_graph(graph, body)
        label = self._label(reasoning, body)
        dataset = self._version_dataset(graph, reasoning, label, body.get("dataset_type", "full_production"))
        train = self.system.scheduler.trainer.train(dataset, model_type=body.get("model_type", "expert_reasoner"))
        feedback = self.system.feedback.observe({
            "decision": label["decision"]["decision"],
            "outcome": "success" if train["artifact"]["status"] == "trained" else "review",
            "risk": label["risk_score"],
            "dataset_version": dataset["version"],
        })
        return {
            "run_id": train["artifact"]["id"],
            "status": "completed" if train["artifact"]["status"] == "trained" else train["artifact"]["status"],
            "etl": {"node_count": len(graph.get("nodes", [])), "edge_count": len(graph.get("edges", []))},
            "simulation": simulation,
            "reasoning_graph": reasoning,
            "label": label,
            "dataset": dataset,
            "model": train["artifact"],
            "metrics": train["metrics"],
            "feedback": feedback,
        }

    def _etl_graph(self, body: dict[str, Any]) -> dict[str, Any]:
        graph = body.get("graph") or body.get("snapshot", {}).get("graph")
        if graph:
            return graph
        return self.system.runtime.graph.to_dict()

    def _simulate(self, body: dict[str, Any]) -> dict[str, Any]:
        steps = body.get("simulation_steps", [])
        transitions = [self.system.runtime.simulate_step(step) for step in steps]
        if not steps:
            transitions.append(self.system.runtime.simulate_step({"type": "noop"}))
        return {"transition_count": len(transitions), "transitions": transitions}

    def _reasoning_graph(self, graph: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        start = body.get("start") or (graph.get("nodes", [{}])[0].get("id") if graph.get("nodes") else None)
        goal = body.get("goal")
        reasoning = self.system.reasoning.analyze(start=start, goal=goal, depth=int(body.get("depth", 2))) if start else {"reasoning_chain": [], "decision": "REVIEW"}
        return {"graph": graph, "reasoning": reasoning, "chain": reasoning.get("reasoning_chain", [])}

    def _label(self, reasoning: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        chain_length = len(reasoning.get("chain", []))
        risk_score = float(body.get("risk_score", 0.2 if chain_length else 0.7))
        decision = self.system.evaluate_decision({
            "decision_type": "approve_recommendation",
            "factors": [
                {"name": "reasoning_chain", "value": min(chain_length / 3, 1), "weight": 0.6, "impact": "positive"},
                {"name": "risk", "value": risk_score, "weight": 0.4, "impact": "negative" if risk_score >= 0.7 else "positive"},
            ],
        })
        return {"decision": decision, "risk_score": risk_score, "chain_length": chain_length}

    def _version_dataset(self, graph: dict[str, Any], reasoning: dict[str, Any], label: dict[str, Any], dataset_type: str) -> dict[str, Any]:
        dataset = build_dataset({"graph": graph}, dataset_type=dataset_type)
        dataset["examples"][0]["reasoning_chain"] = reasoning.get("chain", [])
        dataset["examples"][0]["decision"] = label["decision"]
        dataset["examples"][0]["label"] = {"quality": "bors_labeled", "risk_score": label["risk_score"]}
        dataset["version"] = _dataset_version(dataset_type, {"graph": graph, "label": label})
        return dataset

def _dataset_version(dataset_type: str, graph: dict[str, Any]) -> str:
    node_count = len(graph.get("nodes", graph.get("graph", {}).get("nodes", [])))
    edge_count = len(graph.get("edges", graph.get("graph", {}).get("edges", [])))
    return f"{dataset_type}-n{node_count}-e{edge_count}"
