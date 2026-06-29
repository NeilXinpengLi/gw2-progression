from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from gw2_progression.cognitive_os.behavior.profile import (
    ARCHETYPE_SIGNATURES,
    ActionType,
    Archetype,
    BehaviorProfile,
)


@dataclass
class BehaviorObservation:
    """One observation of player behavior."""

    timestamp: int
    action_type: ActionType
    reward: float
    state_snapshot: dict[str, Any] = field(default_factory=dict)
    archetype_scores: dict[str, float] = field(default_factory=dict)


class BehaviorEvolutionModel:
    """Models how behavior distributions evolve over time (behavior(t) → behavior(t+1)).

    Archetypes have transition probabilities:
      - stability: probability of staying same archetype
      - drift: gradual shift toward adjacent archetypes
      - shock: sudden change from meta shifts or discovery
    """

    def __init__(self, stability: float = 0.85, drift_rate: float = 0.10, shock_rate: float = 0.05) -> None:
        self.stability = stability
        self.drift_rate = drift_rate
        self.shock_rate = shock_rate
        self._archetype_adjacency: dict[Archetype, list[Archetype]] = self._build_adjacency()

    def _build_adjacency(self) -> dict[Archetype, list[Archetype]]:
        return {
            Archetype.TRADER: [Archetype.OPTIMIZER, Archetype.CRAFTER],
            Archetype.CRAFTER: [Archetype.TRADER, Archetype.OPTIMIZER, Archetype.GRINDER],
            Archetype.GRINDER: [Archetype.RAIDER, Archetype.META_FOLLOWER, Archetype.CRAFTER],
            Archetype.META_FOLLOWER: [Archetype.RAIDER, Archetype.OPTIMIZER, Archetype.GRINDER],
            Archetype.OPTIMIZER: [Archetype.TRADER, Archetype.CRAFTER, Archetype.META_FOLLOWER, Archetype.ACHIEVER],
            Archetype.ACHIEVER: [Archetype.OPTIMIZER, Archetype.EXPLORER, Archetype.RAIDER],
            Archetype.EXPLORER: [Archetype.ACHIEVER, Archetype.GRINDER],
            Archetype.RAIDER: [Archetype.META_FOLLOWER, Archetype.ACHIEVER, Archetype.GRINDER],
        }

    def evolve(self, profile: BehaviorProfile, meta_shift: float = 0.0, rng: random.Random | None = None) -> BehaviorProfile:
        rng = rng or random.Random()
        new_weights: dict[Archetype, float] = {}
        effective_shock = min(1.0, self.shock_rate + meta_shift)

        for archetype, weight in profile.archetype_weights.items():
            roll = rng.random()
            if roll < self.stability * (1.0 - meta_shift * 0.5):
                new_weights[archetype] = new_weights.get(archetype, 0.0) + weight
            elif roll < self.stability + self.drift_rate:
                neighbors = self._archetype_adjacency.get(archetype, [])
                if neighbors:
                    target = rng.choice(neighbors)
                    new_weights[target] = new_weights.get(target, 0.0) + weight * 0.7
                    new_weights[archetype] = new_weights.get(archetype, 0.0) + weight * 0.3
                else:
                    new_weights[archetype] = new_weights.get(archetype, 0.0) + weight
            elif roll < self.stability + self.drift_rate + effective_shock:
                all_archs = list(Archetype)
                shock_target = rng.choice(all_archs)
                new_weights[shock_target] = new_weights.get(shock_target, 0.0) + weight * 0.6
                new_weights[archetype] = new_weights.get(archetype, 0.0) + weight * 0.4
            else:
                new_weights[archetype] = new_weights.get(archetype, 0.0) + weight

        total = sum(new_weights.values())
        if total > 0:
            new_weights = {k: v / total for k, v in new_weights.items()}
        else:
            n = len(Archetype)
            new_weights = {a: 1.0 / n for a in Archetype}

        evolved = BehaviorProfile(archetype_weights=new_weights, label=profile.label)
        evolved._action_history = list(profile._action_history)
        evolved._state_history = list(profile._state_history)
        return evolved


