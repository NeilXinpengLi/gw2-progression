"""Deterministic ontology runtime kernel.

This module is the small executable core behind the ontology layer: schemas are
registered up front, every mutation is validated, lineage is recorded, and the
lineage log can replay into the same final state.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

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
class CompiledRuntimeGraph:
    """Foundry-level compiled runtime graph manifest."""

    graph_id: str
    execution_graph: "ExecutionGraph"
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "manifest": copy.deepcopy(self.manifest),
            "nodes": [
                {
                    "node_id": node.node_id,
                    "depends_on": list(node.depends_on),
                    "action": copy.deepcopy(node.action),
                }
                for node in self.execution_graph.topological_order()
            ],
        }


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


@dataclass(frozen=True)
class Entity:
    id: str
    type: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_action_entity(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "properties": copy.deepcopy(self.attributes)}


@dataclass(frozen=True)
class Relation:
    src: str
    dst: str
    rtype: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_action_relation(self) -> dict[str, Any]:
        return {
            "source": self.src,
            "target": self.dst,
            "relation_type": self.rtype,
            "properties": copy.deepcopy(self.attributes),
        }


class Graph:
    """Minimal graph representation produced by ingestion/normalization."""

    def __init__(self) -> None:
        self.nodes: dict[str, Entity] = {}
        self.edges: list[Relation] = []

    def add_node(self, node: Entity) -> Entity:
        self.nodes[node.id] = node
        return node

    def add_edge(self, relation: Relation) -> Relation:
        self.edges.append(relation)
        return relation

    def to_actions(self) -> list[dict[str, Any]]:
        actions = [{"type": "add_entity", "entity": entity.to_action_entity()} for entity in self.nodes.values()]
        actions.extend({"type": "add_relation", "relation": relation.to_action_relation()} for relation in self.edges)
        return actions


class GraphBuilder:
    """Build a deterministic action graph from normalized entities/relations."""

    def build(self, entities: list[dict[str, Any]], relations: list[dict[str, Any]]) -> Graph:
        graph = Graph()
        for entity in entities:
            graph.add_node(Entity(
                id=str(entity.get("id") or entity.get("object_id") or ""),
                type=str(entity.get("type") or entity.get("class_name") or ""),
                attributes=copy.deepcopy(entity.get("properties", entity.get("attributes", {}))),
            ))
        for relation in relations:
            graph.add_edge(Relation(
                src=str(relation.get("source") or relation.get("src") or relation.get("source_id") or ""),
                dst=str(relation.get("target") or relation.get("dst") or relation.get("target_id") or ""),
                rtype=str(relation.get("relation_type") or relation.get("rtype") or relation.get("type") or ""),
                attributes=copy.deepcopy(relation.get("properties", relation.get("attributes", {}))),
            ))
        return graph


class GW2APINormalizer:
    """Normalize small GW2 account-like payloads into ontology entities."""

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        account = raw.get("account", {}) if isinstance(raw.get("account"), dict) else {}
        account_name = str(account.get("name") or raw.get("account_name") or "unknown")
        snapshot_id = str(raw.get("snapshot_id") or raw.get("run_id") or raw.get("exported_at") or "snapshot")
        account_id = f"account:{account_name}"
        entities = [{
            "id": account_id,
            "type": "account_snapshot",
            "properties": {"account_name": account_name, "snapshot_id": snapshot_id},
        }]
        relations: list[dict[str, Any]] = []
        assets = raw.get("assets", [])
        if isinstance(assets, list):
            for index, asset in enumerate(asset for asset in assets if isinstance(asset, dict)):
                item_id = int(asset.get("item_id", asset.get("id", index + 1)) or index + 1)
                location = str(asset.get("location", asset.get("category", "unknown")))
                asset_id = f"asset:{account_name}:{location}:{item_id}:{index}"
                entities.append({
                    "id": asset_id,
                    "type": "account_asset",
                    "properties": {
                        "item_id": item_id,
                        "count": int(asset.get("count", 1) or 0),
                        "location": location,
                        "value": int(asset.get("total_value", asset.get("value", 0)) or 0),
                    },
                })
                relations.append({"source": account_id, "target": asset_id, "relation_type": "owns"})
        return {"entities": entities, "relations": relations}


class GW2API:
    """Tiny GW2 API wrapper for runtime ingestion pipelines."""

    BASE = "https://api.guildwars2.com/v2"

    def __init__(self, fetcher: Callable[[str], Any] | None = None, base_url: str | None = None) -> None:
        self.fetcher = fetcher
        self.base_url = (base_url or self.BASE).rstrip("/")

    def fetch(self, endpoint: str) -> Any:
        endpoint = endpoint.strip("/")
        url = f"{self.base_url}/{endpoint}"
        if self.fetcher:
            return self.fetcher(url)
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()


class DGSKIngestor:
    """Convert normalized ontology payloads into runtime graph actions."""

    def __init__(self, graph_builder: GraphBuilder | None = None) -> None:
        self.graph_builder = graph_builder or GraphBuilder()

    def build_graph(self, normalized: dict[str, Any]) -> Graph:
        return self.graph_builder.build(
            list(normalized.get("entities", [])),
            list(normalized.get("relations", [])),
        )

    def ingest(self, normalized: dict[str, Any], kernel: "OntologyRuntimeKernel") -> dict[str, Any]:
        graph = self.build_graph(normalized)
        results = [kernel.execute(action) for action in graph.to_actions()]
        return {
            "status": "completed",
            "entity_count": len(graph.nodes),
            "relation_count": len(graph.edges),
            "action_count": len(results),
            "state_hash": _stable_hash(kernel.state.to_dict()),
            "results": results,
            "dgsk": {"node_ids": sorted(graph.nodes), "edge_count": len(graph.edges)},
        }


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
        registry.register_entity(EntitySchema(
            name="decision_record",
            required_attributes=("decision", "score", "source"),
            constraints=("deterministic_decision",),
        ))
        registry.register_entity(EntitySchema(
            name="policy_weight",
            required_attributes=("policy", "weight", "source"),
            constraints=("bounded_weight",),
        ))
        registry.register_relation(RelationSchema(
            relation_type="recommends",
            source_entity="decision_record",
            target_entity=None,
        ))
        registry.register_action(ActionSchema(
            action_type="record_decision",
            input_schema={"decision": "dict"},
            effects=("creates decision_record entity",),
        ))
        registry.register_action(ActionSchema(
            action_type="apply_policy_weight",
            input_schema={"policy": "dict"},
            effects=("creates policy_weight entity",),
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
        elif action_type == "record_decision":
            decision = action.get("decision", {})
            if not isinstance(decision, dict):
                errors.append("decision must be a dict")
            else:
                record = {
                    "type": "decision_record",
                    "properties": {
                        "decision": decision.get("decision", ""),
                        "score": decision.get("score", 0),
                        "source": decision.get("source", ""),
                    },
                }
                errors.extend(self.validate_entity(record))
        elif action_type == "apply_policy_weight":
            policy = action.get("policy", {})
            if not isinstance(policy, dict):
                errors.append("policy must be a dict")
            else:
                record = {
                    "type": "policy_weight",
                    "properties": {
                        "policy": policy.get("policy", ""),
                        "weight": policy.get("weight", 0),
                        "source": policy.get("source", ""),
                    },
                }
                errors.extend(self.validate_entity(record))
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
        elif action_type == "record_decision":
            decision = copy.deepcopy(action["decision"])
            decision_id = str(decision.get("id") or f"decision:{_stable_hash(decision)[:12]}")
            new_state.entities[decision_id] = {
                "id": decision_id,
                "type": "decision_record",
                "properties": {
                    "decision": str(decision.get("decision", "")),
                    "score": float(decision.get("score", 0) or 0),
                    "source": str(decision.get("source", "")),
                    "weights": copy.deepcopy(decision.get("weights", {})),
                    "rationale": str(decision.get("rationale", "")),
                },
            }
        elif action_type == "apply_policy_weight":
            policy = copy.deepcopy(action["policy"])
            policy_id = str(policy.get("id") or f"policy:{_stable_hash(policy)[:12]}")
            new_state.entities[policy_id] = {
                "id": policy_id,
                "type": "policy_weight",
                "properties": {
                    "policy": str(policy.get("policy", "")),
                    "weight": float(policy.get("weight", 0) or 0),
                    "source": str(policy.get("source", "")),
                    "reward": float(policy.get("reward", 0) or 0),
                },
            }
        else:
            raise OntologyViolation(f"Unsupported executable action: {action_type}")
        return {"new_state": new_state, "delta": _compute_delta(before, new_state.to_dict())}


class LineageTracker:
    """Records deterministic before/action/after lineage for replay."""

    def __init__(self, store: "LineageStore | None" = None) -> None:
        self.records: list[dict[str, Any]] = []
        self.store = store or LineageStore()

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
        self.store.append(record)
        return copy.deepcopy(record)

    def export(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.records)


class LineageStore:
    """Durable-store-shaped in-memory lineage log for the MVP runtime."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        self._records.append(copy.deepcopy(record))
        return copy.deepcopy(record)

    def list(self, limit: int | None = None) -> list[dict[str, Any]]:
        records = self._records if limit is None else self._records[-max(int(limit), 0):]
        return copy.deepcopy(records)

    def clear(self) -> None:
        self._records.clear()

    def replayable_actions(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(record.get("action", {})) for record in self._records]


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


