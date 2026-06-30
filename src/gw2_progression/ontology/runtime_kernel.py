"""Deterministic ontology runtime kernel.

This module is the small executable core behind the ontology layer: schemas are
registered up front, every mutation is validated, lineage is recorded, and the
lineage log can replay into the same final state.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .config import ACTION_DEFINITIONS, CLASS_DEFINITIONS, RELATION_DEFINITIONS


class OntologyViolation(ValueError):
    """Raised when a runtime action violates ontology schema or state rules."""


@dataclass(frozen=True)
class EntitySchema:
    name: str
    required_attributes: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationSchema:
    relation_type: str
    source_entity: str | None = None
    target_entity: str | None = None
    cardinality: str = "many"
    allow_multiple: bool = True


@dataclass(frozen=True)
class ActionSchema:
    action_type: str
    input_schema: dict[str, str] = field(default_factory=dict)
    preconditions: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()


@dataclass(frozen=True)
class KernelState:
    entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    relations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": copy.deepcopy(self.entities),
            "relations": copy.deepcopy(self.relations),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None = None) -> "KernelState":
        value = value or {}
        return cls(
            entities=copy.deepcopy(value.get("entities", {})),
            relations=copy.deepcopy(value.get("relations", [])),
        )


class OntologyRegistry:
    """In-memory schema registry for entity, relation, and action definitions."""

    def __init__(self) -> None:
        self.entities: dict[str, EntitySchema] = {}
        self.relations: dict[str, RelationSchema] = {}
        self.actions: dict[str, ActionSchema] = {}

    @classmethod
    def from_project_config(cls) -> "OntologyRegistry":
        registry = cls()
        for name, definition in CLASS_DEFINITIONS.items():
            registry.register_entity(EntitySchema(
                name=name,
                required_attributes=tuple(definition.get("required_properties", [])),
                constraints=tuple(definition.get("qa_checks", [])),
            ))
        for relation_type, definition in RELATION_DEFINITIONS.items():
            registry.register_relation(RelationSchema(
                relation_type=relation_type,
                source_entity=definition.get("source_class"),
                target_entity=definition.get("target_class"),
                allow_multiple=bool(definition.get("allow_multiple", True)),
                cardinality="many" if definition.get("allow_multiple", True) else "one",
            ))
        for action_type, definition in ACTION_DEFINITIONS.items():
            registry.register_action(ActionSchema(
                action_type=action_type,
                input_schema=dict(definition.get("input_schema", {})),
                preconditions=tuple(definition.get("preconditions", [])),
                effects=tuple(definition.get("effects", [])),
            ))
        registry.register_action(ActionSchema(
            action_type="add_entity",
            input_schema={"entity": "dict"},
            effects=("creates entity",),
        ))
        registry.register_action(ActionSchema(
            action_type="add_relation",
            input_schema={"relation": "dict"},
            effects=("creates relation",),
        ))
        registry.register_action(ActionSchema(
            action_type="update_entity",
            input_schema={"entity_id": "string", "patch": "dict"},
            preconditions=("entity_exists",),
            effects=("updates entity properties",),
        ))
        return registry

    def register_entity(self, schema: EntitySchema) -> EntitySchema:
        self.entities[schema.name] = schema
        return schema

    def register_relation(self, schema: RelationSchema) -> RelationSchema:
        self.relations[schema.relation_type] = schema
        return schema

    def register_action(self, schema: ActionSchema) -> ActionSchema:
        self.actions[schema.action_type] = schema
        return schema

    def validate_entity(self, entity: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        entity_type = str(entity.get("type") or entity.get("class_name") or "")
        schema = self.entities.get(entity_type)
        if not schema:
            return [f"Unknown entity type: {entity_type}"]
        properties = entity.get("properties", {})
        if not isinstance(properties, dict):
            return ["Entity properties must be a dict"]
        for key in schema.required_attributes:
            if key not in properties or properties.get(key) is None:
                errors.append(f"Missing required property: {key}")
        return errors

    def validate_relation(self, relation: dict[str, Any], state: KernelState) -> list[str]:
        errors: list[str] = []
        relation_type = str(relation.get("relation_type") or relation.get("type") or "")
        schema = self.relations.get(relation_type)
        if not schema:
            return [f"Unknown relation type: {relation_type}"]
        source = str(relation.get("source") or "")
        target = str(relation.get("target") or "")
        source_entity = state.entities.get(source)
        target_entity = state.entities.get(target)
        if source not in state.entities:
            errors.append(f"Relation source does not exist: {source}")
        if target not in state.entities:
            errors.append(f"Relation target does not exist: {target}")
        if source_entity and schema.source_entity and source_entity.get("type") != schema.source_entity:
            errors.append(f"Relation source must be {schema.source_entity}")
        if target_entity and schema.target_entity and target_entity.get("type") != schema.target_entity:
            errors.append(f"Relation target must be {schema.target_entity}")
        if not schema.allow_multiple:
            for existing in state.relations:
                if (
                    existing.get("source") == source
                    and existing.get("relation_type") == relation_type
                ):
                    errors.append(f"Relation {relation_type} allows only one target per source")
                    break
        return errors

    def validate_action(self, action: dict[str, Any], state: KernelState) -> list[str]:
        action_type = str(action.get("type") or action.get("action_type") or "")
        schema = self.actions.get(action_type)
        if not schema:
            return [f"Unknown action type: {action_type}"]
        errors = self._validate_input_schema(action, schema)
        if action_type == "add_entity":
            entity = action.get("entity", {})
            errors.extend(self.validate_entity(entity if isinstance(entity, dict) else {}))
        elif action_type == "add_relation":
            relation = action.get("relation", {})
            errors.extend(self.validate_relation(relation if isinstance(relation, dict) else {}, state))
        elif action_type == "update_entity":
            entity_id = str(action.get("entity_id") or "")
            if entity_id not in state.entities:
                errors.append(f"Entity does not exist: {entity_id}")
            patch = action.get("patch", {})
            if not isinstance(patch, dict):
                errors.append("patch must be a dict")
        return errors

    def _validate_input_schema(self, action: dict[str, Any], schema: ActionSchema) -> list[str]:
        errors: list[str] = []
        for key, type_name in schema.input_schema.items():
            if key not in action:
                errors.append(f"Missing action input: {key}")
                continue
            if not _matches_type(action[key], type_name):
                errors.append(f"Action input {key} must be {type_name}")
        return errors


class StateEngine:
    """Pure state transition engine for ontology actions."""

    def transition(
        self,
        state: KernelState,
        action: dict[str, Any],
        ontology: OntologyRegistry,
    ) -> dict[str, Any]:
        errors = ontology.validate_action(action, state)
        if errors:
            raise OntologyViolation("; ".join(errors))
        before = state.to_dict()
        new_state = KernelState.from_dict(before)
        action_type = str(action.get("type") or action.get("action_type") or "")
        if action_type == "add_entity":
            entity = copy.deepcopy(action["entity"])
            entity_id = str(entity.get("id") or entity.get("object_id") or "")
            if not entity_id:
                raise OntologyViolation("Entity id is required")
            entity.setdefault("properties", {})
            new_state.entities[entity_id] = entity
        elif action_type == "add_relation":
            relation = copy.deepcopy(action["relation"])
            relation["relation_type"] = relation.get("relation_type") or relation.get("type")
            new_state.relations.append(relation)
        elif action_type == "update_entity":
            entity = copy.deepcopy(new_state.entities[str(action["entity_id"])])
            properties = dict(entity.get("properties", {}))
            properties.update(copy.deepcopy(action.get("patch", {})))
            entity["properties"] = properties
            new_state.entities[str(action["entity_id"])] = entity
        else:
            raise OntologyViolation(f"Unsupported executable action: {action_type}")
        return {"new_state": new_state, "delta": _compute_delta(before, new_state.to_dict())}


class LineageTracker:
    """Records deterministic before/action/after lineage for replay."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(self, before: KernelState, action: dict[str, Any], after: KernelState) -> dict[str, Any]:
        record = {
            "step": len(self.records) + 1,
            "from": _stable_hash(before.to_dict()),
            "action": copy.deepcopy(action),
            "action_hash": _stable_hash(action),
            "to": _stable_hash(after.to_dict()),
            "timestamp": len(self.records) + 1,
        }
        self.records.append(record)
        return copy.deepcopy(record)

    def export(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.records)


