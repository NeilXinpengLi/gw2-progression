from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from gw2_progression.cognitive_os.probabilistic.bors import DecisionDistribution, ProbabilisticBORS
from gw2_progression.cognitive_os.probabilistic.causal import CausalChain, CausalReasoningLayer, CounterfactualResult
from gw2_progression.cognitive_os.probabilistic.dgsk import ProbabilisticDGSK
from gw2_progression.cognitive_os.probabilistic.gnn import RuleGNN
from gw2_progression.cognitive_os.probabilistic.policy import PolicyDistribution, ProbabilisticPolicy


@dataclass
class WorldSample:
    """A single world trajectory sample from the probabilistic inference loop."""
    world_id: str
    dgsk_sample: dict[str, Any]
    gnn_embeddings: dict[str, Any]
    trajectory: list[dict[str, Any]]
    decisions: list[DecisionDistribution]
    policy_distributions: list[list[PolicyDistribution]]
    causal_chains: list[CausalChain]
    total_reward: float
    total_uncertainty: float


class ProbabilisticWorldInferenceLoop:
    """The core closed-loop probabilistic world inference system.

    Implements the unified loop:
      1. Sample DGSK graph → probabilistic graph instance
      2. Run GNN inference → node embeddings → rules
      3. Sample behaviors → BehaviorProfile → action distributions
      4. Sample decisions → BORS distributions
      5. Simulate OOSK state evolution → trajectory
      6. Optimize RL policy → policy distributions
      7. LLM generates causal reasoning → chains + explanations
      8. Calibrate probabilities → adjust uncertainty
      9. Repeat for multi-world sampling

    This is the core of "multi-world probabilistic inference."
    """

    def __init__(
        self,
        num_worlds: int = 5,
        steps_per_world: int = 20,
        uncertainty_decay: float = 0.95,
    ) -> None:
        self.num_worlds = num_worlds
        self.steps_per_world = steps_per_world
        self.uncertainty_decay = uncertainty_decay

        self.dgsk = ProbabilisticDGSK()
        self.gnn = RuleGNN()
        self.bors = ProbabilisticBORS()
        self.policy = ProbabilisticPolicy()
        self.causal = CausalReasoningLayer()

        self.samples: list[WorldSample] = []
        self._step_count = 0
        self._world_counter = 0

    def set_simulator(self, simulator_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]) -> None:
        self._simulator = simulator_fn

    def set_action_sampler(self, sampler_fn: Callable[[dict[str, Any]], list[dict[str, Any]]]) -> None:
        self._action_sampler = sampler_fn

    def set_behavior_profile(self, profile_fn: Callable[[], dict[str, Any]] | None = None) -> None:
        self._behavior_profile_fn = profile_fn

    # ─── Main Loop ──────────────────────────────────────────────────

    def step(self, state: dict[str, Any]) -> dict[str, Any]:
        """Single step: run one round of the probabilistic inference loop."""
        self._step_count += 1

        dgsk_sample = self.dgsk.sample_graph()

        gnn_output = self.gnn.forward(dgsk_sample)

        behavioral_profile = {}
        if hasattr(self, '_behavior_profile_fn') and self._behavior_profile_fn:
            behavioral_profile = self._behavior_profile_fn() or {}

        bors_dist = self.bors.compute_decision_distribution(state, behavioral_profile)

        if hasattr(self, '_action_sampler') and self._action_sampler:
            available = self._action_sampler(state)
            state_key = f"s_{self._step_count}"
            policy_dist = self.policy.get_distribution(state_key, available)
        else:
            policy_dist = []

        reward = bors_dist.expected_value
        for pd_item in policy_dist:
            pass

        sampled_action_type = self.bors.sample_decision()
        causal_chains = self.causal.infer_causal_chain(dgsk_sample, "entity:character")

        target_uncertainty = self.dgsk.graph_uncertainty() * (self.uncertainty_decay ** self._step_count)

        return {
            "step": self._step_count,
            "dgsk_sample": dgsk_sample,
            "gnn_output": gnn_output,
            "bors_distribution": {
                "probabilities": bors_dist.probabilities,
                "expected_value": bors_dist.expected_value,
                "uncertainty": bors_dist.uncertainty,
                "sampled_decision": sampled_action_type,
            },
            "policy_distribution": [
                {
                    "action_type": p.action_type,
                    "item_id": p.item_id,
                    "probability": p.probability,
                    "q_value": p.q_value,
                }
                for p in policy_dist[:5]
            ],
            "causal_chains": [
                {
                    "chain_id": c.chain_id,
                    "chain": c.chain,
                    "confidence": c.confidence,
                }
                for c in causal_chains[:3]
            ],
            "target_uncertainty": round(target_uncertainty, 4),
            "reward": round(reward, 4),
        }

    def run_multi_world(self, initial_state: dict[str, Any]) -> list[WorldSample]:
        """Run multiple world simulations in parallel (conceptual).

        Each world gets its own probabilistic graph sample and trajectory.
        """
        self.samples = []

        for w in range(self.num_worlds):
            self._world_counter += 1
            world_id = f"world_{self._world_counter}"

            dgsk_sample = self.dgsk.sample_graph()

            gnn_output = self.gnn.forward(dgsk_sample)

            trajectory: list[dict[str, Any]] = []
            decisions: list[DecisionDistribution] = []
            policy_dists: list[list[PolicyDistribution]] = []
            state = dict(initial_state)
            total_reward = 0.0

            for _step in range(self.steps_per_world):
                bors_dist = self.bors.compute_decision_distribution(state)
                decisions.append(bors_dist)

                behavioral_profile_fn = getattr(self, '_behavior_profile_fn', None)
                behavioral_profile_fn() if behavioral_profile_fn else {}

                if hasattr(self, '_action_sampler') and self._action_sampler:
                    available = self._action_sampler(state)
                    state_key = f"w{self._world_counter}_s{_step}"
                    pdist = self.policy.get_distribution(state_key, available)
                    policy_dists.append(pdist)

                decision_type = self.bors.sample_decision()
                action = {"type": decision_type.lower(), "item_id": "gold", "quantity": 1}

                if hasattr(self, '_simulator'):
                    state = self._simulator(state, action)

                trajectory.append(dict(state))
                total_reward += bors_dist.expected_value

            causal_chains = self.causal.infer_causal_chain(dgsk_sample, "entity:character")

            sample = WorldSample(
                world_id=world_id,
                dgsk_sample=dgsk_sample,
                gnn_embeddings=gnn_output,
                trajectory=trajectory,
                decisions=decisions,
                policy_distributions=policy_dists,
                causal_chains=causal_chains,
                total_reward=round(total_reward, 4),
                total_uncertainty=round(self.dgsk.graph_uncertainty(), 4),
            )
            self.samples.append(sample)

        self.samples.sort(key=lambda s: -s.total_reward)
        return self.samples

    def best_world(self) -> WorldSample | None:
        """Return the highest-reward world sample."""
        if not self.samples:
            return None
        return max(self.samples, key=lambda s: s.total_reward)

    def world_diversity(self) -> float:
        """Measure diversity across world samples using trajectory variance."""
        if len(self.samples) < 2:
            return 0.0
        rewards = [s.total_reward for s in self.samples]
        mean_r = sum(rewards) / len(rewards)
        variance = sum((r - mean_r) ** 2 for r in rewards) / len(rewards)
        return round(math.sqrt(variance), 4)

    def counterfactual_query(
        self,
        state: dict[str, Any],
        original_action: dict[str, Any],
        alternative_action: dict[str, Any],
    ) -> CounterfactualResult:
        """Query: what if alternative action instead of original?"""
        sim_fn = getattr(self, '_simulator', None)
        if not sim_fn:
            raise ValueError("Simulator not set. Call set_simulator() first.")
        return self.causal.counterfactual(state, original_action, alternative_action, sim_fn)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": {
                "num_worlds": self.num_worlds,
                "steps_per_world": self.steps_per_world,
                "uncertainty_decay": self.uncertainty_decay,
            },
            "probabilistic_dgsk": self.dgsk.to_dict(),
            "gnn": self.gnn.to_dict(),
            "bors": self.bors.to_dict(),
            "policy": self.policy.to_dict(),
            "causal": self.causal.to_dict(),
            "world_samples": [
                {
                    "world_id": s.world_id,
                    "total_reward": s.total_reward,
                    "total_uncertainty": s.total_uncertainty,
                    "trajectory_length": len(s.trajectory),
                    "decision_count": len(s.decisions),
                    "causal_chain_count": len(s.causal_chains),
                    "dgsk_node_count": len(s.dgsk_sample.get("nodes", {})),
                    "dgsk_edge_count": len(s.dgsk_sample.get("edges", [])),
                }
                for s in self.samples
            ],
            "world_diversity": self.world_diversity(),
            "best_world": self.best_world().world_id if self.best_world() else None,
            "total_steps": self._step_count,
        }