class BehaviorModel:
    """Top-level behavior model managing multiple player profiles.

    Provides:
      - Classification: state → most likely archetype
      - Distribution: population-level behavior distribution
      - Evolution: behavior(t) → behavior(t+1)
      - Calibration: adjust archetype weights from observations
    """

    def __init__(self, default_archetype: Archetype = Archetype.OPTIMIZER) -> None:
        self.profiles: dict[str, BehaviorProfile] = {}
        self.evolution = BehaviorEvolutionModel()
        self.observations: list[BehaviorObservation] = []
        self._default_archetype = default_archetype

    def get_or_create_profile(self, player_id: str, initial_archetype: Archetype | None = None) -> BehaviorProfile:
        if player_id not in self.profiles:
            arch = initial_archetype or self._default_archetype
            weights = {a: 0.05 for a in Archetype}
            weights[arch] = 0.65
            self.profiles[player_id] = BehaviorProfile(archetype_weights=weights, label=player_id)
        return self.profiles[player_id]

    def classify_from_state(self, state: dict[str, Any]) -> dict[str, float]:
        """Classify the most likely archetype from a state snapshot.

        Uses heuristic features: gold, inventory composition, achievement count.
        """
        gold = state.get("gold", 0)
        inventory = state.get("inventory", {}) or {}
        achievements = state.get("achievements", []) or []
        state.get("market", {}) or {}

        total_items = sum(inventory.values()) if isinstance(inventory, dict) else 0
        num_achievements = len(achievements) if isinstance(achievements, (list, dict)) else 0
        has_trade_items = any(
            str(k) in ("mystic_coin", "ectoplasm") and v > 5
            for k, v in inventory.items()
        ) if isinstance(inventory, dict) else False

        scores: dict[Archetype, float] = {}
        for archetype in Archetype:
            ARCHETYPE_SIGNATURES[archetype]
            score = 1.0

            if gold > 5000 and archetype == Archetype.TRADER:
                score += 2.0
            if gold < 100 and archetype == Archetype.GRINDER:
                score += 1.5
            if has_trade_items and archetype == Archetype.TRADER:
                score += 1.5
            if total_items > 50 and archetype == Archetype.CRAFTER:
                score += 1.0
            if num_achievements > 20 and archetype == Archetype.ACHIEVER:
                score += 2.0
            if total_items > 100 and archetype == Archetype.GRINDER:
                score += 1.0
            if gold > 2000 and archetype == Archetype.OPTIMIZER:
                score += 1.0
            if has_trade_items and archetype == Archetype.META_FOLLOWER:
                score += 0.5

            scores[archetype] = score

        total = sum(scores.values())
        if total > 0:
            scores = {k: round(v / total, 4) for k, v in scores.items()}
        return {k.value: v for k, v in scores.items()}

    def population_distribution(self) -> dict[str, float]:
        """Aggregate distribution across all known profiles."""
        if not self.profiles:
            return {}
        dist: dict[str, float] = {}
        for profile in self.profiles.values():
            dom = profile.dominant_archetype.value
            dist[dom] = dist.get(dom, 0.0) + 1.0
        total = sum(dist.values())
        if total > 0:
            dist = {k: v / total for k, v in dist.items()}
        return dist

    def observe(self, player_id: str, action_type: ActionType, reward: float, state: dict[str, Any]) -> BehaviorObservation:
        profile = self.get_or_create_profile(player_id)
        profile.update_from_observation(action_type, reward)

        obs = BehaviorObservation(
            timestamp=len(self.observations),
            action_type=action_type,
            reward=reward,
            state_snapshot=dict(state),
            archetype_scores=profile.archetype_mixture(),
        )
        self.observations.append(obs)
        return obs

    def evolve_all(self, meta_shift: float = 0.0, rng: random.Random | None = None) -> None:
        rng = rng or random.Random()
        evolved: dict[str, BehaviorProfile] = {}
        for player_id, profile in self.profiles.items():
            evolved[player_id] = self.evolution.evolve(profile, meta_shift=meta_shift, rng=rng)
        self.profiles = evolved

    def meta_shift_from_economy(self, economy: dict[str, Any]) -> float:
        """Infer meta shift magnitude from economy indicators."""
        inflation = economy.get("inflation_rate", 0.0)
        sentiment = economy.get("market_sentiment", 0.5)
        volatility = economy.get("average_volatility", 0.1)
        shift = abs(inflation - 0.02) * 5.0 + (0.5 - sentiment) * 2.0 + volatility * 3.0
        return min(1.0, max(0.0, shift))

    def to_dict(self) -> dict[str, Any]:
        return {
            "population_distribution": self.population_distribution(),
            "profile_count": len(self.profiles),
            "observation_count": len(self.observations),
            "profiles": {pid: p.to_dict() for pid, p in self.profiles.items()},
        }
