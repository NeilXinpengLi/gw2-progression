from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gw2_progression.data_acquisition.dgsk.edge_builder import EdgeBuilder
from gw2_progression.data_acquisition.dgsk.node_manager import NodeManager


@dataclass
class GraphBuildResult:
    nodes_added: int = 0
    edges_added: int = 0
    total_nodes: int = 0
    total_edges: int = 0


class DGSKGraphBuilder:
    """Automatic DGSK graph construction from normalized/expanded data.

    Converts entities → DGSK nodes and relations → DGSK edges.
    Integrates with the existing CognitionGraph and ProbabilisticDGSK.
    """

    def __init__(
        self,
        node_manager: NodeManager | None = None,
        edge_builder: EdgeBuilder | None = None,
    ) -> None:
        self.node_manager = node_manager or NodeManager()
        self.edge_builder = edge_builder or EdgeBuilder()
        self._graph: dict[str, Any] = {"nodes": {}, "edges": []}
        self._build_count = 0

    def build(self, data: dict[str, Any]) -> GraphBuildResult:
        entities = data.get("entities", [])
        relations = data.get("relations", [])
        source = data.get("source", "unknown")

        nodes_added = 0
        edges_added = 0

        for entity in entities:
            nid = entity.get("id", "")
            if not nid:
                continue
            node = self.node_manager.ensure_node(
                node_id=nid,
                node_type=entity.get("type", "entity"),
                label=entity.get("name", nid),
                properties=dict(entity.get("properties", {})),
                source=source,
            )
            if nid not in self._graph["nodes"]:
                self._graph["nodes"][nid] = node
                nodes_added += 1

        for relation in relations:
            src = relation.get("source", "")
            tgt = relation.get("target", "")
            rel_type = relation.get("relation", "related_to")
            if src in self._graph["nodes"] and tgt in self._graph["nodes"]:
                edge = self.edge_builder.build_edge(
                    source=src,
                    target=tgt,
                    relation=rel_type,
                    weight=relation.get("confidence", 0.8),
                    metadata=relation.get("metadata", {}),
                )
                self._graph["edges"].append(edge)
                edges_added += 1

        self._build_count += 1
        return GraphBuildResult(
            nodes_added=nodes_added,
            edges_added=edges_added,
            total_nodes=len(self._graph["nodes"]),
            total_edges=len(self._graph["edges"]),
        )

    @property
    def graph(self) -> dict[str, Any]:
        return dict(self._graph)

    def merge_into(self, target_graph: Any) -> None:
        """Merge built graph into an external CognitionGraph."""
        if hasattr(target_graph, "merge_with_cognition_graph"):
            target_graph.merge_with_cognition_graph(self)
        elif hasattr(target_graph, "add_node") and hasattr(target_graph, "add_edge"):
            for nid, ndata in self._graph["nodes"].items():
                target_graph.add_node(
                    ndata.get("_type", "entity"),
                    ndata.get("label", nid),
                    ndata.get("properties", {}),
                    node_id=nid,
                )
            for edge in self._graph["edges"]:
                target_graph.add_edge(
                    edge["source"],
                    edge["target"],
                    edge.get("edge_type", "related_to"),
                    weight=edge.get("weight", 1.0),
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_nodes": len(self._graph["nodes"]),
            "total_edges": len(self._graph["edges"]),
            "build_count": self._build_count,
            "node_types": self.node_manager.to_dict(),
            "edge_types": self.edge_builder.to_dict(),
        }
