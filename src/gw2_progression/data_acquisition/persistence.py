from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

import httpx

from gw2_progression.data_acquisition.contract import DataExpansionRecord, stable_hash


class DataExpansionMirror:
    """Optional mirrors for production services.

    The local SQLite store remains authoritative for single-machine runs.
    Configured mirrors write the same contract to Postgres, Neo4j, and Qdrant.
    """

    def __init__(
        self,
        postgres_url: str = "",
        neo4j_url: str = "",
        qdrant_url: str = "",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "",
        qdrant_collection: str = "gw2_data_expansion",
        postgres_connection_factory: Any | None = None,
        neo4j_driver_factory: Any | None = None,
        http_client: Any | None = None,
    ) -> None:
        self.postgres_url = postgres_url
        self.neo4j_url = neo4j_url
        self.qdrant_url = qdrant_url
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.qdrant_collection = qdrant_collection
        self.postgres_connection_factory = postgres_connection_factory
        self.neo4j_driver_factory = neo4j_driver_factory
        self.http_client = http_client

    @classmethod
    def from_env(cls) -> "DataExpansionMirror":
        return cls(
            postgres_url=os.getenv("DATA_EXPANSION_POSTGRES_URL", ""),
            neo4j_url=os.getenv("DATA_EXPANSION_NEO4J_URL", ""),
            qdrant_url=os.getenv("DATA_EXPANSION_QDRANT_URL", ""),
            neo4j_user=os.getenv("DATA_EXPANSION_NEO4J_USER", "neo4j"),
            neo4j_password=os.getenv("DATA_EXPANSION_NEO4J_PASSWORD", ""),
            qdrant_collection=os.getenv("DATA_EXPANSION_QDRANT_COLLECTION", "gw2_data_expansion"),
        )

    def write_records(self, records: list[DataExpansionRecord]) -> dict[str, Any]:
        result: dict[str, Any] = {"postgres": None, "neo4j": None, "qdrant": None}
        if self.postgres_url:
            result["postgres"] = self.write_postgres(records)
        if self.neo4j_url:
            result["neo4j"] = self.write_neo4j(records)
        if self.qdrant_url:
            result["qdrant"] = self.write_qdrant(records)
        return result

    def write_postgres(self, records: list[DataExpansionRecord]) -> dict[str, Any]:
        if not self.postgres_url:
            return {"written": False, "reason": "postgres not configured"}
        with self._postgres_connect() as conn:
            conn.execute(self.postgres_schema_sql())
            for record in records:
                conn.execute(
                    """
                    INSERT INTO data_expansion_records (
                        entity_id, source_id, version, source_type, collected_at,
                        observed_at, entity_type, raw_payload_hash, normalized_payload,
                        confidence, lineage, privacy_scope, validation_status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s)
                    ON CONFLICT (entity_id, source_id, version, raw_payload_hash) DO NOTHING
                    """,
                    (
                        record.entity_id,
                        record.source_id,
                        record.version,
                        record.source_type,
                        record.collected_at,
                        record.observed_at,
                        record.entity_type,
                        record.raw_payload_hash,
                        json.dumps(record.normalized_payload, sort_keys=True, default=str),
                        record.confidence,
                        json.dumps(record.lineage, sort_keys=True),
                        record.privacy_scope,
                        record.validation_status,
                        time.time(),
                    ),
                )
            conn.commit()
        return {"written": True, "backend": "postgres", "attempted": len(records)}

    def postgres_schema_sql(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS data_expansion_records (
            entity_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            version TEXT NOT NULL,
            source_type TEXT NOT NULL,
            collected_at DOUBLE PRECISION NOT NULL,
            observed_at DOUBLE PRECISION NOT NULL,
            entity_type TEXT NOT NULL,
            raw_payload_hash TEXT NOT NULL,
            normalized_payload JSONB NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            lineage JSONB NOT NULL,
            privacy_scope TEXT NOT NULL,
            validation_status TEXT NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (entity_id, source_id, version, raw_payload_hash)
        );
        CREATE INDEX IF NOT EXISTS idx_data_expansion_records_source ON data_expansion_records(source_id);
        CREATE INDEX IF NOT EXISTS idx_data_expansion_records_type ON data_expansion_records(entity_type);
        """

    def write_neo4j(self, records: list[DataExpansionRecord]) -> dict[str, Any]:
        if not self.neo4j_url:
            return {"written": False, "reason": "neo4j not configured"}
        driver = self._neo4j_driver()
        try:
            with driver.session() as session:
                for record in records:
                    session.run(
                        (
                            "MERGE (s:DataSource {id: $source_id}) "
                            "MERGE (e:DataEntity {id: $entity_id}) "
                            "SET e.entity_type = $entity_type, e.confidence = $confidence, "
                            "e.privacy_scope = $privacy_scope, e.version = $version, e.raw_payload_hash = $raw_payload_hash "
                            "MERGE (s)-[r:OBSERVED]->(e) "
                            "SET r.observed_at = $observed_at, r.collected_at = $collected_at, r.validation_status = $validation_status"
                        ),
                        **record.to_dict(),
                    )
        finally:
            driver.close()
        return {"written": True, "backend": "neo4j", "attempted": len(records)}

    def write_qdrant(self, records: list[DataExpansionRecord]) -> dict[str, Any]:
        if not self.qdrant_url:
            return {"written": False, "reason": "qdrant not configured"}
        client = self.http_client or httpx.Client(timeout=10)
        try:
            client.put(f"{self.qdrant_url}/collections/{self.qdrant_collection}", json={"vectors": {"size": 16, "distance": "Cosine"}})
            points = [
                {
                    "id": record.raw_payload_hash,
                    "vector": self._embedding(record),
                    "payload": record.to_dict(),
                }
                for record in records
            ]
            response = client.put(f"{self.qdrant_url}/collections/{self.qdrant_collection}/points", json={"points": points})
            response.raise_for_status()
        finally:
            if self.http_client is None and hasattr(client, "close"):
                client.close()
        return {"written": True, "backend": "qdrant", "attempted": len(records)}

    def _embedding(self, record: DataExpansionRecord) -> list[float]:
        text = stable_hash(record.to_dict())
        return [int(text[i : i + 2], 16) / 255.0 for i in range(0, 32, 2)]

    def _postgres_connect(self) -> Any:
        if self.postgres_connection_factory:
            return self.postgres_connection_factory(self.postgres_url)
        import psycopg

        return psycopg.connect(self.postgres_url)

    def _neo4j_driver(self) -> Any:
        if self.neo4j_driver_factory:
            return self.neo4j_driver_factory(self.neo4j_url, auth=(self.neo4j_user, self.neo4j_password))
        from neo4j import GraphDatabase

        return GraphDatabase.driver(self.neo4j_url, auth=(self.neo4j_user, self.neo4j_password))


class DataExpansionStore:
    """Durable store for raw lineage-aware expansion records.

    SQLite is the default local backend so tests and single-machine runs have
    real read-after-write semantics. The schema mirrors the fields expected in
    Postgres and can be migrated later without changing the ingestion contract.
    """

    def __init__(self, path: str | Path = "data/data_expansion.sqlite3", mirror: DataExpansionMirror | None = None) -> None:
        self.path = Path(path)
        self.mirror = mirror or DataExpansionMirror.from_env()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def migrate(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS data_expansion_records (
                    entity_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    collected_at REAL NOT NULL,
                    observed_at REAL NOT NULL,
                    entity_type TEXT NOT NULL,
                    raw_payload_hash TEXT NOT NULL,
                    normalized_payload TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    lineage TEXT NOT NULL,
                    privacy_scope TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (entity_id, source_id, version, raw_payload_hash)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_data_expansion_source ON data_expansion_records(source_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_data_expansion_type ON data_expansion_records(entity_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_data_expansion_observed ON data_expansion_records(observed_at)")
            conn.commit()

    def write_records(self, records: list[DataExpansionRecord]) -> dict[str, Any]:
        written = 0
        with self._connect() as conn:
            for record in records:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO data_expansion_records (
                        entity_id, source_id, version, source_type, collected_at,
                        observed_at, entity_type, raw_payload_hash, normalized_payload,
                        confidence, lineage, privacy_scope, validation_status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.entity_id,
                        record.source_id,
                        record.version,
                        record.source_type,
                        record.collected_at,
                        record.observed_at,
                        record.entity_type,
                        record.raw_payload_hash,
                        json.dumps(record.normalized_payload, sort_keys=True, default=str),
                        record.confidence,
                        json.dumps(record.lineage, sort_keys=True),
                        record.privacy_scope,
                        record.validation_status,
                        time.time(),
                    ),
                )
                written += cur.rowcount
            conn.commit()
        mirror_result = self.mirror.write_records(records)
        return {"written": written, "attempted": len(records), "backend": "sqlite", "path": str(self.path), "mirrors": mirror_result}

    def list_records(self, limit: int = 1000) -> list[DataExpansionRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source_id, source_type, collected_at, observed_at, entity_type,
                       entity_id, raw_payload_hash, normalized_payload, confidence,
                       lineage, privacy_scope, version, validation_status
                FROM data_expansion_records
                ORDER BY observed_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def latest_observed_by_source(self) -> dict[str, float]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT source_id, MAX(observed_at) FROM data_expansion_records GROUP BY source_id"
            ).fetchall()
        return {str(source_id): float(observed_at or 0.0) for source_id, observed_at in rows}

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM data_expansion_records").fetchone()
        return int(row[0] if row else 0)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _row_to_record(self, row: tuple[Any, ...]) -> DataExpansionRecord:
        return DataExpansionRecord(
            source_id=row[0],
            source_type=row[1],
            collected_at=float(row[2]),
            observed_at=float(row[3]),
            entity_type=row[4],
            entity_id=row[5],
            raw_payload_hash=row[6],
            normalized_payload=json.loads(row[7]),
            confidence=float(row[8]),
            lineage=json.loads(row[9]),
            privacy_scope=row[10],
            version=row[11],
            validation_status=row[12],
        )
