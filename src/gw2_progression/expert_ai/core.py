"""Core DGSK/OOSK/BORS runtime for GW2 Expert AI.

This module provides a deterministic in-process implementation of the staged
training infrastructure. It intentionally keeps LLM-facing behavior read-only:
state mutations go through the runtime and decisions go through BORS.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gw2_progression.bors.business_decision import DecisionEngine, DecisionFactor
from gw2_progression.domain_graph.domain_engine import DomainGraphEngine
from gw2_progression.expert_ai.agents import AgentOrchestrator
from gw2_progression.expert_ai.data_sources import EconomyDataSource, MetaBuildDataSource
from gw2_progression.expert_ai.expert_layer import LLMExpertLayer
from gw2_progression.expert_ai.feedback import MemoryFeedbackLoop
from gw2_progression.expert_ai.observability import ObservabilityHub
from gw2_progression.expert_ai.persistence import ExpertAIPersistence
from gw2_progression.expert_ai.scheduler import TrainingScheduler
from gw2_progression.expert_ai.simulation import SyntheticSimulationEngine


@dataclass
class GraphNode:
    id: str
    type: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    relation_type: str
    weight: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeSnapshot:
    id: str
    entities: dict[str, GraphNode]
    relations: list[GraphEdge]
    created_at: float


class GraphStore:
    """Small deterministic graph store with traversal and dependency helpers."""

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []

    def add_node(self, node: GraphNode) -> GraphNode:
        self.nodes[node.id] = node
        return node

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        if edge.source not in self.nodes:
            self.add_node(GraphNode(id=edge.source, type="unknown"))
        if edge.target not in self.nodes:
            self.add_node(GraphNode(id=edge.target, type="unknown"))
        self.edges.append(edge)
        return edge

    def get_node(self, node_id: str) -> GraphNode | None:
        return self.nodes.get(node_id)

    def search(self, query: str = "", node_type: str | None = None, limit: int = 20) -> list[GraphNode]:
        q = query.lower().strip()
        matches = []
        for node in self.nodes.values():
            if node_type and node.type != node_type:
                continue
            haystack = " ".join([node.id, node.type, str(node.properties)]).lower()
            if not q or q in haystack:
                matches.append(node)
        return matches[:limit]

    def neighbors(self, node_id: str, relation_type: str | None = None) -> list[GraphNode]:
        out = []
        for edge in self.edges:
            if edge.source != node_id:
                continue
            if relation_type and edge.relation_type != relation_type:
                continue
            node = self.nodes.get(edge.target)
            if node:
                out.append(node)
        return out

    def traverse(self, start: str, depth: int = 2) -> dict[str, Any]:
        seen = {start}
        queue = deque([(start, 0)])
        steps = []
        while queue:
            current, level = queue.popleft()
            if level >= depth:
                continue
            for edge in self.edges:
                if edge.source != current:
                    continue
                steps.append({"from": edge.source, "to": edge.target, "relation": edge.relation_type, "depth": level + 1})
                if edge.target not in seen:
                    seen.add(edge.target)
                    queue.append((edge.target, level + 1))
        return {"start": start, "visited": sorted(seen), "steps": steps}

    def shortest_path(self, source: str, target: str, max_depth: int = 6) -> list[str]:
        queue = deque([(source, [source])])
        seen = {source}
        while queue:
            current, path = queue.popleft()
            if current == target:
                return path
            if len(path) > max_depth:
                continue
            for edge in self.edges:
                if edge.source == current and edge.target not in seen:
                    seen.add(edge.target)
                    queue.append((edge.target, [*path, edge.target]))
        return []

    def subgraph(self, node_ids: list[str]) -> dict[str, Any]:
        selected = set(node_ids)
        return {
            "nodes": [node_to_dict(n) for n in self.nodes.values() if n.id in selected],
            "edges": [edge_to_dict(e) for e in self.edges if e.source in selected and e.target in selected],
        }

    def to_dict(self) -> dict[str, Any]:
        return {"nodes": [node_to_dict(n) for n in self.nodes.values()], "edges": [edge_to_dict(e) for e in self.edges]}


class ExpertRuntime:
    """OOSK runtime: all mutations flow through actions with rollback support."""

    def __init__(self) -> None:
        self.graph = GraphStore()
        self.snapshots: dict[str, RuntimeSnapshot] = {}
        self.action_log: list[dict[str, Any]] = []
        self.transition_log: list[dict[str, Any]] = []

    def add_entity(self, entity: dict[str, Any]) -> GraphNode:
        node = GraphNode(id=entity.get("id") or str(uuid.uuid4()), type=entity.get("type", "entity"), properties=entity.get("properties", {}))
        return self.graph.add_node(node)

    def get_entity(self, entity_id: str) -> GraphNode | None:
        return self.graph.get_node(entity_id)

    def add_relation(self, relation: dict[str, Any]) -> GraphEdge:
        edge = GraphEdge(
            source=relation["source"],
            target=relation["target"],
            relation_type=relation.get("relation_type", relation.get("type", "related_to")),
            weight=float(relation.get("weight", 1.0)),
            properties=relation.get("properties", {}),
        )
        return self.graph.add_edge(edge)

    def update_state(self, entity_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        node = self.graph.get_node(entity_id)
        if not node:
            raise ValueError(f"Entity not found: {entity_id}")
        before = dict(node.properties)
        node.properties.update(patch)
        transition = {
            "id": str(uuid.uuid4()),
            "type": "state_update",
            "entity_id": entity_id,
            "before": before,
            "after": dict(node.properties),
            "created_at": time.time(),
        }
        self.transition_log.append(transition)
        return transition

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        action_type = action.get("type", "")
        before = self.snapshot()
        try:
            if action_type == "add_entity":
                result = node_to_dict(self.add_entity(action.get("entity", {})))
            elif action_type == "add_relation":
                result = edge_to_dict(self.add_relation(action.get("relation", {})))
            elif action_type == "update_state":
                result = self.update_state(action["entity_id"], action.get("patch", {}))
            else:
                raise ValueError(f"Unsupported action type: {action_type}")
            record = {"action": action, "status": "completed", "result": result, "rollback_snapshot": before.id}
        except Exception as exc:
            record = {"action": action, "status": "failed", "error": str(exc), "rollback_snapshot": before.id}
        self.action_log.append(record)
        return record

    def simulate_step(self, step: dict[str, Any]) -> dict[str, Any]:
        step_type = step.get("type", "noop")
        if step_type == "noop":
            snapshot = self.snapshot()
            result: dict[str, Any] = {"status": "completed", "result": {"message": "no state change"}}
        elif step_type in {"add_entity", "add_relation", "update_state"}:
            result = self.execute(step)
            snapshot = self.snapshot()
        elif step_type == "batch":
            results = [self.execute(action) for action in step.get("actions", [])]
            snapshot = self.snapshot()
            result = {"status": "completed" if all(r["status"] == "completed" for r in results) else "partial", "result": results}
        else:
            result = {"status": "failed", "error": f"Unsupported simulation step: {step_type}"}
            snapshot = self.snapshot()
        transition = {
            "id": str(uuid.uuid4()),
            "type": "simulation_step",
            "step": step,
            "result": result,
            "snapshot_id": snapshot.id,
            "created_at": time.time(),
        }
        self.transition_log.append(transition)
        return transition

    def trace_history(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.transition_log[-limit:]

    def rollback(self, snapshot_id: str) -> bool:
        snapshot = self.snapshots.get(snapshot_id)
        if not snapshot:
            return False
        self.graph.nodes = {k: GraphNode(v.id, v.type, dict(v.properties)) for k, v in snapshot.entities.items()}
        self.graph.edges = [GraphEdge(e.source, e.target, e.relation_type, e.weight, dict(e.properties)) for e in snapshot.relations]
        return True

    def snapshot(self) -> RuntimeSnapshot:
        sid = str(uuid.uuid4())
        snap = RuntimeSnapshot(
            id=sid,
            entities={k: GraphNode(v.id, v.type, dict(v.properties)) for k, v in self.graph.nodes.items()},
            relations=[GraphEdge(e.source, e.target, e.relation_type, e.weight, dict(e.properties)) for e in self.graph.edges],
            created_at=time.time(),
        )
        self.snapshots[sid] = snap
        return snap

    def state(self) -> dict[str, Any]:
        return {**self.graph.to_dict(), "actions": self.action_log[-50:], "transitions": self.trace_history(), "snapshot_count": len(self.snapshots)}


class ReasoningEngine:
    """Build deterministic causal reasoning chains from graph state."""

    def __init__(self, runtime: ExpertRuntime) -> None:
        self.runtime = runtime

    def analyze(self, start: str | None = None, goal: str | None = None, depth: int = 2) -> dict[str, Any]:
        if start and goal:
            path = self.runtime.graph.shortest_path(start, goal)
            chain = [{"step": i + 1, "node": node_id, "claim": f"{node_id} contributes to {goal}"} for i, node_id in enumerate(path)]
            return {"type": "path_reasoning", "start": start, "goal": goal, "reasoning_chain": chain, "decision": "REVIEW" if path else "REJECT"}
        start_id = start or next(iter(self.runtime.graph.nodes), "")
        trace = self.runtime.graph.traverse(start_id, depth) if start_id else {"steps": []}
        chain = [{"step": i + 1, "claim": f"{s['from']} --{s['relation']}--> {s['to']}", "evidence": s} for i, s in enumerate(trace["steps"])]
        return {"type": "trace_reasoning", "start": start_id, "reasoning_chain": chain, "decision": "REVIEW"}

    def trace(self, node_id: str, depth: int = 3) -> dict[str, Any]:
        return self.runtime.graph.traverse(node_id, depth)


class EconomySimulator:
    """Deterministic market simulator for liquidity, volatility, and forecast."""

    def simulate(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        rows = []
        for item in items:
            item_id = item.get("item_id") or item.get("id")
            price = float(item.get("price", item.get("sell_price", 0)))
            supply = max(float(item.get("supply", 0)), 0)
            demand = max(float(item.get("demand", 0)), 0)
            liquidity = "high" if demand >= supply * 0.7 and demand > 100 else "medium" if demand > 0 else "illiquid"
            pressure = (demand - supply) / max(supply + demand, 1)
            forecast = max(price * (1 + pressure * 0.08), 0)
            rows.append({
                "item_id": item_id,
                "price_forecast": round(forecast, 2),
                "volatility": round(abs(pressure), 3),
                "liquidity_score": {"high": 1.0, "medium": 0.6, "illiquid": 0.0}[liquidity],
                "liquidity": liquidity,
            })
        return {"items": rows, "market_risk": "HIGH" if any(r["volatility"] > 0.6 for r in rows) else "LOW"}


class MetaBuildEngine:
    """Evaluate build readiness against role and gear signals."""

    def analyze_build(self, build: dict[str, Any]) -> dict[str, Any]:
        gear = float(build.get("gear_completion_percent", build.get("gear_score", 0)))
        role = 1.0 if build.get("role") in {"dps", "quickness", "alacrity", "healer", "boon"} else 0.55
        patch = 1.0 if build.get("review_status", "reviewed") == "reviewed" else 0.65
        meta_score = max(0, min((gear / 100) * 0.55 + role * 0.25 + patch * 0.2, 1))
        return {
            "meta_score": round(meta_score, 3),
            "role_gap": "none" if role >= 1 else "role not mapped to supported meta role",
            "raid_viability": "ready" if meta_score >= 0.8 else "review" if meta_score >= 0.55 else "not_ready",
        }


class MultiAgentPlanner:
    """Coordinator for planner/economy/meta/build agent outputs."""

    def generate(self, goals: list[dict[str, Any]], constraints: dict[str, Any] | None = None) -> dict[str, Any]:
        constraints = constraints or {}
        budget = int(constraints.get("budget", 0) or 0)
        steps = []
        for i, goal in enumerate(goals, start=1):
            missing_cost = int(goal.get("missing_cost", goal.get("cost", 0)) or 0)
            priority = goal.get("priority", "normal")
            reward = float(goal.get("progress", 0)) + (0.2 if priority == "high" else 0)
            feasible = budget <= 0 or missing_cost <= budget
            steps.append({
                "step": i,
                "agent": "Coordinator",
                "action": f"Advance {goal.get('name', goal.get('template_id', 'goal'))}",
                "cost_estimate": missing_cost,
                "reward": round(reward, 3),
                "decision": "APPROVE" if feasible else "REVIEW",
                "dependencies": goal.get("dependencies", []),
            })
        steps.sort(key=lambda s: (s["decision"] != "APPROVE", -s["reward"], s["cost_estimate"]))
        return {"plan": steps, "dependency_graph": [{"from": d, "to": s["action"]} for s in steps for d in s["dependencies"]]}


class MemorySystem:
    """Append-only graph/vector/episodic memory facade."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        record = {"id": str(uuid.uuid4()), "created_at": time.time(), **event}
        self.events.append(record)
        return record

    def search(self, query: str = "", memory_type: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        q = query.lower().strip()
        rows = []
        for event in self.events:
            if memory_type and event.get("type") != memory_type:
                continue
            if not q or q in str(event).lower():
                rows.append(event)
        return rows[-limit:]

    def update_patterns(self) -> dict[str, Any]:
        counts: dict[str, int] = defaultdict(int)
        for event in self.events:
            counts[event.get("type", "episodic")] += 1
        return {"event_count": len(self.events), "patterns": dict(counts)}


class ExpertAISystem:
    """Facade composing DGSK, OOSK, BORS, reasoning, simulation, and memory."""

    def __init__(self) -> None:
        self.domain_engine = DomainGraphEngine()
        self.runtime = ExpertRuntime()
        self.reasoning = ReasoningEngine(self.runtime)
        self.economy = EconomySimulator()
        self.meta = MetaBuildEngine()
        self.planner = MultiAgentPlanner()
        self.memory = MemorySystem()
        self.feedback = MemoryFeedbackLoop(self.runtime, self.memory)
        self.expert_layer = LLMExpertLayer()
        self.persistence = ExpertAIPersistence()
        self.observability = ObservabilityHub()
        self.economy_source = EconomyDataSource()
        self.meta_source = MetaBuildDataSource()
        self.agents = AgentOrchestrator(self, self.economy_source, self.meta_source)
        self.scheduler = TrainingScheduler(self)
        self.simulation = SyntheticSimulationEngine(self)
        self.decision = DecisionEngine()
        self.compiled_graphs: dict[str, dict[str, Any]] = {}

    def run_training_pipeline(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        from gw2_progression.expert_ai.training import TrainingPipeline

        pipeline = TrainingPipeline(self)
        result = pipeline.run(body or {})
        self.observability.record_flow("train.run", result.get("status", "unknown"), {"run_id": result.get("run_id")})

        from gw2_progression.trainer.publisher import publish_from_training_pipeline
        publish_from_training_pipeline(result, self)

        return result

    def run_agents(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.agents.run(body or {})
        self.observability.record_flow("agents.run", result.get("coordination", {}).get("decision", {}).get("decision", "unknown"))
        return result

    def ingest_raw_account(self, body: dict[str, Any]) -> dict[str, Any]:
        from gw2_progression.expert_ai.raw_account import load_raw_account, raw_account_to_economy_items, raw_account_to_meta_builds, raw_account_to_runtime_payload

        raw = load_raw_account(body["path"]) if body.get("path") else body.get("raw", {})
        payload = raw_account_to_runtime_payload(raw)
        for entity in payload["entities"]:
            self.runtime.add_entity(entity)
        for relation in payload["relations"]:
            self.runtime.add_relation(relation)
        economy_items = raw_account_to_economy_items(raw)
        meta_builds = raw_account_to_meta_builds(raw)
        snapshot = self.runtime.snapshot()
        self.observability.record_flow("etl.raw_account", "completed", {"snapshot_id": snapshot.id, "account_id": payload["summary"]["account_id"]})
        return {"summary": payload["summary"], "snapshot_id": snapshot.id, "economy_items": economy_items, "meta_builds": meta_builds}

    def compile_graph(self, payload: dict[str, Any] | None = None, file_path: str | None = None) -> dict[str, Any]:
        if file_path:
            dg = self.domain_engine.load_file(file_path)
        else:
            path = Path("domain_graph.yaml")
            dg = self.domain_engine.load_file(str(path)) if payload is None and path.exists() else self.domain_engine._from_dict(payload or {})
        errors = self.domain_engine.validate(dg)
        compiled = {
            "id": str(uuid.uuid4()),
            "errors": errors,
            "dgsk": {"domain": dg.domain, "nodes": list(dg.nodes.keys()), "edges": list(dg.edges.keys())},
            "oosk": self.domain_engine.compile_to_oosk(dg),
            "bors": self.domain_engine.compile_to_bors(dg),
        }
        self.compiled_graphs[compiled["id"]] = compiled
        return compiled

    def evaluate_decision(self, body: dict[str, Any]) -> dict[str, Any]:
        raw_factors = body.get("factors", [])
        factors = [
            DecisionFactor(
                name=f.get("name", "factor"),
                value=float(f.get("value", 0)),
                weight=float(f.get("weight", 1)),
                impact=f.get("impact", ""),
                detail=f.get("detail", ""),
            )
            for f in raw_factors
        ]
        record = self.decision.decide(body.get("decision_type", "approve_recommendation"), factors, metadata=body.get("metadata", {}))
        return {
            "decision": record.decision.value,
            "score": record.score,
            "confidence": record.confidence,
            "threshold": record.threshold,
            "reason": record.reason,
            "factors": [f.__dict__ for f in record.factors],
            "metadata": record.metadata,
        }


def node_to_dict(node: GraphNode) -> dict[str, Any]:
    return {"id": node.id, "type": node.type, "properties": node.properties}


def edge_to_dict(edge: GraphEdge) -> dict[str, Any]:
    return {"source": edge.source, "target": edge.target, "relation_type": edge.relation_type, "weight": edge.weight, "properties": edge.properties}


expert_ai = ExpertAISystem()
