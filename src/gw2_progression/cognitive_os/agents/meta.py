from __future__ import annotations

import random
from typing import Any

from gw2_progression.cognitive_os.agents.base import AgentAction, AgentProfile, BaseAgent


class MetaAgent(BaseAgent):
    """Meta/build specialist — chases the current meta.

    Tracks balance patches, theorycrafts optimal builds.
    Prioritizes gear upgrades with highest DPS/HPS impact.
    """

    def __init__(self, name: str = "MetaAnalyst", skill_level: float = 0.85) -> None:
        super().__init__(AgentProfile(
            name=name,
            agent_type="meta",
            skill_level=skill_level,
            specialization="build_optimization",
        ))
        self._meta_priority: dict[str, float] = {}

    def update_meta(self, item_id: str, priority: float) -> None:
        self._meta_priority[item_id] = priority

    def act(self, world_state: dict[str, Any]) -> AgentAction:
        inventory = world_state.get("inventory", {}) or {}

        best_item: str | None = None
        best_priority = 0.0
        for item_id, priority in self._meta_priority.items():
            own_count = inventory.get(item_id, 0)
            if own_count < 1:
                if priority > best_priority:
                    best_priority = priority
                    best_item = item_id

        if best_item:
            return AgentAction(
                action_type="achievement",
                item_id=best_item,
                quantity=1,
                params={"priority": best_priority, "source": "meta_optimization"},
            )

        if random.random() < 0.2:
            improvement_items = [iid for iid in self._meta_priority if iid in inventory]
            if improvement_items:
                chosen = random.choice(improvement_items)
                return AgentAction(
                    action_type="collect",
                    item_id=chosen,
                    quantity=1,
                    params={"source": "gear_upgrade"},
                )

        return AgentAction(
            action_type="achievement",
            item_id="meta_analysis",
            quantity=1,
            params={"priority": 1.0, "source": "meta_scan"},
        )
