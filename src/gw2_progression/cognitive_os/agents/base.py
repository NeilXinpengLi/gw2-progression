from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentAction:
    action_type: str
    item_id: str | None = None
    quantity: int = 1
    target: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentProfile:
    name: str
    agent_type: str
    capital: float = 0.0
    inventory: dict[str, int] = field(default_factory=dict)
    skill_level: float = 0.5
    risk_tolerance: float = 0.5
    specialization: str | None = None


class BaseAgent(ABC):
    def __init__(self, profile: AgentProfile) -> None:
        self.profile = profile
        self._memory: list[dict[str, Any]] = []
        self._total_reward: float = 0.0

    @abstractmethod
    def act(self, world_state: dict[str, Any]) -> AgentAction:
        ...

    def observe(self, world_state: dict[str, Any], action: AgentAction, reward: float) -> None:
        self._memory.append({
            "t": world_state.get("t", 0),
            "action": action,
            "reward": reward,
            "state_snapshot": {k: v for k, v in world_state.items() if k != "inventory"},
        })
        self._total_reward += reward

    def update_profile(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if hasattr(self.profile, k):
                setattr(self.profile, k, v)

    def reset_memory(self) -> None:
        self._memory = []
        self._total_reward = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.profile.name,
            "type": self.profile.agent_type,
            "capital": self.profile.capital,
            "skill_level": self.profile.skill_level,
            "risk_tolerance": self.profile.risk_tolerance,
            "specialization": self.profile.specialization,
            "total_reward": self._total_reward,
            "memory_size": len(self._memory),
        }
