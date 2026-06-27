"""ValueGraph — tracks value propagation through entities, KPIs, risks, and decisions.

Value flow:
  Entity → KPI → Risk → Decision → Outcome

Supports:
  - build() from entities + KPIs + risks
  - propagate() from a starting node through the graph
  - impact_analysis() for what-if scenarios
  - path_to_decision() tracing
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValueNode:
    node_id: str
    node_type: str  # entity / kpi / risk / decision
    name: str = ""
    value: float = 0.0
    properties: dict = field(default_factory=dict)


@dataclass
class ValueEdge:
    source_id: str
    target_id: str
    relation: str = "influences"
    weight: float = 1.0


class ValueGraph:
    """Directed graph for value propagation analysis."""

    def __init__(self):
        self.nodes: dict[str, ValueNode] = {}
        self.edges: list[ValueEdge] = []

    def add_node(self, node: ValueNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: ValueEdge) -> None:
        self.edges.append(edge)

    def build(
        self,
        entities: list[Any] | None = None,
        kpis: list[Any] | None = None,
        risks: list[Any] | None = None,
        decisions: list[Any] | None = None,
    ) -> None:
        self.nodes.clear()
        self.edges.clear()
        for i, ent in enumerate(entities or []):
            nid = f"ent_{i}"
            val = ext_val(ent, "value", 0)
            self.add_node(ValueNode(node_id=nid, node_type="entity", name=ext_name(ent, f"Entity {i}"), value=val))
        for i, kpi in enumerate(kpis or []):
            nid = f"kpi_{i}"
            val = getattr(kpi, "value", 0) if hasattr(kpi, "value") else kpi.get("value", 0)
            self.add_node(ValueNode(node_id=nid, node_type="kpi", name=ext_name(kpi, f"KPI {i}"), value=val))
            for j in range(len(entities or [])):
                self.add_edge(ValueEdge(source_id=f"ent_{j}", target_id=nid, relation="measured_by"))
        for i, risk in enumerate(risks or []):
            nid = f"risk_{i}"
            self.add_node(ValueNode(node_id=nid, node_type="risk", name=ext_name(risk, f"Risk {i}"), value=ext_val(risk, "score", 0.5)))
            for j in range(len(kpis or [])):
                self.add_edge(ValueEdge(source_id=f"kpi_{j}", target_id=nid, relation="assesses"))
        for i, dec in enumerate(decisions or []):
            nid = f"dec_{i}"
            scr = getattr(dec, "score", 0) if hasattr(dec, "score") else dec.get("score", 0)
            self.add_node(ValueNode(node_id=nid, node_type="decision", name=ext_name(dec, f"Decision {i}"), value=scr))
            for j in range(len(risks or [])):
                self.add_edge(ValueEdge(source_id=f"risk_{j}", target_id=nid, relation="informs"))

    def propagate(self, node_id: str, depth: int = 3) -> list[dict]:
        """From a starting node, trace value flow forward up to `depth` hops."""
        visited: set[str] = set()
        results: list[dict] = []
        limit = [0]
        max_results = 200

        def _walk(current_id: str, remaining: int, path_value: float):
            if current_id in visited or remaining < 0:
                return
            if limit[0] >= max_results:
                return
            visited.add(current_id)
            node = self.nodes.get(current_id)
            if not node:
                return
            limit[0] += 1
            results.append({
                "node_id": node.node_id,
                "node_type": node.node_type,
                "name": node.name,
                "value": node.value,
                "path_value": round(path_value, 4),
            })
            for edge in self.edges:
                if edge.source_id == current_id:
                    target_node = self.nodes.get(edge.target_id)
                    next_val = path_value * edge.weight * (target_node.value if target_node else 1)
                    _walk(edge.target_id, remaining - 1, next_val)

        _walk(node_id, depth, 1.0)
        return results

    def impact_analysis(self, entity_id: str) -> dict:
        """What KPIs, risks, and decisions are affected by a given entity."""
        path = self.propagate(entity_id, depth=3)
        kpis = [p for p in path if p["node_type"] == "kpi"]
        risks = [p for p in path if p["node_type"] == "risk"]
        decisions = [p for p in path if p["node_type"] == "decision"]
        return {
            "entity_id": entity_id,
            "affected_kpis": kpis,
            "affected_risks": risks,
            "affected_decisions": decisions,
            "propagation_count": len(path),
        }

    def path_to_decision(self, entity_id: str, target_kpi: str = "") -> list[dict]:
        """Trace the shortest path from entity to a decision node."""
        full_path = self.propagate(entity_id, depth=5)
        decisions = [p for p in full_path if p["node_type"] == "decision"]
        if not decisions:
            return full_path
        return full_path[: full_path.index(decisions[0]) + 1]


def ext_name(obj: Any, fallback: str) -> str:
    if hasattr(obj, "name"):
        return obj.name
    if isinstance(obj, dict):
        return obj.get("name", obj.get("kpi_type", obj.get("risk_type", fallback)))
    return fallback


def ext_val(obj: Any, key: str, default: float) -> float:
    if hasattr(obj, key):
        return getattr(obj, key, default)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default
