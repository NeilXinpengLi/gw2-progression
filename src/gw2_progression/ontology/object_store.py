"""Ontology Object and Relation Store.

In-memory dict-based registry with optional SQLite persistence.
MVP uses dicts (not Neo4j/RDF) for simplicity and speed.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from ..database import using_db
from .exceptions import PersistenceError
from .models import OntologyAction, OntologyObject, OntologyRelation

logger = logging.getLogger("gw2.ontology.store")

_objects: dict[str, OntologyObject] = {}
_relations: dict[str, OntologyRelation] = {}
_objects_by_class: dict[str, dict[str, OntologyObject]] = {}
_relations_by_source: dict[str, list[OntologyRelation]] = {}
_relations_by_target: dict[str, list[OntologyRelation]] = {}
_relations_by_type: dict[str, list[OntologyRelation]] = {}


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _object_id(class_name: str, suffix: str = "") -> str:
    raw = f"{class_name}_{uuid.uuid4().hex[:12]}"
    if suffix:
        raw = f"{raw}_{suffix}"
    return raw


def _reindex(obj: OntologyObject) -> None:
    _objects[obj.object_id] = obj
    _objects_by_class.setdefault(obj.class_name, {})[obj.object_id] = obj


def _index_relation(rel: OntologyRelation) -> None:
    _relations[rel.relation_id] = rel
    _relations_by_source.setdefault(rel.source_id, []).append(rel)
    _relations_by_target.setdefault(rel.target_id, []).append(rel)
    _relations_by_type.setdefault(rel.relation_type, []).append(rel)


def register_object(
    class_name: str,
    account_name: str = "",
    properties: dict | None = None,
    privacy_scope: str = "private",
    source_object_id: str = "",
    object_id: str = "",
) -> OntologyObject:
    now = _ts()
    obj = OntologyObject(
        object_id=object_id or _object_id(class_name),
        class_name=class_name,
        account_name=account_name,
        properties=properties or {},
        qa_status="pending",
        privacy_scope=privacy_scope,
        revision=1,
        source_object_id=source_object_id,
        created_at=now,
        updated_at=now,
    )
    _reindex(obj)
    return obj


def get_object(object_id: str) -> OntologyObject | None:
    return _objects.get(object_id)


def get_objects_by_class(class_name: str) -> list[OntologyObject]:
    return list(_objects_by_class.get(class_name, {}).values())


def get_objects_by_account(class_name: str, account_name: str) -> list[OntologyObject]:
    return [
        o for o in _objects_by_class.get(class_name, {}).values()
        if o.account_name == account_name
    ]


def update_object(object_id: str, **updates: Any) -> OntologyObject | None:
    obj = _objects.get(object_id)
    if not obj:
        return None
    for key, val in updates.items():
        if hasattr(obj, key):
            setattr(obj, key, val)
    obj.updated_at = _ts()
    obj.revision += 1
    return obj


def delete_object(object_id: str) -> bool:
    obj = _objects.pop(object_id, None)
    if not obj:
        return False
    _objects_by_class.get(obj.class_name, {}).pop(object_id, None)
    for rel in list(_relations_by_source.get(object_id, [])):
        delete_relation(rel.relation_id)
    for rel in list(_relations_by_target.get(object_id, [])):
        delete_relation(rel.relation_id)
    return True


def register_relation(
    source_id: str,
    target_id: str,
    relation_type: str,
    properties: dict | None = None,
    confidence: float = 1.0,
) -> OntologyRelation:
    rel = OntologyRelation(
        relation_id=f"rel_{uuid.uuid4().hex[:12]}",
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        properties=properties or {},
        confidence=confidence,
        created_at=_ts(),
    )
    _index_relation(rel)
    return rel


def get_relation(relation_id: str) -> OntologyRelation | None:
    return _relations.get(relation_id)


def get_relations(source_id: str | None = None, target_id: str | None = None, relation_type: str | None = None) -> list[OntologyRelation]:
    results: list[OntologyRelation] = []
    if source_id:
        results = list(_relations_by_source.get(source_id, []))
    elif target_id:
        results = list(_relations_by_target.get(target_id, []))
    elif relation_type:
        results = list(_relations_by_type.get(relation_type, []))
    else:
        results = list(_relations.values())

    if relation_type and results:
        results = [r for r in results if r.relation_type == relation_type]
    return results


def delete_relation(relation_id: str) -> bool:
    rel = _relations.pop(relation_id, None)
    if not rel:
        return False
    _relations_by_source.get(rel.source_id, []).remove(rel)
    _relations_by_target.get(rel.target_id, []).remove(rel)
    _relations_by_type.get(rel.relation_type, []).remove(rel)
    return True


def clear() -> None:
    _objects.clear()
    _relations.clear()
    _objects_by_class.clear()
    _relations_by_source.clear()
    _relations_by_target.clear()
    _relations_by_type.clear()
    _prop_index.clear()


# ── Performance: Batch Operations ─────────────────────────────────────


def register_objects(objects: list[dict]) -> list[OntologyObject]:
    return [register_object(**spec) for spec in objects]


def register_relations(relations: list[dict]) -> list[OntologyRelation]:
    return [register_relation(**spec) for spec in relations]


def get_objects_by_property(class_name: str, property_key: str, property_value: Any) -> list[OntologyObject]:
    key = (class_name, property_key, str(property_value))
    cached = _prop_index.get(key)
    if cached is not None:
        return cached
    result = [
        o for o in _objects_by_class.get(class_name, {}).values()
        if o.properties.get(property_key) == property_value
    ]
    if len(_prop_index) < _PROP_INDEX_MAX:
        _prop_index[key] = result
    return result


def get_objects_by_property_batch(class_name: str, filters: dict[str, Any]) -> list[OntologyObject]:
    results = list(_objects_by_class.get(class_name, {}).values())
    for key, val in filters.items():
        results = [o for o in results if o.properties.get(key) == val]
    return results


def count_objects(class_name: str, account_name: str | None = None) -> int:
    if account_name:
        return sum(1 for o in _objects_by_class.get(class_name, {}).values() if o.account_name == account_name)
    return len(_objects_by_class.get(class_name, {}))


def count_relations(relation_type: str | None = None) -> int:
    if relation_type:
        return len(_relations_by_type.get(relation_type, []))
    return len(_relations)


# ── Performance: Property Index ───────────────────────────────────────

_prop_index: dict[tuple[str, str, str], list[OntologyObject]] = {}
_PROP_INDEX_MAX = 1000


def clear_prop_index() -> None:
    _prop_index.clear()


# ── Performance: Pagination ───────────────────────────────────────────

def get_objects_paginated(class_name: str, offset: int = 0, limit: int = 50) -> list[OntologyObject]:
    all_objs = sorted(
        _objects_by_class.get(class_name, {}).values(),
        key=lambda o: o.created_at,
        reverse=True,
    )
    return all_objs[offset:offset + limit]


_MAX_RETRIES = 3
_RETRY_DELAY = 0.1


async def _with_retry(coro_factory):
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            return await coro_factory()
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(_RETRY_DELAY * (attempt + 1))
    raise PersistenceError(f"Failed after {_MAX_RETRIES} retries: {last_exc}") from last_exc


# ── Persistence ──────────────────────────────────────────────────────


ONTOLOGY_OBJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS ontology_objects (
    object_id TEXT PRIMARY KEY,
    class_name TEXT NOT NULL,
    account_name TEXT NOT NULL DEFAULT '',
    properties TEXT NOT NULL DEFAULT '{}',
    qa_status TEXT NOT NULL DEFAULT 'pending',
    privacy_scope TEXT NOT NULL DEFAULT 'private',
    revision INTEGER NOT NULL DEFAULT 1,
    source_object_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

ONTOLOGY_RELATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS ontology_relations (
    relation_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    properties TEXT NOT NULL DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL
);
"""

