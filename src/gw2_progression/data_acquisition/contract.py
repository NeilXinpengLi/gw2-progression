from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class DataExpansionRecord:
    """Canonical lineage contract for data acquired by the expansion pipeline."""

    source_id: str
    source_type: str
    collected_at: float
    observed_at: float
    entity_type: str
    entity_id: str
    raw_payload_hash: str
    normalized_payload: dict[str, Any]
    confidence: float
    lineage: list[str] = field(default_factory=list)
    privacy_scope: str = "public"
    version: str = "v1"
    validation_status: str = "valid"

    @classmethod
    def from_entity(
        cls,
        entity: dict[str, Any],
        *,
        source_id: str,
        source_type: str,
        collected_at: float,
        observed_at: float,
        confidence: float,
        privacy_scope: str,
        version: str = "v1",
    ) -> "DataExpansionRecord":
        entity_id = str(entity.get("id") or f"{source_id}:unknown")
        lineage = list(dict.fromkeys([source_id, *entity.get("lineage", []), entity.get("source", source_id)]))
        return cls(
            source_id=source_id,
            source_type=source_type,
            collected_at=collected_at,
            observed_at=observed_at,
            entity_type=str(entity.get("type", "entity")),
            entity_id=entity_id,
            raw_payload_hash=stable_hash(entity),
            normalized_payload=dict(entity),
            confidence=max(0.0, min(1.0, float(entity.get("confidence", confidence)))),
            lineage=lineage,
            privacy_scope=privacy_scope,
            version=version,
            validation_status="valid" if entity_id else "invalid",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "collected_at": self.collected_at,
            "observed_at": self.observed_at,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "raw_payload_hash": self.raw_payload_hash,
            "normalized_payload": self.normalized_payload,
            "confidence": self.confidence,
            "lineage": self.lineage,
            "privacy_scope": self.privacy_scope,
            "version": self.version,
            "validation_status": self.validation_status,
        }


@dataclass(frozen=True)
class DataCoverageReport:
    total_records: int
    sources: dict[str, int]
    entity_types: dict[str, int]
    privacy_scopes: dict[str, int]
    confidence_buckets: dict[str, int]
    stale_sources: list[str]
    missing_entity_types: list[str]
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "sources": self.sources,
            "entity_types": self.entity_types,
            "privacy_scopes": self.privacy_scopes,
            "confidence_buckets": self.confidence_buckets,
            "stale_sources": self.stale_sources,
            "missing_entity_types": self.missing_entity_types,
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True)
class ActiveRefreshRequest:
    source_id: str
    reason: str
    priority: int
    entity_type: str | None = None
    entity_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "reason": self.reason,
            "priority": self.priority,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
        }


@dataclass(frozen=True)
class DatasetManifest:
    name: str
    sample_count: int
    source_mix: dict[str, int]
    confidence_distribution: dict[str, int]
    label_coverage: dict[str, int]
    lineage_hashes: list[str]
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sample_count": self.sample_count,
            "source_mix": self.source_mix,
            "confidence_distribution": self.confidence_distribution,
            "label_coverage": self.label_coverage,
            "lineage_hashes": self.lineage_hashes,
            "created_at": self.created_at,
        }
