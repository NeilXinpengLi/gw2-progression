from __future__ import annotations

import random
import time
from typing import Any

from gw2_progression.cognitive_os.agents.base import BaseAgent
from gw2_progression.cognitive_os.agents.crafter import CrafterAgent
from gw2_progression.cognitive_os.agents.meta import MetaAgent
from gw2_progression.cognitive_os.agents.raider import RaiderAgent
from gw2_progression.cognitive_os.agents.trader import TraderAgent
from gw2_progression.cognitive_os.behavior import Archetype, BehaviorModel
from gw2_progression.cognitive_os.calibration import CalibrationLoop
from gw2_progression.cognitive_os.cognition_graph.graph import CognitionGraph, EdgeType, NodeType
from gw2_progression.cognitive_os.economy.lifecycle import EconomicLifecycle
from gw2_progression.cognitive_os.probabilistic import (
    CausalReasoningLayer,
    ProbabilisticBORS,
    ProbabilisticDGSK,
    ProbabilisticPolicy,
    ProbabilisticWorldInferenceLoop,
    RuleGNN,
)
from gw2_progression.cognitive_os.rl.learning_loop import LearningLoop
from gw2_progression.cognitive_os.rl.policy import RLPolicy
from gw2_progression.cognitive_os.rl.reward import RewardFunction
from gw2_progression.cognitive_os.temporal.temporal_state import TemporalState
from gw2_progression.data_acquisition import (
    DataFactory,
    DatasetBuilder,
    DGSKGraphBuilder,
    HorizontalExpander,
    IngestionOrchestrator,
    SourceRegistry,
    StreamEngine,
    SyntheticExpander,
    TaskScheduler,
    TemporalExpander,
    VerticalExpander,
)
from gw2_progression.lifecycle.core.backward.dependency_solver import DependencySolver
from gw2_progression.lifecycle.core.engine import LifecycleEngine
from gw2_progression.lifecycle.core.forward.state_evolver import StateEvolver
from gw2_progression.lifecycle.core.rules.crafting_rules import CraftingRules
from gw2_progression.lifecycle.core.rules.dgsk_constraints import DGSKConstraints
from gw2_progression.lifecycle.core.rules.economy_rules import EconomyRules
from gw2_progression.lifecycle.core.validation.consistency_checker import ConsistencyChecker


