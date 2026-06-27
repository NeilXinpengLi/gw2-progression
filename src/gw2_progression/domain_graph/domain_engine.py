"""Domain Graph Engine — load, validate, compile, and merge Domain Graph YAML.

Three-layer pipeline:
  DGSK: Domain Graph (YAML)
    ↓ compile_to_oosk()
  OOSK: Entity/Relation type registries
    ↓ Runtime operations
  BORS: Business entity mapping
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


# ── Data Models ───────────────────────────────────────────────────────


@dataclass
class NodeProperty:
    name: str
    prop_type: str = "string"
    required: bool = False
    default: Any = None
    enum_values: list[str] | None = None


@dataclass
class NodeDef:
    type: str
    description: str = ""
    properties: list[NodeProperty] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    qa_checks: list[str] = field(default_factory=list)
    privacy_scope: str = "private"


@dataclass
class EdgeDef:
    type: str
    description: str = ""
    source_types: list[str] = field(default_factory=list)
    target_types: list[str] = field(default_factory=list)
    cardinality: str = "N:N"


@dataclass
class DomainEvent:
    name: str
    description: str = ""
    source: str = ""
    triggers: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)


@dataclass
class DomainRule:
    name: str
    description: str = ""
    rule: str = ""
    severity: str = "error"  # error / warning / info


@dataclass
class DomainGraph:
    domain: str = ""
    version: str = "1.0"
    description: str = ""
    nodes: dict[str, NodeDef] = field(default_factory=dict)
    edges: dict[str, EdgeDef] = field(default_factory=dict)
    events: list[DomainEvent] = field(default_factory=list)
    rules: list[DomainRule] = field(default_factory=list)


def _parse_property(raw: str) -> NodeProperty:
    """Parse 'name (type, required/optional)' or 'name (type)'."""
    name_part = raw
    prop_type = "string"
    required = False
    enum_values = None

    if "(" in raw:
        name_part = raw[: raw.index("(")].strip()
        meta = raw[raw.index("(") + 1 : raw.index(")")].strip()
        parts = [p.strip() for p in meta.split(",")]
        if parts:
            prop_type = parts[0]
        if "required" in meta.lower():
            required = True
        if "enum:" in meta.lower():
            enum_start = meta.lower().index("enum:") + 5
            enum_str = meta[enum_start:].strip().strip("/")
            enum_values = [e.strip() for e in enum_str.split("/")]

    return NodeProperty(
        name=name_part,
        prop_type=prop_type,
        required=required,
        enum_values=enum_values,
    )


def _parse_qa_checks(raw: list[str] | None) -> list[str]:
    if not raw:
        return []
    return raw


# ── Engine ─────────────────────────────────────────────────────────────


class DomainGraphEngine:
    """Load, validate, compile, and merge Domain Graph definitions."""

    def load_file(self, filename: str) -> DomainGraph:
        """Load Domain Graph from YAML file."""
        path = Path(filename)
        if not path.exists():
            raise FileNotFoundError(f"Domain Graph not found: {filename}")
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) if yaml else self._simple_parse(f.read())
        return self._from_dict(raw)

    def load_all(self, pattern: str = "*domain.yaml") -> list[DomainGraph]:
        """Load all Domain Graphs matching glob pattern."""
        import glob

        files = glob.glob(pattern, recursive=True)
        return [self.load_file(f) for f in sorted(files)]

    def validate(self, dg: DomainGraph) -> list[str]:
        """Validate node/edge/event reference integrity. Returns error list."""
        errors: list[str] = []
        node_names = set(dg.nodes.keys())

        for edge_name, edge in dg.edges.items():
            for src in edge.source_types:
                if src not in node_names:
                    errors.append(f"Edge '{edge_name}': source '{src}' not in nodes")
            for tgt in edge.target_types:
                if tgt not in node_names:
                    errors.append(f"Edge '{edge_name}': target '{tgt}' not in nodes")

        for event in dg.events:
            if event.source and event.source not in node_names:
                errors.append(f"Event '{event.name}': source '{event.source}' not in nodes")
            for prod in event.produces:
                if prod not in node_names:
                    errors.append(f"Event '{event.name}': produces '{prod}' not in nodes")

        for rule in dg.rules:
            referenced = [
                w.split(".")[0] for w in rule.rule.split() if "." in w
            ]
            for ref in referenced:
                if ref not in node_names:
                    errors.append(f"Rule '{rule.name}': references '{ref}' not in nodes")

        return errors

    def compile_to_oosk(self, dg: DomainGraph) -> dict:
        """Domain Graph → OOSK type registry payload."""
        return {
            "domain": dg.domain,
            "version": dg.version,
            "domain_types": list(dg.nodes.keys()),
            "relation_types": list(dg.edges.keys()),
            "event_types": [e.name for e in dg.events],
            "action_types": {
                e.name: {"triggered_by": e.source, "produces": e.produces}
                for e in dg.events
            },
            "constraint_rules": [
                {"name": r.name, "severity": r.severity, "rule": r.rule}
                for r in dg.rules
            ],
            "node_defs": {name: self._node_to_dict(n) for name, n in dg.nodes.items()},
            "edge_defs": {name: self._edge_to_dict(e) for name, e in dg.edges.items()},
        }

    def compile_to_bors(self, dg: DomainGraph) -> dict:
        """Domain Graph → BORS BusinessEntity mapping."""
        mapping = {}
        for name, node in dg.nodes.items():
            business_props = [p.name for p in node.properties if p.required]
            mapping[f"{name}_value"] = {
                "domain_type": name,
                "description": node.description,
                "required_properties": business_props,
                "privacy_scope": node.privacy_scope,
                "qa_checks": node.qa_checks,
            }
        return mapping

    def merge(self, graphs: list[DomainGraph]) -> DomainGraph:
        """Merge multiple Domain Graphs into one."""
        if not graphs:
            return DomainGraph()
        merged = DomainGraph(
            domain="+".join(g.domain for g in graphs),
            version=max(g.version for g in graphs),
            description="; ".join(g.description for g in graphs if g.description),
        )
        seen_nodes: set[str] = set()
        seen_edges: set[str] = set()
        seen_events: set[str] = set()
        seen_rules: set[str] = set()

        for g in graphs:
            for name, node in g.nodes.items():
                if name not in seen_nodes:
                    merged.nodes[name] = node
                    seen_nodes.add(name)
            for name, edge in g.edges.items():
                if name not in seen_edges:
                    merged.edges[name] = edge
                    seen_edges.add(name)
            for event in g.events:
                if event.name not in seen_events:
                    merged.events.append(event)
                    seen_events.add(event.name)
            for rule in g.rules:
                if rule.name not in seen_rules:
                    merged.rules.append(rule)
                    seen_rules.add(rule.name)

        return merged

    def find_common_structure(self, graphs: list[DomainGraph]) -> dict:
        """Find common node/edge types across multiple Domain Graphs."""
        if not graphs:
            return {"common_nodes": [], "common_edges": []}
        node_sets = [set(g.nodes.keys()) for g in graphs]
        edge_sets = [set(g.edges.keys()) for g in graphs]
        return {
            "common_nodes": list(set.intersection(*node_sets)),
            "common_edges": list(set.intersection(*edge_sets)),
        }

    # ── Internal ─────────────────────────────────────────────────

    def _from_dict(self, raw: dict) -> DomainGraph:
        dg = DomainGraph(
            domain=raw.get("domain", ""),
            version=raw.get("version", "1.0"),
            description=raw.get("description", ""),
        )
        for n in raw.get("nodes", []):
            nd = NodeDef(
                type=n["type"],
                description=n.get("description", ""),
                properties=[_parse_property(p) for p in n.get("properties", [])],
                constraints=n.get("constraints", []),
                qa_checks=_parse_qa_checks(n.get("qa_checks")),
                privacy_scope=n.get("privacy_scope", "private"),
            )
            dg.nodes[nd.type] = nd

        for e in raw.get("edges", []):
            ed = EdgeDef(
                type=e["type"],
                description=e.get("description", ""),
                source_types=e.get("source", []),
                target_types=e.get("target", []),
                cardinality=e.get("cardinality", "N:N"),
            )
            dg.edges[ed.type] = ed

        for e in raw.get("events", []):
            ev = DomainEvent(
                name=e["name"],
                description=e.get("description", ""),
                source=e.get("source", ""),
                triggers=e.get("triggers", []),
                produces=e.get("produces", []),
            )
            dg.events.append(ev)

        for r in raw.get("rules", []):
            rule = DomainRule(
                name=r["name"],
                description=r.get("description", ""),
                rule=r.get("rule", ""),
                severity=r.get("severity", "error"),
            )
            dg.rules.append(rule)

        return dg

    def _node_to_dict(self, node: NodeDef) -> dict:
        return {
            "type": node.type,
            "description": node.description,
            "properties": [f"{p.name} ({p.prop_type}, {'required' if p.required else 'optional'})" for p in node.properties],
            "constraints": node.constraints,
            "qa_checks": node.qa_checks,
            "privacy_scope": node.privacy_scope,
        }

    def _edge_to_dict(self, edge: EdgeDef) -> dict:
        return {
            "type": edge.type,
            "description": edge.description,
            "source": edge.source_types,
            "target": edge.target_types,
            "cardinality": edge.cardinality,
        }

    @staticmethod
    def _simple_parse(text: str) -> dict:
        """Fallback parser when PyYAML is not installed."""
        import json
        import re

        def _clean(line: str) -> str:
            return line.split("#")[0].rstrip()

        lines = [l for l in text.split("\n") if _clean(l).strip()]
        joined = "\n".join(_clean(l) for l in lines)
        try:
            return json.loads(joined)
        except json.JSONDecodeError:
            raise RuntimeError("PyYAML required to parse .yaml files. Install with: pip install pyyaml")