@dataclass(frozen=True)
class ExecutionGraphNode:
    node_id: str
    action: dict[str, Any]
    depends_on: tuple[str, ...] = ()


class ExecutionGraph:
    """Deterministic DAG of ontology actions."""

    def __init__(self, nodes: list[ExecutionGraphNode] | None = None) -> None:
        self.nodes: dict[str, ExecutionGraphNode] = {}
        for node in nodes or []:
            self.add_node(node)

    def add_node(self, node: ExecutionGraphNode) -> ExecutionGraphNode:
        if node.node_id in self.nodes:
            raise OntologyViolation(f"Duplicate execution node: {node.node_id}")
        self.nodes[node.node_id] = node
        return node

    @classmethod
    def from_actions(cls, actions: list[dict[str, Any]]) -> "ExecutionGraph":
        nodes = []
        previous = ""
        for index, action in enumerate(actions, start=1):
            node_id = str(action.get("node_id") or f"step:{index}")
            depends_on = tuple(action.get("depends_on", [previous] if previous else []))
            clean_action = {key: copy.deepcopy(value) for key, value in action.items() if key not in {"node_id", "depends_on"}}
            nodes.append(ExecutionGraphNode(node_id=node_id, action=clean_action, depends_on=depends_on))
            previous = node_id
        return cls(nodes)

    def topological_order(self) -> list[ExecutionGraphNode]:
        ordered: list[ExecutionGraphNode] = []
        temporary: set[str] = set()
        permanent: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in permanent:
                return
            if node_id in temporary:
                raise OntologyViolation(f"Cycle detected in execution graph at {node_id}")
            node = self.nodes.get(node_id)
            if not node:
                raise OntologyViolation(f"Missing dependency node: {node_id}")
            temporary.add(node_id)
            for dependency in sorted(node.depends_on):
                visit(dependency)
            temporary.remove(node_id)
            permanent.add(node_id)
            ordered.append(node)

        for node_id in sorted(self.nodes):
            visit(node_id)
        return ordered


