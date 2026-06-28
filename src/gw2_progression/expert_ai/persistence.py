"""Persistence and external service adapters for the Expert AI runtime."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import httpx

if TYPE_CHECKING:
    from gw2_progression.expert_ai.core import RuntimeSnapshot


@dataclass(frozen=True)
class ExpertAIServiceConfig:
    postgres_url: str = ""
    neo4j_url: str = ""
    qdrant_url: str = ""
    redis_url: str = ""
    state_path: str = "data/expert_ai_state.json"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    retry_attempts: int = 3
    retry_backoff_seconds: float = 0.2

    @classmethod
    def from_env(cls) -> "ExpertAIServiceConfig":
        return cls(
            postgres_url=os.getenv("EXPERT_AI_POSTGRES_URL", ""),
            neo4j_url=os.getenv("EXPERT_AI_NEO4J_URL", ""),
            qdrant_url=os.getenv("EXPERT_AI_QDRANT_URL", ""),
            redis_url=os.getenv("EXPERT_AI_REDIS_URL", ""),
            state_path=os.getenv("EXPERT_AI_STATE_PATH", "data/expert_ai_state.json"),
            neo4j_user=os.getenv("EXPERT_AI_NEO4J_USER", "neo4j"),
            neo4j_password=os.getenv("EXPERT_AI_NEO4J_PASSWORD", ""),
            retry_attempts=int(os.getenv("EXPERT_AI_RETRY_ATTEMPTS", "3")),
            retry_backoff_seconds=float(os.getenv("EXPERT_AI_RETRY_BACKOFF_SECONDS", "0.2")),
        )

    def redacted(self) -> dict[str, str]:
        return {
            "postgres_url": _redact(self.postgres_url),
            "neo4j_url": _redact(self.neo4j_url),
            "qdrant_url": _redact(self.qdrant_url),
            "redis_url": _redact(self.redis_url),
            "state_path": self.state_path,
            "neo4j_user": self.neo4j_user,
        }


class LocalJsonStateStore:
    """Small durable fallback store for snapshots and memory records."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save_runtime_snapshot(self, snapshot: RuntimeSnapshot) -> dict[str, Any]:
        state = self._read()
        state.setdefault("snapshots", {})[snapshot.id] = {
            "id": snapshot.id,
            "created_at": snapshot.created_at,
            "entities": {key: _node_to_dict(value) for key, value in snapshot.entities.items()},
            "relations": [_edge_to_dict(edge) for edge in snapshot.relations],
        }
        self._write(state)
        return {"stored": True, "snapshot_id": snapshot.id, "backend": "local_json"}

    def load_runtime_snapshot(self, snapshot_id: str) -> RuntimeSnapshot | None:
        raw = self._read().get("snapshots", {}).get(snapshot_id)
        if not raw:
            return None
        from gw2_progression.expert_ai.core import GraphEdge, GraphNode, RuntimeSnapshot

        return RuntimeSnapshot(
            id=raw["id"],
            created_at=float(raw["created_at"]),
            entities={key: GraphNode(id=value["id"], type=value["type"], properties=value.get("properties", {})) for key, value in raw.get("entities", {}).items()},
            relations=[
                GraphEdge(
                    source=edge["source"],
                    target=edge["target"],
                    relation_type=edge["relation_type"],
                    weight=float(edge.get("weight", 1.0)),
                    properties=edge.get("properties", {}),
                )
                for edge in raw.get("relations", [])
            ],
        )

    def append_memory(self, event: dict[str, Any]) -> dict[str, Any]:
        state = self._read()
        state.setdefault("memory", []).append(event)
        self._write(state)
        return {"stored": True, "event_id": event.get("id"), "backend": "local_json"}

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"snapshots": {}, "memory": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


