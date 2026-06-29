"""GW2 Data Mesh v1 — data ingestion, normalization, confidence, and pipeline orchestration.

Architecture:
  External Sources (GW2 API / gw2radar / wiki / reddit / efficiency)
    -> DataIngestion Layer
    -> SchemaNormalizer (DGSK standard format)
    -> ConfidenceSystem (per-source confidence evaluation)
    -> DGSK Graph Builder (gw2radar DomainGraphEngine)
    -> OOSK Runtime Sync Engine (gw2radar RuntimeStore + RuntimeMapper)
    -> BORS Labeling Engine (gw2radar DecisionEngine)
    -> Knowledge Base (gw2radar KB articles + chunks + rules)
    -> DataMeshPipeline (full orchestration)
    -> Reasoning Dataset Generator
    -> Self-Learning Flywheel
"""

from __future__ import annotations

from gw2_progression.data_mesh.ingestion import DataIngestion, IngestResult
from gw2_progression.data_mesh.integration import DataMeshBridge, check_mesh_health
from gw2_progression.data_mesh.pipeline import DataMeshPipeline, PipelineResult, PipelineStage
from gw2_progression.data_mesh.schema.confidence import ConfidenceRecord, ConfidenceSystem
from gw2_progression.data_mesh.schema.normalizer import DGSKStructure, SchemaNormalizer
from gw2_progression.data_mesh.sources.registry import (
    BUILTIN_SOURCES,
    AllowedUse,
    CrawlPolicy,
    KBDomain,
    KnowledgeArticle,
    KnowledgeSource,
    SourceRegistry,
    SourceType,
)

__all__ = [
    "DataIngestion",
    "IngestResult",
    "DataMeshPipeline",
    "PipelineResult",
    "PipelineStage",
    "DataMeshBridge",
    "check_mesh_health",
    "SourceType",
    "AllowedUse",
    "CrawlPolicy",
    "KBDomain",
    "KnowledgeSource",
    "KnowledgeArticle",
    "SourceRegistry",
    "BUILTIN_SOURCES",
    "SchemaNormalizer",
    "DGSKStructure",
    "ConfidenceSystem",
    "ConfidenceRecord",
]