class DAGExecutor:
    """Executes ontology action DAGs through the same validated runtime path."""

    def __init__(self, kernel: "OntologyRuntimeKernel") -> None:
        self.kernel = kernel

    def execute(self, graph: ExecutionGraph) -> dict[str, Any]:
        results = []
        for node in graph.topological_order():
            result = self.kernel.execute(node.action)
            results.append({"node_id": node.node_id, "status": result["status"], "result": result})
        return {
            "status": "completed",
            "executed": len(results),
            "results": results,
            "state_hash": self.kernel.snapshot()["state_hash"],
        }


class ExecutionGraphCompiler:
    """Compiles ontology actions and registry metadata into a deterministic DAG manifest."""

    def __init__(self, registry: OntologyRegistry) -> None:
        self.registry = registry

    def compile(self, actions: list[dict[str, Any]] | None = None, graph_id: str = "runtime") -> CompiledRuntimeGraph:
        execution_graph = ExecutionGraph.from_actions(actions or [])
        ordered = execution_graph.topological_order()
        manifest = {
            "kernel_version": "v2-foundry",
            "graph_id": graph_id,
            "node_count": len(ordered),
            "action_types": [str(node.action.get("type") or node.action.get("action_type") or "") for node in ordered],
            "ontology": {
                "entities": sorted(self.registry.entities),
                "relations": sorted(self.registry.relations),
                "actions": sorted(self.registry.actions),
            },
            "guarantees": {
                "deterministic_execution": True,
                "ontology_enforcement": True,
                "dag_compilation": True,
                "lineage_replay": True,
                "constrained_reasoning": True,
            },
        }
        return CompiledRuntimeGraph(
            graph_id=f"{graph_id}:{_stable_hash(manifest)[:12]}",
            execution_graph=execution_graph,
            manifest=manifest,
        )