class Neo4jGraphAdapter:
    """Prepare graph payloads for Neo4j ingestion without requiring the driver at import time."""

    def __init__(self, url: str = "", user: str = "neo4j", password: str = "", driver_factory: Callable[..., Any] | None = None) -> None:
        self.url = url
        self.user = user
        self.password = password
        self.driver_factory = driver_factory

    def is_configured(self) -> bool:
        return bool(self.url)

    def export_cypher(self, graph: dict[str, Any]) -> list[dict[str, Any]]:
        statements: list[dict[str, Any]] = []
        for node in graph.get("nodes", []):
            statements.append({
                "statement": "MERGE (n:ExpertNode {id: $id}) SET n.type = $type, n.properties = $properties",
                "parameters": {"id": node["id"], "type": node["type"], "properties": node.get("properties", {})},
            })
        for edge in graph.get("edges", []):
            statements.append({
                "statement": (
                    "MATCH (a:ExpertNode {id: $source}), (b:ExpertNode {id: $target}) "
                    "MERGE (a)-[r:EXPERT_RELATION {relation_type: $relation_type}]->(b) "
                    "SET r.weight = $weight, r.properties = $properties"
                ),
                "parameters": {
                    "source": edge["source"],
                    "target": edge["target"],
                    "relation_type": edge["relation_type"],
                    "weight": edge.get("weight", 1.0),
                    "properties": edge.get("properties", {}),
                },
            })
        return statements

    def write_graph(self, graph: dict[str, Any], retry_attempts: int = 3, retry_backoff_seconds: float = 0.2) -> dict[str, Any]:
        statements = self.export_cypher(graph)
        if not self.is_configured():
            return {"written": False, "reason": "neo4j not configured", "statement_count": len(statements)}

        def _write() -> int:
            driver = self._driver()
            try:
                with driver.session() as session:
                    for stmt in statements:
                        session.run(stmt["statement"], **stmt["parameters"])
                return len(statements)
            finally:
                driver.close()

        count = _retry(_write, retry_attempts, retry_backoff_seconds)
        return {"written": True, "backend": "neo4j", "statement_count": count}

    def read_node(self, node_id: str, retry_attempts: int = 3, retry_backoff_seconds: float = 0.2) -> dict[str, Any] | None:
        if not self.is_configured():
            return None

        def _read() -> dict[str, Any] | None:
            driver = self._driver()
            try:
                with driver.session() as session:
                    result = session.run("MATCH (n:ExpertNode {id: $id}) RETURN n.id AS id, n.type AS type, n.properties AS properties", id=node_id)
                    row = result.single()
                    return None if row is None else {"id": row["id"], "type": row["type"], "properties": row["properties"]}
            finally:
                driver.close()

        return _retry(_read, retry_attempts, retry_backoff_seconds)

    def readiness(self, retry_attempts: int = 1, retry_backoff_seconds: float = 0.0) -> dict[str, Any]:
        if not self.is_configured():
            return {"configured": False, "ready": False, "reason": "neo4j not configured"}

        def _ping() -> dict[str, Any]:
            driver = self._driver()
            try:
                with driver.session() as session:
                    result = session.run("RETURN 1 AS ok")
                    row = result.single()
                return {"configured": True, "ready": bool(row and row["ok"] == 1)}
            finally:
                driver.close()

        return _safe_external_check(_ping, retry_attempts, retry_backoff_seconds)

    def _driver(self) -> Any:
        if self.driver_factory:
            return self.driver_factory(self.url, auth=(self.user, self.password))
        from neo4j import GraphDatabase

        return GraphDatabase.driver(self.url, auth=(self.user, self.password))


