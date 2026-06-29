from __future__ import annotations

from typing import Any


class EdgeBuilder:
    """Builds DGSK edges from extracted relations.

    Maps relation types to edge types with confidence weighting.
    """

    RELATION_MAP: dict[str, str] = {
        "depends_on": "depends_on",
        "produces": "produces",
        "consumes": "consumes",
        "requires": "depends_on",
        "part_of": "contains",
        "located_in": "contains",
        "related_to": "influences",
        "trades_with": "trades_with",
        "references": "influences",
    }

    def __init__(self) -> None:
        self._edge_count_by_type: dict[str, int] = {}

    def build_edge(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float = 0.8,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        edge_type = self.RELATION_MAP.get(relation, relation)
        self._edge_count_by_type[edge_type] = self._edge_count_by_type.get(edge_type, 0) + 1

        return {
            "source": source,
            "target": target,
            "relation": relation,
            "edge_type": edge_type,
            "weight": weight,
            "metadata": metadata or {},
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "by_type": dict(self._edge_count_by_type),
        }
