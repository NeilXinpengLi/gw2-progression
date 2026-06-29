from __future__ import annotations

import time
from typing import Any

from gw2_progression.data_acquisition.registry.source_registry import SourceConfig


class TemporalExpander:
    """Temporal Expansion — reconstruct history from snapshots.

    Simulates historical state from a current snapshot by
    applying backward inference rules.
    """

    def __init__(self, history_depth: int = 5) -> None:
        self.history_depth = history_depth
        self._snapshot_history: list[dict[str, Any]] = []

    def expand(self, data: dict[str, Any], source: SourceConfig) -> dict[str, Any]:
        entities = data.get("entities", [])

        current_time = time.time()
        historical_entities = []
        window = max(1, len(entities) // 2)

        for i, entity in enumerate(entities[:window]):
            for t in range(1, self.history_depth + 1):
                hist_entity = dict(entity)
                hist_entity["id"] = f"{entity['id']}@t-{t}"
                hist_entity["temporal_offset"] = -t
                hist_entity["timestamp"] = current_time - (t * 86400)
                hist_entity["properties"] = dict(entity.get("properties", {}))
                hist_entity["properties"]["estimation_confidence"] = max(0.3, 1.0 - t * 0.15)
                historical_entities.append(hist_entity)

        result = dict(data)
        result["entities"] = entities + historical_entities
        result["_temporal_expanded"] = True

        self._snapshot_history.append({
            "source": source.id,
            "timestamp": current_time,
            "entity_count": len(entities),
            "historical_count": len(historical_entities),
        })
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "history_depth": self.history_depth,
            "snapshots": len(self._snapshot_history),
        }