class BORSDecisionLayer:
    """Deterministic decision layer that emits ontology actions, not side effects."""

    def __init__(self, kernel: "OntologyRuntimeKernel") -> None:
        self.kernel = kernel

    def decide(self, objective: str = "BALANCED", weights: dict[str, float] | None = None) -> dict[str, Any]:
        weights = weights or self._derive_weights()
        if not weights:
            weights = {"HOLD": 1.0}
        decision, score = max(sorted(weights.items()), key=lambda item: item[1])
        payload = {
            "id": f"decision:{objective.lower()}:{_stable_hash(weights)[:8]}",
            "decision": decision,
            "score": round(float(score), 6),
            "source": "BORS",
            "weights": weights,
            "rationale": f"{decision} has the highest deterministic score for {objective}.",
        }
        action = {"type": "record_decision", "decision": payload}
        compiled = self.kernel.compile([action], graph_id=f"bors:{objective.lower()}")
        return {
            "decision": payload,
            "compiled_graph": compiled.to_dict(),
            "execution": self.kernel.execute_compiled(compiled),
        }

    def _derive_weights(self) -> dict[str, float]:
        total_value = 0.0
        low_count_assets = 0
        for entity in self.kernel.state.entities.values():
            props = entity.get("properties", {})
            count = float(props.get("count", 0) or 0)
            value = float(props.get("value", props.get("unit_value", 0)) or 0)
            total_value += count * value
            if entity.get("type") == "account_asset" and count <= 1:
                low_count_assets += 1
        return {
            "BUY": 0.25 if total_value < 10000 else 0.15,
            "SELL": 0.45 if total_value >= 10000 else 0.2,
            "HOLD": 0.35 + min(low_count_assets * 0.05, 0.2),
        }


class RLOptimizationLayer:
    """Policy optimizer facade that records learned weights through the kernel."""

    def __init__(self, kernel: "OntologyRuntimeKernel") -> None:
        self.kernel = kernel

    def optimize(self, rewards: dict[str, float] | None = None) -> dict[str, Any]:
        rewards = rewards or {"balanced": 0.0}
        total = sum(abs(float(value)) for value in rewards.values()) or 1.0
        actions = []
        policies = []
        for name in sorted(rewards):
            reward = float(rewards[name])
            weight = round(abs(reward) / total, 6)
            policy = {
                "id": f"policy:{name}:{_stable_hash({'name': name, 'reward': reward})[:8]}",
                "policy": name,
                "weight": weight,
                "reward": reward,
                "source": "RL",
            }
            policies.append(policy)
            actions.append({"type": "apply_policy_weight", "policy": policy})
        compiled = self.kernel.compile(actions, graph_id="rl:policy-optimization")
        return {
            "policies": policies,
            "compiled_graph": compiled.to_dict(),
            "execution": self.kernel.execute_compiled(compiled),
        }


class OOSKSimulation:
    """Time-stepped world evolution using validated ontology actions."""

    def __init__(self, kernel: "OntologyRuntimeKernel") -> None:
        self.kernel = kernel
        self.time = 0

    def run(self, steps: list[dict[str, Any]], ticks: int = 1) -> dict[str, Any]:
        ticks = max(int(ticks), 1)
        timeline = []
        for _ in range(ticks):
            self.time += 1
            executed = []
            for step in steps:
                result = self.kernel.execute(step)
                executed.append(result)
            timeline.append({
                "tick": self.time,
                "executed": len(executed),
                "state_hash": self.kernel.snapshot()["state_hash"],
                "results": executed,
            })
        return {
            "status": "completed",
            "time": self.time,
            "timeline": timeline,
            "state_hash": self.kernel.snapshot()["state_hash"],
        }


class LLMConstrainedReasoning:
    """Accepts only LLM-proposed actions that validate against ontology state."""

    def __init__(self, kernel: "OntologyRuntimeKernel") -> None:
        self.kernel = kernel

    def validate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        validation = self.kernel.validate_llm_action(candidate)
        return {
            "accepted": validation["accepted"],
            "errors": validation["errors"],
            "reasoning_mode": "ontology_constrained",
            "action": validation["action"],
        }

    def execute(self, candidate: dict[str, Any]) -> dict[str, Any]:
        validation = self.validate(candidate)
        if not validation["accepted"]:
            return {"status": "rejected", "validation": validation}
        return {"status": "accepted", "validation": validation, "execution": self.kernel.execute(candidate)}


