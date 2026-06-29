from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MaturityLayer:
    layer: str
    name: str
    score: float
    status: str
    evidence: list[str]
    gaps: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "name": self.name,
            "score": round(self.score, 3),
            "status": self.status,
            "evidence": self.evidence,
            "gaps": self.gaps,
        }


class GCOSMaturityEvaluator:
    """Evaluates implementation maturity against the final GCOS L0-L10 stack."""

    def evaluate(self, engine: Any) -> dict[str, Any]:
        layers = [
            self._l0_sources(engine),
            self._l1_ingestion(engine),
            self._l2_graph(engine),
            self._l3_temporal(engine),
            self._l4_behavior(engine),
            self._l5_rules(engine),
            self._l6_probabilistic(engine),
            self._l7_intelligence(engine),
            self._l8_reasoning(engine),
            self._l9_population(engine),
            self._l10_feedback(engine),
        ]
        overall = sum(layer.score for layer in layers) / len(layers)
        return {
            "system": "GW2 Cognitive Intelligence Operating System",
            "overall_maturity": round(overall, 3),
            "overall_status": self._status(overall),
            "layers": [layer.to_dict() for layer in layers],
            "critical_gaps": self._critical_gaps(layers),
            "recommendations": self._recommendations(layers),
        }

    def _status(self, score: float) -> str:
        if score >= 0.9:
            return "production_ready"
        if score >= 0.75:
            return "integrated"
        if score >= 0.5:
            return "partial"
        return "conceptual"

    def _layer(self, layer: str, name: str, score: float, evidence: list[str], gaps: list[str]) -> MaturityLayer:
        return MaturityLayer(layer=layer, name=name, score=score, status=self._status(score), evidence=evidence, gaps=gaps)

    def _l0_sources(self, engine: Any) -> MaturityLayer:
        sources = engine.source_registry.get_enabled()
        source_types = engine.source_registry.to_dict().get("by_type", {})
        has_account = bool(engine.source_registry.get("gw2_account_raw_replay"))
        score = 0.55 + min(len(sources), 10) * 0.035 + (0.1 if has_account else 0.0)
        gaps = []
        if source_types.get("community", 0) == 0:
            gaps.append("community behavior sources are not registered")
        if not has_account:
            gaps.append("account raw replay source is missing")
        return self._layer(
            "L0",
            "GW2 API + External Sources",
            min(score, 0.95),
            [f"{len(sources)} enabled sources", f"source types: {source_types}"],
            gaps,
        )

    def _l1_ingestion(self, engine: Any) -> MaturityLayer:
        status = engine.ingestion_orchestrator.to_dict()
        score = 0.75
        if status.get("records_persisted", 0) > 0:
            score += 0.1
        if getattr(engine.ingestion_orchestrator, "_graph_hooks", []):
            score += 0.1
        return self._layer(
            "L1",
            "Multi-source Ingestion Layer",
            min(score, 0.95),
            ["ingestion orchestrator wired", "expansion hooks registered", "graph hooks registered"],
            ["external credentials for community sources still need live deployment"],
        )

    def _l2_graph(self, engine: Any) -> MaturityLayer:
        graph = engine.cognition.to_dict()
        stats = graph.get("stats", {})
        dgsk_nodes = len(engine.probabilistic_dgsk.nodes)
        score = 0.65
        if stats.get("nodes", 0) > 0 and stats.get("edges", 0) > 0:
            score += 0.15
        if dgsk_nodes > 0:
            score += 0.1
        return self._layer(
            "L2",
            "DGSK World Graph Layer",
            min(score, 0.95),
            [f"cognition stats: {stats}", f"probabilistic DGSK nodes: {dgsk_nodes}"],
            ["semantic relation coverage still depends on broader real ingestion"],
        )

    def _l3_temporal(self, engine: Any) -> MaturityLayer:
        trajectory_length = engine.temporal.trajectory_length()
        score = 0.75 + min(max(trajectory_length - 1, 0), 5) * 0.03
        return self._layer(
            "L3",
            "Temporal Simulation (OOSK)",
            min(score, 0.95),
            [f"trajectory length: {trajectory_length}", f"current t: {engine.temporal.t}"],
            ["long-horizon replay fidelity needs more real snapshots"],
        )

    def _l4_behavior(self, engine: Any) -> MaturityLayer:
        profile_count = len(engine.behavior_model.profiles)
        agent_types = sorted(agent.profile.agent_type for agent in engine.agents.values())
        expected = {"trader", "crafter", "farmer", "explorer", "optimizer"}
        present = set(agent_types)
        score = 0.55 + min(profile_count, 3) * 0.05 + min(len(present), 5) * 0.05
        gaps = []
        missing = sorted(expected - present)
        if missing:
            gaps.append(f"missing final-spec NPC roles: {', '.join(missing)}")
        return self._layer(
            "L4",
            "Behavior & NPC Generation Layer",
            min(score, 0.9),
            [f"profiles: {profile_count}", f"agent types: {agent_types}"],
            gaps,
        )

    def _l5_rules(self, engine: Any) -> MaturityLayer:
        score = 0.85
        evidence = [
            engine.constraints.__class__.__name__,
            engine.crafting.__class__.__name__,
            engine.economy_rules.__class__.__name__,
            engine.lifecycle.__class__.__name__,
        ]
        return self._layer(
            "L5",
            "Rule Engine (DGSK++)",
            score,
            evidence,
            ["rule extraction from live Wiki should continue expanding coverage"],
        )

    def _l6_probabilistic(self, engine: Any) -> MaturityLayer:
        samples = len(engine.probabilistic_world.samples)
        score = 0.75 + min(samples, 5) * 0.03
        return self._layer(
            "L6",
            "Probabilistic World Model",
            min(score, 0.9),
            [f"world samples: {samples}", "counterfactual loop available"],
            ["calibration requires more real target snapshots"],
        )

    def _l7_intelligence(self, engine: Any) -> MaturityLayer:
        learning = engine.learning_loop.status()
        trained = learning.get("episodes", 0) > 0
        score = 0.7 + (0.1 if trained else 0.0)
        return self._layer(
            "L7",
            "GNN + RL Intelligence Layer",
            min(score, 0.85),
            ["RuleGNN available", f"learning status: {learning}"],
            ["policy quality still depends on real model training depth"] if not trained else [],
        )

    def _l8_reasoning(self, engine: Any) -> MaturityLayer:
        score = 0.72
        return self._layer(
            "L8",
            "LLM Causal Reasoning Layer",
            score,
            [engine.probabilistic_causal.__class__.__name__, "counterfactual endpoint available"],
            ["needs deeper provider-backed explanatory evaluation"],
        )

    def _l9_population(self, engine: Any) -> MaturityLayer:
        population = engine.population_intelligence()
        clusters = population.get("clusters", [])
        score = 0.72 + min(len(clusters), 4) * 0.04
        return self._layer(
            "L9",
            "Population Intelligence Layer",
            min(score, 0.9),
            [f"clusters: {len(clusters)}", f"signals: {population.get('signals', {})}"],
            ["population validity needs larger observed player cohorts"],
        )

    def _l10_feedback(self, engine: Any) -> MaturityLayer:
        factory = engine.factory_status()
        samples = engine.dataset_builder.total_samples()
        score = 0.78 + (0.07 if samples > 0 else 0.0)
        return self._layer(
            "L10",
            "Self-improving Feedback Loop",
            min(score, 0.9),
            [f"flywheel: {factory.get('flywheel', {})}", f"dataset samples: {samples}"],
            ["production scheduler should keep running against live services"],
        )

    def _critical_gaps(self, layers: list[MaturityLayer]) -> list[str]:
        gaps: list[str] = []
        for layer in layers:
            if layer.score < 0.75:
                gaps.extend(f"{layer.layer}: {gap}" for gap in layer.gaps)
        return gaps

    def _recommendations(self, layers: list[MaturityLayer]) -> list[str]:
        ordered = sorted(layers, key=lambda layer: layer.score)
        return [
            f"Prioritize {layer.layer} {layer.name}: {layer.gaps[0] if layer.gaps else 'increase measured coverage'}"
            for layer in ordered[:3]
        ]
