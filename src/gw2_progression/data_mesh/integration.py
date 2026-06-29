"""Data Mesh integration: bridges gw2radar production infrastructure with gw2-progression Expert AI training pipeline.

This module provides the GW2 Data Mesh v1 merge point:
  - DGSK: gw2radar DomainGraphEngine (YAML-based, validation, diff, compile-to-OOSK/BORS)
  - OOSK: gw2radar RuntimeStore + RuntimeMapper + MemoryGraph
  - BORS: gw2radar DecisionEngine + DecisionGraph + ValueGraph
  - KB:   gw2radar kb_models + kb_repository + kb_entity_linker
  - Training: gw2-progression TrainingPipeline (ETL -> simulation -> reasoning -> labeling)
"""

from __future__ import annotations

import uuid
from typing import Any

from gw2_progression.expert_ai.scheduler import ModelTrainer as LocalModelTrainer

HAS_GW2RADAR = False
try:
    from gw2radar.bors.decision_engine import DecisionEngine as RadarDecisionEngine
    from gw2radar.bors.decision_engine import DecisionFactor as RadarDecisionFactor
    from gw2radar.domain_graph.domain_engine import DomainGraphEngine as RadarDomainGraphEngine
    from gw2radar.oosk.runtime_store import RuntimeStore as RadarRuntimeStore
    HAS_GW2RADAR = True
except ImportError:
    RadarDomainGraphEngine = None
    RadarDecisionEngine = None