class QdrantMemoryAdapter:
    """Prepare deterministic vector-memory points for Qdrant ingestion."""

    def __init__(self, url: str = "", collection: str = "gw2_expert_memory", vector_size: int = 16, http_client: Any | None = None) -> None:
        self.url = url
        self.collection = collection
        self.vector_size = vector_size
        self.http_client = http_client

    def is_configured(self) -> bool:
        return bool(self.url)

    def to_point(self, event: dict[str, Any]) -> dict[str, Any]:
        text = json.dumps(event, sort_keys=True, default=str)
        return {
            "id": event.get("id") or hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "vector": _hash_embedding(text, self.vector_size),
            "payload": event,
        }

    def upsert_event(self, event: dict[str, Any], retry_attempts: int = 3, retry_backoff_seconds: float = 0.2) -> dict[str, Any]:
        point = self.to_point(event)
        if not self.is_configured():
            return {"written": False, "reason": "qdrant not configured", "point": point}

        def _upsert() -> dict[str, Any]:
            client = self._client()
            try:
                client.put(f"{self.url}/collections/{self.collection}", json={"vectors": {"size": self.vector_size, "distance": "Cosine"}})
                response = client.put(f"{self.url}/collections/{self.collection}/points", json={"points": [point]})
                response.raise_for_status()
                return {"written": True, "backend": "qdrant", "point_id": point["id"]}
            finally:
                self._close_client(client)

        return _retry(_upsert, retry_attempts, retry_backoff_seconds)

    def search(self, query: str, limit: int = 10, retry_attempts: int = 3, retry_backoff_seconds: float = 0.2) -> dict[str, Any]:
        if not self.is_configured():
            return {"results": [], "reason": "qdrant not configured"}
        vector = _hash_embedding(query, self.vector_size)

        def _search() -> dict[str, Any]:
            client = self._client()
            try:
                response = client.post(f"{self.url}/collections/{self.collection}/points/search", json={"vector": vector, "limit": limit, "with_payload": True})
                response.raise_for_status()
                return response.json()
            finally:
                self._close_client(client)

        return _retry(_search, retry_attempts, retry_backoff_seconds)

    def readiness(self, retry_attempts: int = 1, retry_backoff_seconds: float = 0.0) -> dict[str, Any]:
        if not self.is_configured():
            return {"configured": False, "ready": False, "reason": "qdrant not configured"}

        def _ping() -> dict[str, Any]:
            client = self._client()
            try:
                response = client.get(f"{self.url}/readyz")
                response.raise_for_status()
                return {"configured": True, "ready": True}
            finally:
                self._close_client(client)

        return _safe_external_check(_ping, retry_attempts, retry_backoff_seconds)

    def _client(self) -> Any:
        return self.http_client or httpx.Client(timeout=10)

    def _close_client(self, client: Any) -> None:
        if self.http_client is None and hasattr(client, "close"):
            client.close()


