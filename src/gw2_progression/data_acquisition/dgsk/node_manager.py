from __future__ import annotations

from typing import Any


class NodeManager:
    """Manages DGSK node lifecycle during graph construction.

    Deduplicates nodes by ID, tracks node types and metadata.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._type_counts: dict[str, int] = {}

    def ensure_node(
        self,
        node_id: str,
        node_type: str = "entity",
        label: str = "",
        properties: dict[str, Any] | None = None,
        source: str = "",
    ) -> dict[str, Any]:
        if node_id in self._nodes:
            existing = self._nodes[node_id]
            if properties:
                existing["properties"].update(properties)
            if source and source not in existing.get("sources", []):
                existing.setdefault("sources", []).append(source)
            return existing

        node = {
            "id": node_id,
            "type": node_type,
            "_type": node_type,
            "label": label or node_id,
            "properties": properties or {},
            "sources": [source] if source else [],
        }
        self._nodes[node_id] = node
        self._type_counts[node_type] = self._type_counts.get(node_type, 0) + 1
        return node

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return self._nodes.get(node_id)

    def remove_node(self, node_id: str) -> bool:
        node = self._nodes.pop(node_id, None)
        if node:
            nt = node.get("type", "unknown")
            self._type_counts[nt] = max(0, self._type_counts.get(nt, 1) - 1)
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": len(self._nodes),
            "by_type": dict(self._type_counts),
        }