class DataMeshBridge:
    """Unified bridge — uses gw2radar production infra when available, falls back to local Expert AI.

    OpenCode execution contract:
      1. MultiSourceIngestion.ingest() -> raw streams
      2. SchemaNormalizer.normalize() -> unified DGSK structure
      3. DGSK Graph Builder (radar DomainGraphEngine) -> truth layer
      4. OOSK Runtime Sync (radar RuntimeMapper -> RuntimeStore) -> world state
      5. BORS Labeling (radar DecisionEngine) -> SELL/HOLD/BUY/CRAFT
      6. KB grounding (radar kb_models) -> reasoning support
      7. Training Dataset Factory -> self-learning flywheel
    """

    def __init__(self, use_radar: bool | None = None, api_key: str | None = None):
        self.use_radar = HAS_GW2RADAR if use_radar is None else (use_radar and HAS_GW2RADAR)
        self._api_key = api_key
        self._dgsk: Any = None
        self._oosk: Any = None
        self._bors: Any = None
        self._kb: Any = None

    # ── DGSK Layer ──────────────────────────────────────────────────────

    def get_dgsk_engine(self) -> Any:
        """Return DGSK engine: gw2radar DomainGraphEngine (production) or local fallback."""
        if self._dgsk is None:
            if self.use_radar:
                self._dgsk = RadarDomainGraphEngine()
            else:
                from gw2_progression.domain_graph.domain_engine import DomainGraphEngine as LocalDG
                self._dgsk = LocalDG()
        return self._dgsk

    def compile_domain_graph(self, yaml_path: str | None = None, yaml_dict: dict | None = None) -> dict[str, Any]:
        """Load, validate, and compile a domain graph (DGSK step)."""
        engine = self.get_dgsk_engine()
        if self.use_radar:
            if yaml_path:
                dg = engine.load_file(yaml_path)
            else:
                dg = engine._from_dict(yaml_dict or {})
            errors = engine.validate(dg)
            oosk_registry = engine.compile_to_oosk(dg) if not errors else None
            bors_mappings = engine.compile_to_bors(dg) if not errors else None
            return {
                "engine": "gw2radar",
                "id": str(uuid.uuid4()),
                "errors": errors or [],
                "dgsk": {"domain": dg.domain, "nodes": list(dg.nodes.keys()), "edges": list(dg.edges.keys())},
                "oosk_registry": oosk_registry,
                "bors_mappings": bors_mappings,
            }
        else:
            from pathlib import Path

            from gw2_progression.expert_ai.core import expert_ai

            return expert_ai.compile_graph(payload=yaml_dict, file_path=yaml_path or str(Path.cwd() / "domain_graph.yaml"))

    # ── OOSK Layer ──────────────────────────────────────────────────────

    def get_oosk_runtime(self) -> Any:
        """Return OOSK runtime: gw2radar RuntimeStore or local ExpertRuntime."""
        if self._oosk is None:
            if self.use_radar:
                self._oosk = RadarRuntimeStore()
            else:
                from gw2_progression.expert_ai.core import ExpertRuntime
                self._oosk = ExpertRuntime()
        return self._oosk

    def sync_oosk(self, entities: list[dict], relations: list[dict]) -> dict[str, Any]:
        """Sync entities/relations into OOSK runtime (step 3-5 of bootstrap)."""
        self.get_oosk_runtime()
        if self.use_radar:
            from gw2radar.graph import GraphData
            from gw2radar.graph.graph_builder import Entity, EntityType, Relation

            graph = GraphData()
            for e in entities:
                etype = e.get("type", "item").lower().replace(" ", "_")
                if etype not in {t.value for t in EntityType}:
                    etype = "item"
                graph.add_entity(Entity(
                    id=e["id"],
                    type=EntityType(etype),
                    canonical_name=e.get("properties", {}).get("name", e["id"]),
                    properties=e.get("properties", {}),
                ))
            from gw2radar.graph.graph_builder import RelationType as RadarRelationType
            valid_predicates = {t.value for t in RadarRelationType}
            for r in relations:
                rel_pred = r.get("relation_type", "related_to").lower()
                if rel_pred not in valid_predicates:
                    rel_pred = "related_to"
                predicate_val = rel_pred if rel_pred in valid_predicates else "requires"
                graph.add_relation(Relation(
                    id=str(uuid.uuid4()),
                    subject_id=r["source"],
                    predicate=predicate_val,
                    object_id=r["target"],
                    properties=r.get("properties", {}),
                ))
            snapshot_id = str(uuid.uuid4())
            return {"snapshot_id": snapshot_id, "entity_count": len(entities), "relation_count": len(relations), "engine": "gw2radar"}
        else:
            from gw2_progression.expert_ai.core import expert_ai

            for e in entities:
                expert_ai.runtime.add_entity(e)
            for r in relations:
                expert_ai.runtime.add_relation(r)
            snap = expert_ai.runtime.snapshot()
            return {"snapshot_id": snap.id, "entity_count": len(snap.entities), "relation_count": len(snap.relations), "engine": "local"}

    # ── BORS Layer ──────────────────────────────────────────────────────

    def get_bors_engine(self) -> Any:
        """Return BORS engine: gw2radar DecisionEngine or local DecisionEngine."""
        if self._bors is None:
            if self.use_radar:
                self._bors = RadarDecisionEngine()
            else:
                from gw2_progression.bors.business_decision import DecisionEngine as LocalDE
                self._bors = LocalDE()
        return self._bors

    def evaluate_decision(self, decision_type: str, factors: list[dict], metadata: dict | None = None) -> dict[str, Any]:
        """Evaluate a BORS decision with weighted factors."""
        engine = self.get_bors_engine()
        if self.use_radar:
            radar_factors = [
                RadarDecisionFactor(name=f["name"], value=float(f.get("value", 0)), weight=float(f.get("weight", 1)), impact=f.get("impact", ""))
                for f in factors
            ]
            result = engine.decide(decision_type, radar_factors)
            return {
                "decision": result.decision.value if hasattr(result.decision, "value") else str(result.decision),
                "score": result.score,
                "confidence": result.confidence,
                "reason": result.reason,
                "engine": "gw2radar",
            }
        else:
            from gw2_progression.expert_ai.core import expert_ai

            return expert_ai.evaluate_decision({"decision_type": decision_type, "factors": factors, "metadata": metadata or {}})

    # ── Knowledge Base ──────────────────────────────────────────────────

    def get_kb_status(self) -> dict[str, Any]:
        """Report KB availability and stats."""
        if self.use_radar:
            try:
                from gw2radar.kb.kb_repository import list_articles, list_rules, list_sources
                sources = list_sources()
                articles = list_articles()
                rules = list_rules()
                return {
                    "available": True,
                    "sources": len(sources),
                    "articles": len(articles),
                    "rules": len(rules),
                    "engine": "gw2radar",
                }
            except Exception as e:
                return {"available": False, "error": str(e), "engine": "gw2radar"}
        return {"available": False, "engine": "local"}

    def ground_reasoning_with_kb(self, reasoning_chain: list[dict]) -> list[dict]:
        """Ground a reasoning chain with KB rules/articles if available."""
        if self.use_radar:
            try:
                from gw2radar.kb.kb_repository import search_articles

                grounded = []
                for step in reasoning_chain:
                    kb_matches = search_articles(query=step.get("relation", ""), limit=3)
                    step["kb_grounding"] = [{"article_id": a.id, "title": a.title, "relevance": 0.8} for a in kb_matches[:2]] if kb_matches else []
                    grounded.append(step)
                return grounded
            except Exception:
                pass
        return reasoning_chain

    # ── Training Pipeline ───────────────────────────────────────────────

    def run_training(self, dataset: dict, model_type: str = "expert_reasoner", rounds: int = 3) -> list[dict[str, Any]]:
        """Run training rounds using local TrainingPipeline + ModelTrainer."""
        trainer = LocalModelTrainer()
        trained = []
        for rnd in range(1, rounds + 1):
            ds = dataset.copy()
            ds["model_type"] = model_type
            result = trainer.train(ds, model_type=model_type)
            trained.append({
                "round": rnd,
                "model_id": result["artifact"]["id"],
                "quality": result["metrics"]["estimated_quality"],
                "status": result["artifact"]["status"],
                "path": str(result["artifact"]["path"]),
            })
        return trained

    # ── Multi-Source Ingestion ──────────────────────────────────────────

    def multi_source_ingest(self, sources: list[dict]) -> list[dict]:
        """Unified multi-source ingestion via DataIngestion + SchemaNormalizer."""
        from gw2_progression.data_mesh.ingestion import DataIngestion
        from gw2_progression.data_mesh.schema.normalizer import SchemaNormalizer

        ingestion = DataIngestion(api_key=self._api_key)
        results = ingestion.ingest_multi(sources)
        outputs = []
        for r in results:
            entry = r.to_dict()
            if r.status in ("ok", "cached"):
                ds = SchemaNormalizer.normalize(r.raw_data, source_type=r.source_type)
                entry["normalized"] = ds.to_dict()
            outputs.append(entry)
        return outputs

    def run_pipeline(self, sources: list[dict], options: dict | None = None) -> dict:
        """Run the full DataMeshPipeline."""
        from gw2_progression.data_mesh.pipeline import DataMeshPipeline

        pipe = DataMeshPipeline(api_key=self._api_key)
        result = pipe.run(sources, options)
        return result.to_dict()

    @staticmethod
    def normalize(raw: dict) -> dict:
        """Legacy wrapper — delegates to SchemaNormalizer."""
        from gw2_progression.data_mesh.schema.normalizer import SchemaNormalizer
        ds = SchemaNormalizer.normalize(raw, source_type="legacy")
        return ds.to_dict()

    # ── Pipeline Status ─────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Full mesh status report."""
        dgsk_engine = "gw2radar" if self.use_radar else "local"
        kb = self.get_kb_status()
        return {
            "mesh_version": "v1",
            "dgsk_engine": dgsk_engine,
            "oosk_runtime": dgsk_engine,
            "bors_engine": dgsk_engine,
            "kb_available": kb.get("available", False),
            "kb_sources": kb.get("sources", 0),
            "kb_articles": kb.get("articles", 0),
            "kb_rules": kb.get("rules", 0),
        }


def check_mesh_health() -> dict[str, Any]:
    """Quick health check for the Data Mesh."""
    bridge = DataMeshBridge()
    return bridge.status()
