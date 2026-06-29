from __future__ import annotations

from typing import Any

from gw2_progression.cognitive_os.agents.base import AgentAction, AgentProfile, BaseAgent


class ExplorerAgent(BaseAgent):
    """Exploration and achievement sampler for horizontal progression."""

    def __init__(self, name: str = "Explorer", curiosity: float = 0.8) -> None:
        super().__init__(AgentProfile(
            name=name,
            agent_type="explorer",
            skill_level=curiosity,
            risk_tolerance=0.7,
            specialization="map_completion",
        ))
        self._regions = ["core_tyria", "heart_of_thorns", "path_of_fire", "end_of_dragons", "janthir"]

    def act(self, world_state: dict[str, Any]) -> AgentAction:
        achievements = set(world_state.get("achievements", []) or [])
        missing_regions = [region for region in self._regions if f"explored_{region}" not in achievements]
        target = missing_regions[0] if missing_regions else "achievement_task"

        return AgentAction(
            action_type="achievement",
            item_id=target,
            quantity=1,
            params={
                "mode": "explore" if missing_regions else "completionist",
                "novelty": round(self.profile.skill_level, 3),
                "remaining_regions": len(missing_regions),
            },
        )
