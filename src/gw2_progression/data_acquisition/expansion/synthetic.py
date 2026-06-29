from __future__ import annotations

import random
from typing import Any

from gw2_progression.data_acquisition.registry.source_registry import SourceConfig


class SyntheticExpander:
    """Synthetic Expansion — generate simulated entities from graph patterns.

    Creates plausible agents, behaviors, and world states from
    existing data to enrich the graph for simulation.
    """

    def __init__(self, synthetic_ratio: float = 0.3) -> None:
        self.synthetic_ratio = synthetic_ratio
        self._generated_count = 0

    def expand(self, data: dict[str, Any], source: SourceConfig) -> dict[str, Any]:
        entities = data.get("entities", [])
        count = max(1, int(len(entities) * self.synthetic_ratio))

        new_entities = list(entities)
        for i in range(count):
            self._generated_count += 1
            synthetic = {
                "id": f"synthetic:agent_{self._generated_count}",
                "type": "synthetic_entity",
                "name": f"SimAgent_{self._generated_count}",
                "properties": {
                    "synthetic_kind": "agent",
                    "archetype": random.choice(["trader", "crafter", "grinder", "raider", "optimizer"]),
                    "risk_tolerance": round(random.uniform(0, 1), 2),
                    "capital": round(random.uniform(100, 10000), 2),
                    "skill_level": round(random.uniform(0.3, 1.0), 2),
                    "is_synthetic": True,
                },
                "source": data.get("source", source.id),
                "confidence": min(0.75, source.confidence_default),
                "lineage": [data.get("source", source.id), "synthetic_expansion"],
            }
            new_entities.append(synthetic)

        result = dict(data)
        result["entities"] = new_entities
        result["_synthetic_expanded"] = True
        return result