ONTOLOGY_ACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS ontology_actions (
    action_id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    account_name TEXT NOT NULL DEFAULT '',
    params TEXT NOT NULL DEFAULT '{}',
    preconditions_met INTEGER NOT NULL DEFAULT 0,
    affected_object_ids TEXT NOT NULL DEFAULT '[]',
    rollback_strategy TEXT NOT NULL DEFAULT 'manual',
    privacy_policy TEXT NOT NULL DEFAULT 'private',
    freshness_policy TEXT NOT NULL DEFAULT 'any',
    qa_status TEXT NOT NULL DEFAULT 'pending',
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT ''
);
"""


async def persist_object(obj: OntologyObject) -> None:
    async def _do():
        async with using_db() as conn:
            await conn.execute(
                """INSERT OR REPLACE INTO ontology_objects
                (object_id, class_name, account_name, properties, qa_status, privacy_scope,
                 revision, source_object_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    obj.object_id,
                    obj.class_name,
                    obj.account_name,
                    json.dumps(obj.properties),
                    obj.qa_status,
                    obj.privacy_scope,
                    obj.revision,
                    obj.source_object_id,
                    obj.created_at,
                    obj.updated_at,
                ),
            )
    await _with_retry(_do)


async def persist_relation(rel: OntologyRelation) -> None:
    async def _do():
        async with using_db() as conn:
            await conn.execute(
                """INSERT OR REPLACE INTO ontology_relations
                (relation_id, source_id, target_id, relation_type, properties, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    rel.relation_id,
                    rel.source_id,
                    rel.target_id,
                    rel.relation_type,
                    json.dumps(rel.properties),
                    rel.confidence,
                    rel.created_at,
                ),
            )
    await _with_retry(_do)


async def persist_action(action: OntologyAction) -> None:
    async def _do():
        async with using_db() as conn:
            await conn.execute(
                """INSERT OR REPLACE INTO ontology_actions
                (action_id, action_type, account_name, params, preconditions_met,
                 affected_object_ids, rollback_strategy, privacy_policy, freshness_policy,
                 qa_status, status, error, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    action.action_id,
                    action.action_type,
                    action.account_name,
                    json.dumps(action.params),
                    1 if action.preconditions_met else 0,
                    json.dumps(action.affected_object_ids),
                    action.rollback_strategy,
                    action.privacy_policy,
                    action.freshness_policy,
                    action.qa_status,
                    action.status,
                    action.error,
                    action.created_at,
                    action.completed_at,
                ),
            )
    await _with_retry(_do)


