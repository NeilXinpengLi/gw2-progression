from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    ENTITY = "entity"
    STATE = "state"
    DECISION = "decision"
    ACTION = "action"
    AGENT = "agent"
    GOAL = "goal"


class EdgeType(str, Enum):
    EVOLVES_TO = "evolves_to"
    DEPENDS_ON = "depends_on"
    CAUSES = "causes"
    INFLUENCES = "influences"
    CHANGES = "changes"
    AFFECTS = "affects"
    PRODUCES = "produces"
    CONSUMES = "consumes"


@dataclass
class CognitionNode:
    node_id: str
    node_type: NodeType
    label: str
    properties: dict[str, Any] = field(default_factory=dict)
    t_created: int = 0
    t_expires: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active_at(self, t: int) -> bool:
        return self.t_created <= t and (self.t_expires is None or t < self.t_expires)


@dataclass
class CognitionEdge:
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    t_created: int = 0
    t_expires: int | None = None
    properties: dict[str, Any] = field(default_factory=dict)

    def is_active_at(self, t: int) -> bool:
        return self.t_created <= t and (self.t_expires is None or t < self.t_expires)


class CognitionGraph:
    """Time-aware cognitive graph connecting entities, states, decisions.

    Character ──(evolves_to)──> Build
    Build ──(affects)──> Economy
    Economy ──(influences)──> Decision
    Decision ──(changes)──> Character
    """

    def __init__(self) -> None:
        self._nodes: dict[str, CognitionNode] = {}
        self._edges: list[CognitionEdge] = []
        self._node_indices: dict[NodeType, list[str]] = {nt: [] for nt in NodeType}
        self._edge_indices: dict[EdgeType, list[str]] = {et: [] for et in EdgeType}

    def add_node(
        self,
        node_type: NodeType,
        label: str,
        properties: dict[str, Any] | None = None,
        node_id: str | None = None,
        t_created: int = 0,
        t_expires: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        nid = node_id or f"{node_type.value}:{uuid.uuid4().hex[:12]}"
        node = CognitionNode(
            node_id=nid,
            node_type=node_type,
            label=label,
            properties=properties or {},
            t_created=t_created,
            t_expires=t_expires,
            metadata=metadata or {},
        )
        self._nodes[nid] = node
        self._node_indices.setdefault(node_type, []).append(nid)
        return nid

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        t_created: int = 0,
        t_expires: int | None = None,
        properties: dict[str, Any] | None = None,
        edge_id: str | None = None,
    ) -> str:
        if source_id not in self._nodes:
            msg = f"Source node {source_id} not found"
            raise KeyError(msg)
        if target_id not in self._nodes:
            msg = f"Target node {target_id} not found"
            raise KeyError(msg)
        eid = edge_id or f"e:{uuid.uuid4().hex[:12]}"
        edge = CognitionEdge(
            edge_id=eid,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            t_created=t_created,
            t_expires=t_expires,
            properties=properties or {},
        )
        self._edges.append(edge)
        self._edge_indices.setdefault(edge_type, []).append(eid)
        return eid

    def get_node(self, node_id: str) -> CognitionNode | None:
        return self._nodes.get(node_id)

    def get_nodes_by_type(self, node_type: NodeType) -> list[CognitionNode]:
        return [self._nodes[nid] for nid in self._node_indices.get(node_type, []) if nid in self._nodes]

    def get_edges(self, edge_type: EdgeType | None = None) -> list[CognitionEdge]:
        if edge_type:
            return [e for e in self._edges if e.edge_type == edge_type]
        return list(self._edges)

    def get_outgoing(self, node_id: str) -> list[CognitionEdge]:
        return [e for e in self._edges if e.source_id == node_id]

    def get_incoming(self, node_id: str) -> list[CognitionEdge]:
        return [e for e in self._edges if e.target_id == node_id]

    def get_neighbors(self, node_id: str, edge_type: EdgeType | None = None) -> list[CognitionNode]:
        neighbor_ids: set[str] = set()
        for e in self._edges:
            if e.source_id == node_id and (edge_type is None or e.edge_type == edge_type):
                neighbor_ids.add(e.target_id)
            if e.target_id == node_id and (edge_type is None or e.edge_type == edge_type):
                neighbor_ids.add(e.source_id)
        return [self._nodes[nid] for nid in neighbor_ids if nid in self._nodes]

    def traverse(
        self,
        start_id: str,
        max_depth: int = 3,
        edge_types: set[EdgeType] | None = None,
        at_time: int | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        visited: set[str] = set()

        def _dfs(node_id: str, depth: int, path: list[str]) -> None:
            if depth > max_depth or node_id in visited:
                return
            visited.add(node_id)
            node = self._nodes.get(node_id)
            if node and (at_time is None or node.is_active_at(at_time)):
                results.append({
                    "node_id": node_id,
                    "node_type": node.node_type.value,
                    "label": node.label,
                    "depth": depth,
                    "path": list(path),
                    "properties": node.properties,
                })
            for e in self._edges:
                if e.source_id == node_id:
                    if edge_types and e.edge_type not in edge_types:
                        continue
                    if at_time is not None and not e.is_active_at(at_time):
                        continue
                    _dfs(e.target_id, depth + 1, path + [e.target_id])

        _dfs(start_id, 0, [start_id])
        return results

    def find_path(self, source_id: str, target_id: str, max_depth: int = 5) -> list[list[str]]:
        paths: list[list[str]] = []

        def _dfs(current: str, target: str, path: list[str], depth: int) -> None:
            if depth > max_depth:
                return
            if current == target:
                paths.append(list(path))
                return
            for e in self._edges:
                if e.source_id == current and e.target_id not in path:
                    _dfs(e.target_id, target, path + [e.target_id], depth + 1)

        _dfs(source_id, target_id, [source_id], 0)
        return paths

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {nid: {
                "node_id": n.node_id,
                "node_type": n.node_type.value,
                "label": n.label,
                "properties": n.properties,
                "t_created": n.t_created,
                "t_expires": n.t_expires,
            } for nid, n in self._nodes.items()},
            "edges": [{
                "edge_id": e.edge_id,
                "source_id": e.source_id,
                "target_id": e.target_id,
                "edge_type": e.edge_type.value,
                "weight": e.weight,
                "t_created": e.t_created,
            } for e in self._edges],
            "stats": {
                "node_count": len(self._nodes),
                "edge_count": len(self._edges),
                "node_types": {nt.value: len(nids) for nt, nids in self._node_indices.items()},
                "edge_types": {et.value: len(eids) for et, eids in self._edge_indices.items()},
            },
        }
