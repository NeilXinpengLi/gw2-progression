from __future__ import annotations

import random
from typing import Any

from gw2_progression.cognitive_os.agents.base import AgentAction, AgentProfile, BaseAgent


class RaiderAgent(BaseAgent):
    """PvE/Raid specialist — farms instances for rare drops and currencies.

    Targets high-value raid rewards and daily fractals.
    Tracks lockout timers and farm efficiency.
    """

    def __init__(self, name: str = "Raider", skill_level: float = 0.8) -> None:
        super().__init__(AgentProfile(
            name=name,
            agent_type="raider",
            skill_level=skill_level,
            specialization="pve_raids",
        ))
        self._raid_targets: list[str] = ["magnetite_shard", "gaeting_crystal", "legendary_insight"]
        self._daily_done: set[str] = set()

    def reset_dailies(self) -> None:
        self._daily_done.clear()

    def act(self, world_state: dict[str, Any]) -> AgentAction:
        achievements = set(world_state.get("achievements", []) or [])
        inventory = world_state.get("inventory", {}) or {}

        for target in self._raid_targets:
            if target not in self._daily_done:
                daily_ach = f"daily_{target}"
                if daily_ach not in achievements and random.random() < self.profile.skill_level:
                    self._daily_done.add(target)
                    return AgentAction(
                        action_type="farm",
                        item_id=target,
                        quantity=max(1, int(self.profile.skill_level * 5)),
                        params={"source": "raid", "daily": True},
                    )

        if random.random() < 0.3:
            item_id = random.choice(list(inventory.keys())) if inventory else "magnetite_shard"
            return AgentAction(
                action_type="gather",
                item_id=item_id if isinstance(item_id, str) else str(item_id),
                quantity=3,
                params={"source": "fractal"},
            )

        return AgentAction(
            action_type="farm",
            item_id="magnetite_shard",
            quantity=3,
            params={"source": "raid"},
        )