class OntologyRuntimeKernel:
    """High-level facade combining registry, execution, queries, and replay."""

    def __init__(self, registry: OntologyRegistry | None = None) -> None:
        self.registry = registry or OntologyRegistry.from_project_config()
        self.state = KernelState()
        self.lineage_store = LineageStore()
        self.lineage = LineageTracker(self.lineage_store)
        self.execution = ExecutionEngine(self.registry, lineage=self.lineage)
        self.compiler = ExecutionGraphCompiler(self.registry)
        self.simulation = OOSKSimulation(self)
        self.reasoning = LLMConstrainedReasoning(self)
        self.bors = BORSDecisionLayer(self)
        self.rl = RLOptimizationLayer(self)
        self.ingestor = DGSKIngestor()

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        result = self.execution.execute(action, self.state)
        self.state = result["state"]
        return {
            "status": result["status"],
            "state_hash": _stable_hash(self.state.to_dict()),
            "delta": result["delta"],
            "lineage": result["lineage"],
        }

    def ingest_normalized(self, normalized: dict[str, Any]) -> dict[str, Any]:
        return self.ingestor.ingest(normalized, self)

    def ingest_raw_gw2(self, raw: dict[str, Any]) -> dict[str, Any]:
        normalized = GW2APINormalizer().normalize(raw)
        result = self.ingest_normalized(normalized)
        return {**result, "normalized": normalized}

    def execute_graph(self, actions: list[dict[str, Any]]) -> dict[str, Any]:
        return self.execute_compiled(self.compile(actions, graph_id="ad-hoc"))

    def compile(self, actions: list[dict[str, Any]] | None = None, graph_id: str = "runtime") -> CompiledRuntimeGraph:
        return self.compiler.compile(actions or [], graph_id=graph_id)

    def execute_compiled(self, compiled: CompiledRuntimeGraph | dict[str, Any]) -> dict[str, Any]:
        if isinstance(compiled, CompiledRuntimeGraph):
            graph = compiled.execution_graph
            graph_id = compiled.graph_id
            manifest = compiled.manifest
        else:
            graph = ExecutionGraph.from_actions(list(compiled.get("actions", [])))
            graph_id = str(compiled.get("graph_id", "runtime"))
            manifest = {"graph_id": graph_id}
        result = DAGExecutor(self).execute(graph)
        return {
            **result,
            "graph_id": graph_id,
            "manifest": copy.deepcopy(manifest),
        }

    def simulate(self, steps: list[dict[str, Any]], ticks: int = 1) -> dict[str, Any]:
        return self.simulation.run(steps, ticks=ticks)

    def validate_llm_action(self, candidate: dict[str, Any]) -> dict[str, Any]:
        errors = self.registry.validate_action(candidate, self.state)
        return {
            "accepted": not errors,
            "errors": errors,
            "action": copy.deepcopy(candidate) if not errors else None,
        }

    def execute_llm_action(self, candidate: dict[str, Any]) -> dict[str, Any]:
        return self.reasoning.execute(candidate)

    def decide(self, objective: str = "BALANCED", weights: dict[str, float] | None = None) -> dict[str, Any]:
        return self.bors.decide(objective=objective, weights=weights)

    def optimize_policy(self, rewards: dict[str, float] | None = None) -> dict[str, Any]:
        return self.rl.optimize(rewards=rewards)

    def query(self) -> QueryEngine:
        return QueryEngine(self.state)

    def replay(self, lineage_log: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return ReplayEngine(self.registry).replay(lineage_log or self.lineage.export())

    def snapshot(self) -> dict[str, Any]:
        return {
            "kernel_version": "v2-foundry",
            "state": self.state.to_dict(),
            "state_hash": _stable_hash(self.state.to_dict()),
            "lineage": self.lineage_store.list(),
            "compiled_guarantees": self.guarantees(),
        }

    def guarantees(self) -> dict[str, Any]:
        replay = self.replay(self.lineage_store.list())
        return {
            "kernel_version": "v2-foundry",
            "everything_is_execution_graph": True,
            "deterministic_execution": replay["deterministic"],
            "full_traceability": all("action_hash" in record and "to" in record for record in self.lineage_store.list()),
            "ontology_enforcement": True,
            "graph_compilation": True,
            "constrained_ai_reasoning": True,
            "lineage_replay": replay["deterministic"] and not replay["mismatches"],
            "mismatches": replay["mismatches"],
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
