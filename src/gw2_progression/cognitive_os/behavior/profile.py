from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    FARM = "farm"
    CRAFT = "craft"
    TRADE = "trade"
    RAID = "raid"
    ACHIEVEMENT = "achievement"
    META = "meta"
    GATHER = "gather"
    EXPLORE = "explore"


class Archetype(str, Enum):
    TRADER = "trader"
    CRAFTER = "crafter"
    GRINDER = "grinder"
    META_FOLLOWER = "meta_follower"
    OPTIMIZER = "optimizer"
    ACHIEVER = "achiever"
    EXPLORER = "explorer"
    RAIDER = "raider"


@dataclass
class ArchetypeSignature:
    name: Archetype
    action_weights: dict[ActionType, float]
    item_preferences: list[str] = field(default_factory=list)
    risk_tolerance: float = 0.5
    time_horizon: str = "medium"
    capital_preference: str = "balanced"


ARCHETYPE_SIGNATURES: dict[Archetype, ArchetypeSignature] = {
    Archetype.TRADER: ArchetypeSignature(
        name=Archetype.TRADER,
        action_weights={
            ActionType.FARM: 0.05,
            ActionType.CRAFT: 0.10,
            ActionType.TRADE: 0.70,
            ActionType.RAID: 0.0,
            ActionType.ACHIEVEMENT: 0.05,
            ActionType.META: 0.05,
            ActionType.GATHER: 0.0,
            ActionType.EXPLORE: 0.05,
        },
        item_preferences=["mystic_coin", "ectoplasm", "t6_mats"],
        risk_tolerance=0.6,
        time_horizon="short",
        capital_preference="liquid",
    ),
    Archetype.CRAFTER: ArchetypeSignature(
        name=Archetype.CRAFTER,
        action_weights={
            ActionType.FARM: 0.05,
            ActionType.CRAFT: 0.65,
            ActionType.TRADE: 0.15,
            ActionType.RAID: 0.0,
            ActionType.ACHIEVEMENT: 0.05,
            ActionType.META: 0.05,
            ActionType.GATHER: 0.05,
            ActionType.EXPLORE: 0.0,
        },
        item_preferences=["mithril_ingot", "elder_plank", "bolt_of_damask"],
        risk_tolerance=0.3,
        time_horizon="medium",
        capital_preference="materials",
    ),
    Archetype.GRINDER: ArchetypeSignature(
        name=Archetype.GRINDER,
        action_weights={
            ActionType.FARM: 0.60,
            ActionType.CRAFT: 0.05,
            ActionType.TRADE: 0.05,
            ActionType.RAID: 0.10,
            ActionType.ACHIEVEMENT: 0.05,
            ActionType.META: 0.10,
            ActionType.GATHER: 0.05,
            ActionType.EXPLORE: 0.0,
        },
        risk_tolerance=0.4,
        time_horizon="short",
        capital_preference="spend",
    ),
    Archetype.META_FOLLOWER: ArchetypeSignature(
        name=Archetype.META_FOLLOWER,
        action_weights={
            ActionType.FARM: 0.10,
            ActionType.CRAFT: 0.15,
            ActionType.TRADE: 0.10,
            ActionType.RAID: 0.20,
            ActionType.ACHIEVEMENT: 0.10,
            ActionType.META: 0.30,
            ActionType.GATHER: 0.0,
            ActionType.EXPLORE: 0.05,
        },
        risk_tolerance=0.5,
        time_horizon="short",
        capital_preference="gear",
    ),
    Archetype.OPTIMIZER: ArchetypeSignature(
        name=Archetype.OPTIMIZER,
        action_weights={
            ActionType.FARM: 0.10,
            ActionType.CRAFT: 0.20,
            ActionType.TRADE: 0.20,
            ActionType.RAID: 0.15,
            ActionType.ACHIEVEMENT: 0.15,
            ActionType.META: 0.10,
            ActionType.GATHER: 0.05,
            ActionType.EXPLORE: 0.05,
        },
        risk_tolerance=0.4,
        time_horizon="long",
        capital_preference="balanced",
    ),
    Archetype.ACHIEVER: ArchetypeSignature(
        name=Archetype.ACHIEVER,
        action_weights={
            ActionType.FARM: 0.10,
            ActionType.CRAFT: 0.15,
            ActionType.TRADE: 0.05,
            ActionType.RAID: 0.10,
            ActionType.ACHIEVEMENT: 0.50,
            ActionType.META: 0.05,
            ActionType.GATHER: 0.0,
            ActionType.EXPLORE: 0.05,
        },
        risk_tolerance=0.3,
        time_horizon="long",
        capital_preference="achievements",
    ),
    Archetype.EXPLORER: ArchetypeSignature(
        name=Archetype.EXPLORER,
        action_weights={
            ActionType.FARM: 0.05,
            ActionType.CRAFT: 0.05,
            ActionType.TRADE: 0.05,
            ActionType.RAID: 0.05,
            ActionType.ACHIEVEMENT: 0.15,
            ActionType.META: 0.10,
            ActionType.GATHER: 0.30,
            ActionType.EXPLORE: 0.25,
        },
        risk_tolerance=0.7,
        time_horizon="medium",
        capital_preference="balanced",
    ),
    Archetype.RAIDER: ArchetypeSignature(
        name=Archetype.RAIDER,
        action_weights={
            ActionType.FARM: 0.10,
            ActionType.CRAFT: 0.10,
            ActionType.TRADE: 0.05,
            ActionType.RAID: 0.55,
            ActionType.ACHIEVEMENT: 0.10,
            ActionType.META: 0.05,
            ActionType.GATHER: 0.0,
            ActionType.EXPLORE: 0.05,
        },
        item_preferences=["legendary_insight", "li", "magnetite_shard"],
        risk_tolerance=0.5,
        time_horizon="medium",
        capital_preference="gear",
    ),
}