class ExecutionEngine:
    """Deterministic action executor with ontology validation and lineage."""

    def __init__(
        self,
        ontology: OntologyRegistry | None = None,
        state_engine: StateEngine | None = None,
        lineage: LineageTracker | None = None,
    ) -> None:
        self.ontology = ontology or OntologyRegistry.from_project_config()
        self.state_engine = state_engine or StateEngine()
        self.lineage = lineage or LineageTracker()

    def execute(self, action: dict[str, Any], state: KernelState | dict[str, Any] | None = None) -> dict[str, Any]:
        before = state if isinstance(state, KernelState) else KernelState.from_dict(state)
        transition = self.state_engine.transition(before, action, self.ontology)
        after: KernelState = transition["new_state"]
        lineage_record = self.lineage.record(before, action, after)
        return {
            "status": "completed",
            "state": after,
            "delta": transition["delta"],
            "lineage": lineage_record,
        }


class QueryEngine:
    """Graph and analytics queries over a kernel state."""

    def __init__(self, state: KernelState) -> None:
        self.state = state

    def traverse(self, start: str, depth: int = 2, relation_type: str | None = None) -> dict[str, Any]:
        seen = {start}
        frontier = [(start, 0)]
        steps: list[dict[str, Any]] = []
        while frontier:
            current, level = frontier.pop(0)
            if level >= depth:
                continue
            for relation in self.state.relations:
                if relation.get("source") != current:
                    continue
                if relation_type and relation.get("relation_type") != relation_type:
                    continue
                target = str(relation.get("target"))
                steps.append({
                    "from": current,
                    "to": target,
                    "relation": relation.get("relation_type"),
                    "depth": level + 1,
                })
                if target not in seen:
                    seen.add(target)
                    frontier.append((target, level + 1))
        return {"start": start, "visited": sorted(seen), "steps": steps}

    def dependencies(self, entity_id: str) -> list[dict[str, Any]]:
        return [copy.deepcopy(rel) for rel in self.state.relations if rel.get("target") == entity_id]

    def lifecycle(self, entity_id: str, lineage_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
        events = []
        for record in lineage_log:
            action = record.get("action", {})
            action_entity = action.get("entity", {}).get("id") or action.get("entity_id")
            relation = action.get("relation", {})
            if action_entity == entity_id or relation.get("source") == entity_id or relation.get("target") == entity_id:
                events.append(copy.deepcopy(record))
        return events

    def economy_impact(self, entity_id: str) -> dict[str, Any]:
        entity = self.state.entities.get(entity_id, {})
        properties = entity.get("properties", {})
        count = int(properties.get("count", 0) or 0)
        value = int(properties.get("value", properties.get("unit_value", 0)) or 0)
        return {
            "entity_id": entity_id,
            "count": count,
            "estimated_value": count * value,
            "relation_count": sum(
                1 for rel in self.state.relations
                if rel.get("source") == entity_id or rel.get("target") == entity_id
            ),
        }


class ReplayEngine:
    """Rebuild state from lineage actions and verify deterministic hashes."""

    def __init__(self, ontology: OntologyRegistry | None = None) -> None:
        self.ontology = ontology or OntologyRegistry.from_project_config()

    def replay(
        self,
        lineage_log: list[dict[str, Any]],
        initial_state: KernelState | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        engine = ExecutionEngine(ontology=self.ontology)
        state = initial_state if isinstance(initial_state, KernelState) else KernelState.from_dict(initial_state)
        mismatches: list[dict[str, Any]] = []
        for record in sorted(lineage_log, key=lambda row: int(row.get("step", 0))):
            result = engine.execute(record["action"], state)
            state = result["state"]
            expected = record.get("to")
            actual = _stable_hash(state.to_dict())
            if expected and expected != actual:
                mismatches.append({"step": record.get("step"), "expected": expected, "actual": actual})
        return {
            "state": state,
            "lineage": engine.lineage.export(),
            "deterministic": not mismatches,
            "mismatches": mismatches,
        }


class OntologyRuntimeKernel:
    """High-level facade combining registry, execution, queries, and replay."""

    def __init__(self, registry: OntologyRegistry | None = None) -> None:
        self.registry = registry or OntologyRegistry.from_project_config()
        self.state = KernelState()
        self.lineage = LineageTracker()
        self.execution = ExecutionEngine(self.registry, lineage=self.lineage)

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        result = self.execution.execute(action, self.state)
        self.state = result["state"]
        return {
            "status": result["status"],
            "state_hash": _stable_hash(self.state.to_dict()),
            "delta": result["delta"],
            "lineage": result["lineage"],
        }

    def validate_llm_action(self, candidate: dict[str, Any]) -> dict[str, Any]:
        errors = self.registry.validate_action(candidate, self.state)
        return {
            "accepted": not errors,
            "errors": errors,
            "action": copy.deepcopy(candidate) if not errors else None,
        }

    def execute_llm_action(self, candidate: dict[str, Any]) -> dict[str, Any]:
        validation = self.validate_llm_action(candidate)
        if not validation["accepted"]:
            return {"status": "rejected", "validation": validation}
        return self.execute(candidate)

    def query(self) -> QueryEngine:
        return QueryEngine(self.state)

    def replay(self, lineage_log: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return ReplayEngine(self.registry).replay(lineage_log or self.lineage.export())

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state.to_dict(),
            "state_hash": _stable_hash(self.state.to_dict()),
            "lineage": self.lineage.export(),
        }


def _matches_type(value: Any, type_name: str) -> bool:
    normalized = type_name.lower()
    if normalized in {"string", "str"}:
        return isinstance(value, str)
    if normalized in {"int", "integer"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if normalized in {"dict", "object"}:
        return isinstance(value, dict)
    if normalized in {"list", "array"}:
        return isinstance(value, list)
    if normalized in {"bool", "boolean"}:
        return isinstance(value, bool)
    return True


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _compute_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_entities = before.get("entities", {})
    after_entities = after.get("entities", {})
    before_relations = before.get("relations", [])
    after_relations = after.get("relations", [])
    added_entities = sorted(set(after_entities) - set(before_entities))
    removed_entities = sorted(set(before_entities) - set(after_entities))
    updated_entities = sorted(
        entity_id
        for entity_id in set(before_entities) & set(after_entities)
        if before_entities[entity_id] != after_entities[entity_id]
    )
    return {
        "added_entities": added_entities,
        "removed_entities": removed_entities,
        "updated_entities": updated_entities,
        "relation_delta": len(after_relations) - len(before_relations),
        "before_hash": _stable_hash(before),
        "after_hash": _stable_hash(after),
    }