class CognitiveOSEngine:
    """GW2 Cognitive OS v1.0 — Unified system orchestrator.

    Integrates:
      - TemporalState (unified time axis)
      - CognitionGraph (time-aware semantic graph)
      - DGSK (world structure: entities + relations + constraints)
      - OOSK (runtime simulation: state evolution)
      - BORS (decision layer: KPI → decision)
      - RL (self-improving policies)
      - Multi-Agent system (trader, crafter, raider, meta)
      - Economy lifecycle (supply/demand/meta dynamics)
      - Behavior Distribution Engine (archetype distributions)
      - Probabilistic World Model (multi-world inference)
      - Simulation Calibration Loop (closed-loop adjustment)
      - GNN Rule Induction (graph structure learning)
      - LLM Causal Reasoning Layer
    """

    def __init__(self) -> None:
        self.temporal = TemporalState()
        self.cognition = CognitionGraph()
        self.economy = EconomicLifecycle()
        self.policy = RLPolicy()
        self.reward_fn = RewardFunction()
        self.learning_loop = LearningLoop(policy=self.policy, reward_fn=self.reward_fn)

        # Probabilistic layers
        self.behavior_model = BehaviorModel()
        self.calibration = CalibrationLoop()
        self.probabilistic_dgsk = ProbabilisticDGSK()
        self.probabilistic_gnn = RuleGNN()
        self.probabilistic_bors = ProbabilisticBORS()
        self.probabilistic_policy = ProbabilisticPolicy()
        self.probabilistic_causal = CausalReasoningLayer()
        self.probabilistic_world = ProbabilisticWorldInferenceLoop()

        # Data Acquisition OS
        self.source_registry = SourceRegistry()
        self.horizontal_expander = HorizontalExpander()
        self.vertical_expander = VerticalExpander()
        self.temporal_expander = TemporalExpander()
        self.synthetic_expander = SyntheticExpander()
        self.graph_builder = DGSKGraphBuilder()
        self.stream_engine = StreamEngine()
        self.task_scheduler = TaskScheduler(registry=self.source_registry)
        self.ingestion_orchestrator = IngestionOrchestrator(registry=self.source_registry)
        self.dataset_builder = DatasetBuilder()
        self.data_factory = DataFactory(
            source_registry=self.source_registry,
            ingestion_orchestrator=self.ingestion_orchestrator,
            graph_builder=self.graph_builder,
            stream_engine=self.stream_engine,
            task_scheduler=self.task_scheduler,
            dataset_builder=self.dataset_builder,
        )

        self.solver = DependencySolver()
        self.solver.register_account_dependencies()
        self.evolver = StateEvolver(solver=self.solver)
        self.constraints = DGSKConstraints()
        self.crafting = CraftingRules()
        self.economy_rules = EconomyRules()
        self.consistency = ConsistencyChecker()
        self.lifecycle = LifecycleEngine()

        self.agents: dict[str, BaseAgent] = {}
        self._initialized = False
        self._simulation_count = 0

    def initialize(self, initial_state: dict[str, Any] | None = None) -> None:
        self.temporal.reset(initial_state)
        self._build_cognition_graph(initial_state)
        self._register_default_agents()
        self._register_economy_items(initial_state)

        # Wire probabilistic world loop
        self.probabilistic_world.set_simulator(lambda s, a: self.evolver.evolve(s, a))
        self.probabilistic_world.set_action_sampler(self._sample_available_actions)

        # Register default behavior profile
        self.behavior_model.get_or_create_profile("default", Archetype.OPTIMIZER)

        # Merge CognitionGraph into ProbabilisticDGSK
        self.probabilistic_dgsk.merge_with_cognition_graph(self.cognition)

        # Wire Data Acquisition OS expansion hooks
        def expansion_hook(data, source):
            data = self.horizontal_expander.expand(data, source)
            data = self.vertical_expander.expand(data, source)
            data = self.temporal_expander.expand(data, source)
            data = self.synthetic_expander.expand(data, source)
            return data
        self.ingestion_orchestrator.register_expansion_hook(expansion_hook)

        # Wire graph builder hook
        def graph_hook(data):
            self.graph_builder.build(data)

            # Feed entities into behavior model
            for entity in data.get("entities", []):
                etype = entity.get("type", "")
                if etype in ("synthetic_agent", "behavior"):
                    self.behavior_model.get_or_create_profile(
                        entity.get("id", "unknown"),
                    )

            # Feed into probabilistic DGSK
            for entity in data.get("entities", []):
                eid = entity.get("id", "")
                etype = entity.get("type", "entity")
                if eid and eid not in self.probabilistic_dgsk.nodes:
                    self.probabilistic_dgsk.add_node(eid, etype, entity.get("properties", {}))

            for relation in data.get("relations", []):
                src = relation.get("source", "")
                tgt = relation.get("target", "")
                rel = relation.get("relation", "related_to")
                if src and tgt:
                    self.probabilistic_dgsk.add_edge(
                        src, tgt, rel,
                        probability=relation.get("confidence", 0.8),
                    )

        self.ingestion_orchestrator.register_graph_hook(graph_hook)

        # Wire DataFactory hooks to engine methods
        self.data_factory._simulate_fn = lambda: self.step()
        self.data_factory._infer_fn = lambda: self.classify_behavior()
        self.data_factory._graph_to_dgsk_fn = lambda: self._sync_dgsk_from_cognition()

        # Register scheduler handlers
        def ingest_handler(source):
            self.ingestion_orchestrator.ingest_source(source)

        for source in self.source_registry.get_enabled():
            self.task_scheduler.register_handler(source.id, ingest_handler)

        self._initialized = True

    def _sync_dgsk_from_cognition(self) -> None:
        self.probabilistic_dgsk.merge_with_cognition_graph(self.cognition)

    def _build_cognition_graph(self, state: dict[str, Any] | None) -> None:
        g = self.cognition
        state = state or {}

        entity_node = g.add_node(NodeType.ENTITY, "character", {
            "gold": state.get("gold", 0),
            "items": len(state.get("inventory", {}) or {}),
        }, node_id="entity:character")
        state_node = g.add_node(NodeType.STATE, "world_state", {
            "t": 0,
            "achievements": len(state.get("achievements", []) or []),
        }, node_id="state:world")
        goal_node = g.add_node(NodeType.GOAL, "progression", {}, node_id="goal:progression")
        decision_node = g.add_node(NodeType.DECISION, "initial_decision", {}, node_id="decision:init")

        g.add_edge(entity_node, state_node, EdgeType.EVOLVES_TO, weight=1.0)
        g.add_edge(state_node, decision_node, EdgeType.INFLUENCES, weight=0.5)
        g.add_edge(decision_node, entity_node, EdgeType.CHANGES, weight=1.0)
        g.add_edge(entity_node, goal_node, EdgeType.DEPENDS_ON, weight=1.0)
        g.add_edge(goal_node, decision_node, EdgeType.CAUSES, weight=0.8)

    def _register_default_agents(self) -> None:
        self.agents["trader"] = TraderAgent(capital=1000.0)
        self.agents["crafter"] = CrafterAgent(skill_level=0.7)
        self.agents["raider"] = RaiderAgent(skill_level=0.8)
        self.agents["meta"] = MetaAgent(skill_level=0.85)

    def _register_economy_items(self, state: dict[str, Any] | None) -> None:
        inv = (state or {}).get("inventory", {}) or {}
        for item_id, _count in inv.items():
            self.economy.register_item(
                str(item_id),
                initial_price=random.uniform(10, 1000),
                volatility=random.uniform(0.05, 0.3),
            )

    def step(self, action: dict[str, Any] | None = None) -> dict[str, Any]:
        state = self.temporal.current
        if action is None:
            action = self._select_next_action(state)

        new_state = self.evolver.evolve(state, action)
        reward_components = self.reward_fn.compute(state, new_state, action)
        validations = new_state.get("_action_validations", [])

        self.temporal.apply_transition(new_state, action)
        self.economy.step()

        self._update_cognition_graph(action, reward_components.total, validations)

        return {
            "t": self.temporal.t,
            "action": action,
            "state": new_state,
            "reward": reward_components.total,
            "reward_components": {
                "economic_gain": reward_components.economic_gain,
                "progression_efficiency": reward_components.progression_efficiency,
                "reasoning_accuracy": reward_components.reasoning_accuracy,
                "instability": reward_components.instability,
            },
            "validations": validations,
            "economy": self.economy.to_dict(),
        }

    def _select_next_action(self, state: dict[str, Any]) -> dict[str, Any]:
        available = self._sample_available_actions(state)
        chosen = self.policy.select_action(state, available)
        if chosen:
            return chosen
        return available[0] if available else {"type": "farm", "item_id": "gold", "quantity": 1}

    def _sample_available_actions(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        inventory = state.get("inventory", {}) or {}
        market = state.get("market", {}) or {}
        actions: list[dict[str, Any]] = []

        for item_id, count in list(inventory.items())[:10]:
            sid = str(item_id)
            if count > 0:
                actions.append({"type": "farm", "item_id": sid, "quantity": min(count, 5)})
            if sid in market:
                actions.append({"type": "trade", "item_id": sid, "quantity": min(count, 5)})
        if not actions:
            actions.append({"type": "farm", "item_id": "gold", "quantity": 1})
        return actions

    def _update_cognition_graph(self, action: dict[str, Any], reward: float, validations: list[dict[str, Any]]) -> None:
        g = self.cognition
        t = self.temporal.t

        action_node = g.add_node(
            NodeType.ACTION,
            f"{action.get('type', 'unknown')}:{action.get('item_id', '')}",
            {"reward": reward, "valid": any(v.get("valid", False) for v in validations) if validations else True},
            t_created=t,
        )
        state_node = "state:world"
        decision_node = "decision:init"
        entity_node = "entity:character"

        g.add_edge(action_node, state_node, EdgeType.CHANGES, weight=reward, t_created=t)
        g.add_edge(decision_node, action_node, EdgeType.CAUSES, weight=0.5, t_created=t)

        if reward > 0.5:
            g.add_edge(action_node, entity_node, EdgeType.PRODUCES, weight=reward, t_created=t)

    def simulate_episode(self, max_steps: int = 50) -> dict[str, Any]:
        return self.learning_loop.run_episode(
            initial_state=dict(self.temporal.current),
            action_sampler=self._sample_available_actions,
            simulator=lambda s, a: self.evolver.evolve(s, a),
            max_steps=max_steps,
        )

    def train(self, episodes: int = 100, max_steps: int = 50, verbose: bool = True) -> dict[str, Any]:
        def factory() -> dict[str, Any]:
            return dict(self.temporal.current or {})

        return self.learning_loop.train(
            initial_state_factory=factory,
            action_sampler=self._sample_available_actions,
            simulator=lambda s, a: self.evolver.evolve(s, a),
            episodes=episodes,
            max_steps_per_episode=max_steps,
            verbose=verbose,
        )

    def agent_interact(self, world_state: dict[str, Any]) -> dict[str, Any]:
        actions: dict[str, Any] = {}
        combined_state = dict(world_state)

        for agent_name, agent in self.agents.items():
            action = agent.act(combined_state)
            actions[agent_name] = {
                "action_type": action.action_type,
                "item_id": action.item_id,
                "quantity": action.quantity,
                "params": action.params,
            }
            step_action = {
                "type": action.action_type,
                "item_id": action.item_id or "",
                "quantity": action.quantity,
                **(action.params or {}),
            }
            combined_state = self.evolver.evolve(combined_state, step_action)
            reward_comp = self.reward_fn.compute(world_state, combined_state, step_action)
            agent.observe(combined_state, action, reward_comp.total)

        self.temporal.apply_transition(combined_state, {"type": "multi_agent", "agents": list(actions.keys())})
        return {
            "t": self.temporal.t,
            "agents": actions,
            "state": combined_state,
            "agent_profiles": {name: ag.to_dict() for name, ag in self.agents.items()},
            "economy": self.economy.to_dict(),
        }

    def run_simulation(
        self,
        initial_state: dict[str, Any] | None = None,
        steps: int = 20,
        mode: str = "auto",
    ) -> dict[str, Any]:
        self._simulation_count += 1
        if initial_state:
            self.initialize(initial_state)

        trajectory: list[dict[str, Any]] = []
        for _step in range(steps):
            if mode == "multi_agent":
                result = self.agent_interact(self.temporal.current)
            else:
                result = self.step()
            trajectory.append(result)

        final_state = trajectory[-1]["state"] if trajectory else {}
        total_reward = sum(s.get("reward", 0) for s in trajectory)
        return {
            "simulation_id": self._simulation_count,
            "steps": steps,
            "mode": mode,
            "total_reward": round(total_reward, 3),
            "final_t": self.temporal.t,
            "trajectory": trajectory,
            "final_state": final_state,
            "cognition_graph": self.cognition.to_dict(),
            "economy": self.economy.to_dict(),
            "policy": self.policy.to_dict(),
            "learning": self.learning_loop.status(),
            "consistency": self.consistency.match_ratio(final_state, self.temporal.current) if self.temporal.current else 0,
        }

    def analyze(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = state or self.temporal.current
        return {
            "t": self.temporal.t,
            "cognition_graph": self.cognition.to_dict(),
            "economy": self.economy.market_health(),
            "policy": self.policy.to_dict(),
            "learning": self.learning_loop.status(),
            "agents": {name: ag.to_dict() for name, ag in self.agents.items()},
            "temporal": {
                "age": self.temporal.age,
                "trajectory_length": self.temporal.trajectory_length(),
            },
            "state_summary": {
                "gold": state.get("gold", 0),
                "inventory_size": len(state.get("inventory", {}) or {}),
                "achievements": len(state.get("achievements", []) or []),
                "validation_count": len(state.get("_action_validations", [])),
            },
        }

    def probabilistic_step(self) -> dict[str, Any]:
        """Run one step of the probabilistic world inference loop."""
        state = self.temporal.current
        return self.probabilistic_world.step(state)

    def run_multi_world(self, num_worlds: int | None = None, steps: int | None = None) -> dict[str, Any]:
        """Run multi-world probabilistic simulation."""
        self.probabilistic_world.num_worlds = num_worlds or self.probabilistic_world.num_worlds
        self.probabilistic_world.steps_per_world = steps or self.probabilistic_world.steps_per_world
        samples = self.probabilistic_world.run_multi_world(self.temporal.current)
        return {
            "world_count": len(samples),
            "best_world_id": self.probabilistic_world.best_world().world_id if self.probabilistic_world.best_world() else None,
            "world_diversity": self.probabilistic_world.world_diversity(),
            "worlds": [
                {
                    "world_id": s.world_id,
                    "total_reward": s.total_reward,
                    "total_uncertainty": s.total_uncertainty,
                    "trajectory_length": len(s.trajectory),
                }
                for s in samples
            ],
            "probabilistic_state": self.probabilistic_world.to_dict(),
        }

    def calibrate(self, target_state: dict[str, Any] | None = None) -> dict[str, Any]:
        """Calibrate simulation against a target (API) state."""
        simulated = self.temporal.current
        real = target_state or simulated
        obs = self.calibration.observe(simulated, real)

        state = self.temporal.current
        if state:
            calibrated = self.calibration.apply_to_state(state)
            self.temporal.apply_transition(calibrated, {"type": "calibration"})

        following_states: dict[str, float] = {}
        for m in obs.metrics:
            following_states[m.name] = round(m.absolute_error, 4)

        return {
            "loss": obs.total_loss,
            "metrics": following_states,
            "parameters": dict(self.calibration.parameters),
            "calibration_state": self.calibration.to_dict(),
        }

    def classify_behavior(self) -> dict[str, Any]:
        """Classify the current state's archetype distribution."""
        state = self.temporal.current
        scores = self.behavior_model.classify_from_state(state)
        profile = self.behavior_model.get_or_create_profile("default")
        return {
            "archetype_scores": scores,
            "dominant_archetype": max(scores, key=scores.get) if scores else "unknown",
            "profile": profile.to_dict(),
            "population": self.behavior_model.population_distribution(),
        }

    def counterfactual_query(
        self,
        original_action: dict[str, Any],
        alternative_action: dict[str, Any],
    ) -> dict[str, Any]:
        """What-if analysis."""
        state = self.temporal.current
        result = self.probabilistic_world.counterfactual_query(state, original_action, alternative_action)
        return {
            "question": result.question,
            "actual_outcome": result.actual_outcome,
            "counterfactual_outcome": result.counterfactual_outcome,
            "delta": result.delta,
            "confidence": result.confidence,
        }

    def gnn_induction(self) -> dict[str, Any]:
        """Run GNN rule induction on the cognition graph."""
        graph_data = self.cognition.to_dict()
        return self.probabilistic_gnn.forward(graph_data)

    # ─── Data Acquisition OS Methods ────────────────────────────────

    def ingest_source(self, source_id: str | None = None) -> dict[str, Any]:
        """Ingest data from a specific or all sources."""
        if source_id:
            source = self.source_registry.get(source_id)
            if not source:
                return {"status": "error", "message": f"Unknown source: {source_id}"}
            result = self.ingestion_orchestrator.ingest_source(source)
        else:
            results = self.ingestion_orchestrator.ingest_all()
            result = results[-1] if results else None

        return {
            "status": "completed" if result and result.success else "failed",
            "source_id": source_id or "all",
            "entities": result.total_entities if result else 0,
            "relations": result.total_relations if result else 0,
            "duration_ms": result.duration_ms if result else 0,
            "orchestrator": self.ingestion_orchestrator.to_dict(),
        }

    def run_scheduler(self) -> dict[str, Any]:
        """Run pending scheduled tasks."""
        results = self.task_scheduler.run_pending(time.time())
        return {
            "tasks_run": len(results),
            "results": results,
            "scheduler": self.task_scheduler.to_dict(),
        }

    def stream_data(self, source_id: str, data_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Push data into the streaming engine."""
        self.stream_engine.push_data(source_id, data_type, data)
        return self.stream_engine.to_dict()

    def flush_stream(self) -> dict[str, Any]:
        """Manually flush the stream buffer."""
        flushed = self.stream_engine.flush()
        return {
            "flushed_count": len(flushed),
            "stream": self.stream_engine.to_dict(),
        }

    def get_graph_builder_status(self) -> dict[str, Any]:
        return self.graph_builder.to_dict()

    def get_source_registry(self) -> dict[str, Any]:
        return self.source_registry.to_dict()

    def register_source(self, config: dict[str, Any]) -> dict[str, Any]:
        source = self.source_registry.register(config)
        return {"status": "registered", "source": source.to_dict()}

    # ─── Data Factory Methods ───────────────────────────────────────

    def run_flywheel(self, iterations: int = 1) -> dict[str, Any]:
        """Run the autonomous data flywheel."""
        self.data_factory.start()
        results = self.data_factory.run_flywheel(iterations=iterations)
        return {
            "iterations_run": len(results),
            "flywheel": self.data_factory.flywheel.to_dict(),
            "datasets": self.dataset_builder.to_dict(),
        }

    def factory_status(self) -> dict[str, Any]:
        """Get the data factory status report."""
        return self.data_factory.status_report()

    def generate_datasets(self) -> dict[str, Any]:
        """Build training datasets from current state."""
        state = self.temporal.current
        archetype_scores = self.behavior_model.classify_from_state(state)
        economy_state = self.economy.to_dict() if hasattr(self.economy, 'to_dict') else {}

        self.dataset_builder.build_behavior_dataset(state, archetype_scores, self._simulation_count)
        self.dataset_builder.build_economy_dataset(economy_state, self._simulation_count)
        saved = self.dataset_builder.save_all()

        return {
            "datasets_saved": saved,
            "total_samples": self.dataset_builder.total_samples(),
            "dataset_builder": self.dataset_builder.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "initialized": self._initialized,
            "t": self.temporal.t,
            "cognition_graph": self.cognition.to_dict(),
            "economy": self.economy.market_health(),
            "policy": self.policy.to_dict(),
            "learning": self.learning_loop.status(),
            "agents": {name: ag.to_dict() for name, ag in self.agents.items()},
            "behavior_model": self.behavior_model.to_dict(),
            "calibration": self.calibration.to_dict(),
            "probabilistic": self.probabilistic_world.to_dict(),
            "data_acquisition": {
                "source_registry": self.source_registry.to_dict(),
                "graph_builder": self.graph_builder.to_dict(),
                "stream": self.stream_engine.to_dict(),
                "scheduler": self.task_scheduler.to_dict(),
            },
            "data_factory": self.data_factory.status_report(),
        }


_cognitive_os: CognitiveOSEngine | None = None


def get_cognitive_os() -> CognitiveOSEngine:
    global _cognitive_os
    if _cognitive_os is None:
        _cognitive_os = CognitiveOSEngine()
    return _cognitive_os