class PostgresStateAdapter:
    """Postgres DDL and payload helpers for durable runtime state."""

    def __init__(self, url: str = "", connection_factory: Callable[..., Any] | None = None) -> None:
        self.url = url
        self.connection_factory = connection_factory

    def is_configured(self) -> bool:
        return bool(self.url)

    def schema_sql(self) -> str:
        return "\n".join([
            "CREATE TABLE IF NOT EXISTS expert_ai_snapshots (",
            "  id TEXT PRIMARY KEY,",
            "  created_at DOUBLE PRECISION NOT NULL,",
            "  payload JSONB NOT NULL",
            ");",
            "CREATE TABLE IF NOT EXISTS expert_ai_memory (",
            "  id TEXT PRIMARY KEY,",
            "  created_at DOUBLE PRECISION NOT NULL,",
            "  memory_type TEXT NOT NULL,",
            "  payload JSONB NOT NULL",
            ");",
            "CREATE TABLE IF NOT EXISTS expert_ai_schema_migrations (",
            "  version TEXT PRIMARY KEY,",
            "  applied_at DOUBLE PRECISION NOT NULL",
            ");",
            "CREATE INDEX IF NOT EXISTS idx_expert_ai_memory_type ON expert_ai_memory(memory_type);",
            "CREATE INDEX IF NOT EXISTS idx_expert_ai_memory_created_at ON expert_ai_memory(created_at);",
        ])

    def snapshot_row(self, snapshot: RuntimeSnapshot) -> dict[str, Any]:
        return {
            "id": snapshot.id,
            "created_at": snapshot.created_at,
            "payload": {
                "entities": {key: _node_to_dict(value) for key, value in snapshot.entities.items()},
                "relations": [_edge_to_dict(edge) for edge in snapshot.relations],
            },
        }

    def migrate(self, retry_attempts: int = 3, retry_backoff_seconds: float = 0.2) -> dict[str, Any]:
        if not self.is_configured():
            return {"migrated": False, "reason": "postgres not configured"}

        def _migrate() -> dict[str, Any]:
            with self._connect() as conn:
                conn.execute(self.schema_sql())
                conn.execute(
                    "INSERT INTO expert_ai_schema_migrations (version, applied_at) VALUES (%s, %s) ON CONFLICT (version) DO NOTHING",
                    ("expert_ai_v1", time.time()),
                )
                conn.commit()
            return {"migrated": True, "backend": "postgres"}

        return _retry(_migrate, retry_attempts, retry_backoff_seconds)

    def write_snapshot(self, snapshot: RuntimeSnapshot, retry_attempts: int = 3, retry_backoff_seconds: float = 0.2) -> dict[str, Any]:
        if not self.is_configured():
            return {"written": False, "reason": "postgres not configured"}
        row = self.snapshot_row(snapshot)

        def _write() -> dict[str, Any]:
            with self._connect() as conn:
                conn.execute(
                    (
                        "INSERT INTO expert_ai_snapshots (id, created_at, payload) VALUES (%s, %s, %s::jsonb) "
                        "ON CONFLICT (id) DO UPDATE SET created_at = EXCLUDED.created_at, payload = EXCLUDED.payload"
                    ),
                    (row["id"], row["created_at"], json.dumps(row["payload"], sort_keys=True)),
                )
                conn.commit()
            return {"written": True, "backend": "postgres", "snapshot_id": row["id"]}

        return _retry(_write, retry_attempts, retry_backoff_seconds)

    def read_snapshot(self, snapshot_id: str, retry_attempts: int = 3, retry_backoff_seconds: float = 0.2) -> dict[str, Any] | None:
        if not self.is_configured():
            return None

        def _read() -> dict[str, Any] | None:
            with self._connect() as conn:
                row = conn.execute("SELECT id, created_at, payload FROM expert_ai_snapshots WHERE id = %s", (snapshot_id,)).fetchone()
            if not row:
                return None
            payload = row[2] if isinstance(row[2], dict) else json.loads(row[2])
            return {"id": row[0], "created_at": row[1], "payload": payload}

        return _retry(_read, retry_attempts, retry_backoff_seconds)

    def write_memory(self, event: dict[str, Any], retry_attempts: int = 3, retry_backoff_seconds: float = 0.2) -> dict[str, Any]:
        if not self.is_configured():
            return {"written": False, "reason": "postgres not configured"}

        def _write() -> dict[str, Any]:
            with self._connect() as conn:
                conn.execute(
                    (
                        "INSERT INTO expert_ai_memory (id, created_at, memory_type, payload) VALUES (%s, %s, %s, %s::jsonb) "
                        "ON CONFLICT (id) DO UPDATE SET created_at = EXCLUDED.created_at, memory_type = EXCLUDED.memory_type, payload = EXCLUDED.payload"
                    ),
                    (event["id"], float(event["created_at"]), event.get("type", "episodic"), json.dumps(event, sort_keys=True)),
                )
                conn.commit()
            return {"written": True, "backend": "postgres", "event_id": event["id"]}

        return _retry(_write, retry_attempts, retry_backoff_seconds)

    def readiness(self, retry_attempts: int = 1, retry_backoff_seconds: float = 0.0) -> dict[str, Any]:
        if not self.is_configured():
            return {"configured": False, "ready": False, "reason": "postgres not configured"}

        def _ping() -> dict[str, Any]:
            with self._connect() as conn:
                row = conn.execute("SELECT 1").fetchone()
            return {"configured": True, "ready": bool(row and row[0] == 1)}

        return _safe_external_check(_ping, retry_attempts, retry_backoff_seconds)

    def _connect(self) -> Any:
        if self.connection_factory:
            return self.connection_factory(self.url)
        import psycopg

        return psycopg.connect(self.url)