class BehaviorProfile:
    """A player's behavioral signature as a distribution over archetypes.

    Instead of a single archetype, each player has a mixture distribution.
    This enables probabilistic behavior modeling.
    """

    def __init__(
        self,
        archetype_weights: dict[Archetype, float] | None = None,
        label: str = "default",
    ) -> None:
        if archetype_weights:
            total = sum(archetype_weights.values())
            self.archetype_weights = {
                k: v / total for k, v in archetype_weights.items()
            }
        else:
            n = len(Archetype)
            uniform = 1.0 / n
            self.archetype_weights = {a: uniform for a in Archetype}
        self.label = label
        self._action_history: list[ActionType] = []
        self._state_history: list[dict[str, Any]] = []

    @property
    def dominant_archetype(self) -> Archetype:
        return max(self.archetype_weights, key=self.archetype_weights.get)

    def archetype_mixture(self) -> dict[str, float]:
        return {a.value: round(w, 4) for a, w in self.archetype_weights.items()}

    def action_distribution(self) -> dict[ActionType, float]:
        dist: dict[ActionType, float] = {}
        for archetype, weight in self.archetype_weights.items():
            sig = ARCHETYPE_SIGNATURES[archetype]
            for action, aw in sig.action_weights.items():
                dist[action] = dist.get(action, 0.0) + weight * aw

        total = sum(dist.values())
        if total > 0:
            dist = {k: v / total for k, v in dist.items()}
        return dist

    def sample_action(self, rng: random.Random | None = None) -> ActionType:
        import random as _random
        rng = rng or _random.Random()
        dist = self.action_distribution()
        actions = list(dist.keys())
        weights = [dist[a] for a in actions]
        return rng.choices(actions, weights=weights, k=1)[0]

    def sample_action_with_state(
        self,
        state: dict[str, Any],
        rng: random.Random | None = None,
    ) -> tuple[ActionType, dict[str, Any]]:
        """Sample an action type, then produce a concrete action dict."""
        action_type = self.sample_action(rng)
        params = self._params_for_action(action_type, state)
        self._action_history.append(action_type)
        self._state_history.append(dict(state))
        return action_type, params

    def _params_for_action(self, action_type: ActionType, state: dict[str, Any]) -> dict[str, Any]:
        inventory = state.get("inventory", {}) or {}
        market = state.get("market", {}) or {}
        base = {"type": action_type.value, "item_id": "", "quantity": 1}

        if action_type == ActionType.FARM:
            targets = ["gold", "magnetite_shard", "mystic_coin"]
            return {**base, "item_id": targets[0], "quantity": 3}
        if action_type == ActionType.TRADE:
            for item_id, data in market.items():
                if data.get("price", 100) < 120:
                    return {**base, "item_id": str(item_id), "quantity": 5, "price": data["price"]}
            return {**base, "item_id": "gold", "quantity": 1}
        if action_type == ActionType.CRAFT:
            for item_id, count in inventory.items():
                sid = str(item_id)
                if count > 0:
                    return {**base, "item_id": sid, "quantity": min(count, 5)}
            return {**base, "item_id": "mystic_coin", "quantity": 1}
        if action_type == ActionType.RAID:
            return {**base, "item_id": "raid_boss", "quantity": 1}
        if action_type == ActionType.ACHIEVEMENT:
            return {**base, "item_id": "achievement_task", "quantity": 1}
        if action_type == ActionType.META:
            return {**base, "item_id": "meta_event", "quantity": 1}
        if action_type == ActionType.EXPLORE:
            return {**base, "item_id": "exploration", "quantity": 1}

        return {**base, "item_id": "gold", "quantity": 1}

    def update_from_observation(self, action_type: ActionType, reward: float) -> None:
        """Bayesian-like update: reinforce archetypes consistent with observed reward."""
        for archetype, weight in list(self.archetype_weights.items()):
            sig = ARCHETYPE_SIGNATURES[archetype]
            action_weight = sig.action_weights.get(action_type, 0.0)
            consistency = action_weight * max(0, reward)
            self.archetype_weights[archetype] = weight * (1.0 + consistency * 0.1)

        total = sum(self.archetype_weights.values())
        if total > 0:
            self.archetype_weights = {k: v / total for k, v in self.archetype_weights.items()}

    def similarity(self, other: BehaviorProfile) -> float:
        """Cosine similarity between archetype weight vectors."""
        all_archs = set(self.archetype_weights) | set(other.archetype_weights)
        dot = sum(self.archetype_weights.get(a, 0.0) * other.archetype_weights.get(a, 0.0) for a in all_archs)
        n1 = math.sqrt(sum(self.archetype_weights.get(a, 0.0) ** 2 for a in all_archs))
        n2 = math.sqrt(sum(other.archetype_weights.get(a, 0.0) ** 2 for a in all_archs))
        if n1 * n2 == 0:
            return 0.0
        return dot / (n1 * n2)

    def entropy(self) -> float:
        """Shannon entropy of the archetype distribution — higher = more mixed."""
        total = sum(self.archetype_weights.values())
        if total <= 0:
            return 0.0
        h = 0.0
        for w in self.archetype_weights.values():
            p = w / total
            if p > 0:
                h -= p * math.log2(p)
        return h / math.log2(len(self.archetype_weights)) if len(self.archetype_weights) > 1 else 0.0

    @property
    def risk_tolerance(self) -> float:
        """Weighted risk tolerance across archetypes."""
        total_w = sum(self.archetype_weights.values())
        if total_w <= 0:
            return 0.5
        return sum(
            self.archetype_weights.get(a, 0.0) * ARCHETYPE_SIGNATURES[a].risk_tolerance
            for a in Archetype
        ) / total_w

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "dominant_archetype": self.dominant_archetype.value,
            "archetype_mixture": self.archetype_mixture(),
            "action_distribution": {k.value: round(v, 4) for k, v in self.action_distribution().items()},
            "entropy": round(self.entropy(), 4),
            "risk_tolerance": round(self.risk_tolerance, 3),
            "action_count": len(self._action_history),
        }