async def load_objects(account_name: str | None = None) -> list[OntologyObject]:
    results: list[OntologyObject] = []
    async with using_db() as conn:
        if account_name:
            cursor = await conn.execute(
                "SELECT * FROM ontology_objects WHERE account_name = ? ORDER BY created_at DESC",
                (account_name,),
            )
        else:
            cursor = await conn.execute("SELECT * FROM ontology_objects ORDER BY created_at DESC")
        rows = await cursor.fetchall()
    for row in rows:
        obj = OntologyObject(
            object_id=row["object_id"],
            class_name=row["class_name"],
            account_name=row["account_name"],
            properties=json.loads(row["properties"]) if row["properties"] else {},
            qa_status=row["qa_status"],
            privacy_scope=row["privacy_scope"],
            revision=row["revision"],
            source_object_id=row["source_object_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        _reindex(obj)
        results.append(obj)
    return results


async def load_relations() -> list[OntologyRelation]:
    results: list[OntologyRelation] = []
    async with using_db() as conn:
        cursor = await conn.execute("SELECT * FROM ontology_relations ORDER BY created_at DESC")
        rows = await cursor.fetchall()
    for row in rows:
        rel = OntologyRelation(
            relation_id=row["relation_id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            relation_type=row["relation_type"],
            properties=json.loads(row["properties"]) if row["properties"] else {},
            confidence=row["confidence"],
            created_at=row["created_at"],
        )
        _index_relation(rel)
        results.append(rel)
    return results