class RedisQueueAdapter:
    """Redis queue facade for background Expert AI tasks."""

    def __init__(self, url: str = "", queue_name: str = "expert_ai_tasks", client_factory: Callable[..., Any] | None = None) -> None:
        self.url = url
        self.queue_name = queue_name
        self.client_factory = client_factory

    def is_configured(self) -> bool:
        return bool(self.url)

    def enqueue(self, task: dict[str, Any], retry_attempts: int = 3, retry_backoff_seconds: float = 0.2) -> dict[str, Any]:
        if not self.is_configured():
            return {"queued": False, "reason": "redis not configured"}

        def _enqueue() -> dict[str, Any]:
            client = self._client()
            task_id = client.xadd(self.queue_name, {"payload": json.dumps(task, sort_keys=True)})
            return {"queued": True, "backend": "redis", "task_id": _decode(task_id)}

        return _retry(_enqueue, retry_attempts, retry_backoff_seconds)

    def dequeue(self, count: int = 1, block_ms: int = 1000, retry_attempts: int = 3, retry_backoff_seconds: float = 0.2) -> list[dict[str, Any]]:
        if not self.is_configured():
            return []

        def _dequeue() -> list[dict[str, Any]]:
            client = self._client()
            rows = client.xread({self.queue_name: "0-0"}, count=count, block=block_ms)
            tasks = []
            for _stream, messages in rows:
                for task_id, fields in messages:
                    payload = fields.get(b"payload") or fields.get("payload")
                    tasks.append({"id": _decode(task_id), "payload": json.loads(_decode(payload))})
            return tasks

        return _retry(_dequeue, retry_attempts, retry_backoff_seconds)

    def ack(self, task_id: str, retry_attempts: int = 3, retry_backoff_seconds: float = 0.2) -> dict[str, Any]:
        if not self.is_configured():
            return {"acked": False, "reason": "redis not configured", "task_id": task_id}

        def _ack() -> dict[str, Any]:
            client = self._client()
            removed = client.xdel(self.queue_name, task_id)
            return {"acked": bool(removed), "backend": "redis", "task_id": task_id}

        return _retry(_ack, retry_attempts, retry_backoff_seconds)

    def readiness(self, retry_attempts: int = 1, retry_backoff_seconds: float = 0.0) -> dict[str, Any]:
        if not self.is_configured():
            return {"configured": False, "ready": False, "reason": "redis not configured"}

        def _ping() -> dict[str, Any]:
            client = self._client()
            return {"configured": True, "ready": bool(client.ping())}

        return _safe_external_check(_ping, retry_attempts, retry_backoff_seconds)

    def _client(self) -> Any:
        if self.client_factory:
            return self.client_factory(self.url)
        import redis

        return redis.Redis.from_url(self.url)


