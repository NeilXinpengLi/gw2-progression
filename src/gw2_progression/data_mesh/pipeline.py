from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from gw2_progression.data_mesh.ingestion import DataIngestion, IngestResult
from gw2_progression.data_mesh.schema.confidence import ConfidenceRecord, ConfidenceSystem
from gw2_progression.data_mesh.schema.normalizer import DGSKStructure, SchemaNormalizer
from gw2_progression.data_mesh.sources.registry import SourceRegistry


@dataclass
class PipelineStage:
    name: str
    status: str
    elapsed_ms: float = 0.0
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    id: str
    status: str
    sources_ingested: int
    source_results: list[IngestResult]
    normalized: DGSKStructure | None
    confidence: ConfidenceRecord | None
    stages: list[PipelineStage]
    total_elapsed_ms: float
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        base = {
            "id": self.id,
            "status": self.status,
            "sources_ingested": self.sources_ingested,
            "source_results": [r.to_dict() for r in self.source_results],
            "stages": [s.__dict__ for s in self.stages],
            "total_elapsed_ms": round(self.total_elapsed_ms, 2),
            "timestamp": self.timestamp,
            "error": self.error,
        }
        if self.normalized is not None:
            base["normalized"] = self.normalized.to_dict()
        if self.confidence is not None:
            base["confidence"] = self.confidence.to_dict()
        return base


class DataMeshPipeline:
    def __init__(
        self,
        api_key: str | None = None,
        source_registry: SourceRegistry | None = None,
    ):
        self._api_key = api_key
        self._registry = source_registry or SourceRegistry()
        self._ingestion = DataIngestion(api_key=api_key)
        self._confidence = ConfidenceSystem(source_registry=self._registry)

    def run(
        self,
        sources: list[dict],
        options: dict | None = None,
    ) -> PipelineResult:
        opts = options or {}
        pipeline_id = str(uuid.uuid4())
        start = time.perf_counter()
        stages: list[PipelineStage] = []
        total_elapsed = 0.0

        s1 = PipelineStage(name="resolve_sources", status="pending")
        try:
            s1_start = time.perf_counter()
            resolved = self._resolve_sources(sources)
            s1.elapsed_ms = (time.perf_counter() - s1_start) * 1000
            s1.status = "ok"
            s1.details = {"resolved_count": len(resolved)}
        except Exception as e:
            s1.elapsed_ms = (time.perf_counter() - s1_start) * 1000
            s1.status = "error"
            s1.error = str(e)
            stages.append(s1)
            total_elapsed = (time.perf_counter() - start) * 1000
            return PipelineResult(
                id=pipeline_id,
                status="failed",
                sources_ingested=0,
                source_results=[],
                normalized=None,
                confidence=None,
                stages=stages,
                total_elapsed_ms=total_elapsed,
                error=str(e),
            )
        stages.append(s1)

        s2 = PipelineStage(name="ingest", status="pending")
        try:
            s2_start = time.perf_counter()
            results = self._ingestion.ingest_multi(resolved)
            s2.elapsed_ms = (time.perf_counter() - s2_start) * 1000
            errors = [r for r in results if r.status == "error"]
            s2.status = "partial" if errors else "ok"
            s2.details = {"total": len(results), "ok": len(results) - len(errors), "errors": len(errors)}
        except Exception as e:
            s2.elapsed_ms = (time.perf_counter() - s2_start) * 1000
            s2.status = "error"
            s2.error = str(e)
            stages.append(s2)
            total_elapsed = (time.perf_counter() - start) * 1000
            return PipelineResult(
                id=pipeline_id,
                status="failed",
                sources_ingested=0,
                source_results=results if "results" in dir() else [],
                normalized=None,
                confidence=None,
                stages=stages,
                total_elapsed_ms=total_elapsed,
                error=str(e),
            )
        stages.append(s2)

        ok_results = [r for r in results if r.status in ("ok", "cached")]

        s3 = PipelineStage(name="normalize", status="pending")
        normalized = None
        try:
            s3_start = time.perf_counter()
            structures = []
            for r in ok_results:
                ds = SchemaNormalizer.normalize(r.raw_data, source_type=r.source_type)
                structures.append(ds)
            normalized = SchemaNormalizer.merge(structures) if structures else DGSKStructure()
            s3.elapsed_ms = (time.perf_counter() - s3_start) * 1000
            s3.status = "ok"
            s3.details = {"source_count": len(structures), "merged_keys": list(normalized.metadata.keys())}
        except Exception as e:
            s3.elapsed_ms = (time.perf_counter() - s3_start) * 1000
            s3.status = "error"
            s3.error = str(e)
        stages.append(s3)

        s4 = PipelineStage(name="confidence", status="pending")
        confidence_record = None
        try:
            s4_start = time.perf_counter()
            source_types = [r.source_type for r in ok_results]
            source_ids = [r.source_id for r in ok_results]
            cross_val = len(set(source_types))
            type_counts: dict[str, int] = {}
            for st in source_types:
                type_counts[st] = type_counts.get(st, 0) + 1
            dominant_type = max(type_counts, key=type_counts.get) if type_counts else "unknown"
            confidence_record = self._confidence.evaluate(
                source_type=dominant_type,
                source_id=source_ids[0] if source_ids else None,
                records_count=sum(r.record_count for r in ok_results),
                cross_validation_count=cross_val,
            )
            s4.elapsed_ms = (time.perf_counter() - s4_start) * 1000
            s4.status = "ok"
            s4.details = {"adjusted_confidence": confidence_record.adjusted_confidence}
        except Exception as e:
            s4.elapsed_ms = (time.perf_counter() - s4_start) * 1000
            s4.status = "error"
            s4.error = str(e)
        stages.append(s4)

        s5 = PipelineStage(name="persist", status="pending")
        try:
            s5_start = time.perf_counter()
            persist_target = opts.get("persist_target", "")
            if persist_target and normalized is not None:
                import json
                from pathlib import Path

                p = Path(persist_target)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(
                    json.dumps(normalized.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                s5.details = {"path": str(p), "size_bytes": p.stat().st_size}
            s5.elapsed_ms = (time.perf_counter() - s5_start) * 1000
            s5.status = "ok"
        except Exception as e:
            s5.elapsed_ms = (time.perf_counter() - s5_start) * 1000
            s5.status = "error"
            s5.error = str(e)
        stages.append(s5)

        total_elapsed = (time.perf_counter() - start) * 1000
        has_errors = any(s.status == "error" for s in stages)
        has_partial = any(s.status == "partial" for s in stages)

        return PipelineResult(
            id=pipeline_id,
            status="error" if has_errors else ("partial" if has_partial else "ok"),
            sources_ingested=len(ok_results),
            source_results=results,
            normalized=normalized,
            confidence=confidence_record,
            stages=stages,
            total_elapsed_ms=total_elapsed,
            error=None,
        )

    def _resolve_sources(self, sources: list[dict]) -> list[dict]:
        resolved = []
        for s in sources:
            s_type = s.get("type", "")
            source_id = s.get("source_id", "")
            if not source_id and self._registry:
                candidates = self._registry.list_sources()
                for cs in candidates:
                    if cs.source_type.value == s_type or s_type in cs.source_id:
                        source_id = cs.source_id
                        break
            entry = {
                "type": s_type,
                "params": dict(s.get("params", {})),
                "source_id": source_id or f"{s_type}:auto",
            }
            resolved.append(entry)
        return resolved