class ExpertAIPersistence:
    """Facade for local durable state plus production service adapters."""

    def __init__(self, config: ExpertAIServiceConfig | None = None) -> None:
        self.config = config or ExpertAIServiceConfig.from_env()
        self.local_state = LocalJsonStateStore(self.config.state_path)
        self.neo4j = Neo4jGraphAdapter(self.config.neo4j_url, user=self.config.neo4j_user, password=self.config.neo4j_password)
        self.qdrant = QdrantMemoryAdapter(self.config.qdrant_url)
        self.postgres = PostgresStateAdapter(self.config.postgres_url)
        self.redis = RedisQueueAdapter(self.config.redis_url)

    def health(self) -> dict[str, Any]:
        return {
            "checked_at": time.time(),
            "config": self.config.redacted(),
            "services": {
                "neo4j": {"configured": self.neo4j.is_configured(), "mode": "read_write"},
                "qdrant": {"configured": self.qdrant.is_configured(), "mode": "read_write"},
                "postgres": {"configured": self.postgres.is_configured(), "mode": "read_write"},
                "redis": {"configured": self.redis.is_configured(), "mode": "queue"},
                "local_json": {"configured": True, "path": self.config.state_path},
            },
        }

    def readiness(self) -> dict[str, Any]:
        attempts = min(self.config.retry_attempts, 2)
        backoff = min(self.config.retry_backoff_seconds, 0.1)
        services = {
            "neo4j": self.neo4j.readiness(attempts, backoff),
            "qdrant": self.qdrant.readiness(attempts, backoff),
            "postgres": self.postgres.readiness(attempts, backoff),
            "redis": self.redis.readiness(attempts, backoff),
            "local_json": {"configured": True, "ready": self.local_state.path.parent.exists() or self.local_state.path.parent.parent.exists()},
        }
        return {"checked_at": time.time(), "ready": all(service.get("ready", False) for service in services.values() if service.get("configured")), "services": services}

    def persist_snapshot(self, snapshot: RuntimeSnapshot) -> dict[str, Any]:
        stored = self.local_state.save_runtime_snapshot(snapshot)
        postgres = self.postgres.write_snapshot(snapshot, self.config.retry_attempts, self.config.retry_backoff_seconds)
        return {**stored, "postgres": postgres}

    def persist_memory(self, event: dict[str, Any]) -> dict[str, Any]:
        stored = self.local_state.append_memory(event)
        postgres = self.postgres.write_memory(event, self.config.retry_attempts, self.config.retry_backoff_seconds)
        qdrant = self.qdrant.upsert_event(event, self.config.retry_attempts, self.config.retry_backoff_seconds)
        return {**stored, "postgres": postgres, "qdrant": qdrant}

    def export_graph(self, graph: dict[str, Any]) -> dict[str, Any]:
        statements = self.neo4j.export_cypher(graph)
        return {"backend": "neo4j", "configured": self.neo4j.is_configured(), "statement_count": len(statements), "statements": statements}

    def write_graph(self, graph: dict[str, Any]) -> dict[str, Any]:
        return self.neo4j.write_graph(graph, self.config.retry_attempts, self.config.retry_backoff_seconds)

    def migrate(self) -> dict[str, Any]:
        return {"postgres": self.postgres.migrate(self.config.retry_attempts, self.config.retry_backoff_seconds)}

    def enqueue_task(self, task: dict[str, Any]) -> dict[str, Any]:
        return self.redis.enqueue(task, self.config.retry_attempts, self.config.retry_backoff_seconds)

    def dequeue_tasks(self, count: int = 1) -> list[dict[str, Any]]:
        return self.redis.dequeue(count=count, retry_attempts=self.config.retry_attempts, retry_backoff_seconds=self.config.retry_backoff_seconds)

    def ack_task(self, task_id: str) -> dict[str, Any]:
        return self.redis.ack(task_id, self.config.retry_attempts, self.config.retry_backoff_seconds)


def _hash_embedding(text: str, size: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = []
    for idx in range(size):
        byte = digest[idx % len(digest)]
        values.append(round((byte / 127.5) - 1, 6))
    return values


def _node_to_dict(node: Any) -> dict[str, Any]:
    return {"id": node.id, "type": node.type, "properties": node.properties}


def _edge_to_dict(edge: Any) -> dict[str, Any]:
    return {"source": edge.source, "target": edge.target, "relation_type": edge.relation_type, "weight": edge.weight, "properties": edge.properties}


def _retry(operation: Callable[[], Any], attempts: int, backoff_seconds: float) -> Any:
    last_error: Exception | None = None
    for attempt in range(max(attempts, 1)):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt < max(attempts, 1) - 1:
                time.sleep(backoff_seconds * (attempt + 1))
    raise last_error  # type: ignore[misc]


def _safe_external_check(operation: Callable[[], dict[str, Any]], attempts: int, backoff_seconds: float) -> dict[str, Any]:
    try:
        return _retry(operation, attempts, backoff_seconds)
    except Exception as exc:
        return {"configured": True, "ready": False, "error": type(exc).__name__, "detail": str(exc)}


def _decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _redact(value: str) -> str:
    if not value:
        return ""
    if "@" not in value:
        return value
    prefix, suffix = value.rsplit("@", 1)
    scheme = prefix.split("://", 1)[0] if "://" in prefix else "service"
    return f"{scheme}://***@{suffix}"
