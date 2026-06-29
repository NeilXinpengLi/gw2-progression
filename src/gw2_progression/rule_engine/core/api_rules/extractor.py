"""API Structural Rule Extractor — extracts dependency/graph rules from GW2 API endpoint schemas.

This is the rule engine's first stage: parse GW2 API endpoint definitions into
structured rules (item dependencies, crafting constraints, entity relations).
"""

from __future__ import annotations

from typing import Any

from gw2_progression.rule_engine.core.api_rules.schema_parser import (
    ENDPOINT_SCHEMAS,
    EndpointDef,
    Rule,
    RuleType,
)


class APIRuleExtractor:
    """Extracts structural rules from GW2 API endpoint schemas.

    Maps directly to the spec's core/api_rules/extractor.py:
      - to_dependency_rule()  -> required fields become dependency constraints
      - to_graph_rule()       -> relations between entities become graph edges
    """

    def __init__(self, schemas: list[EndpointDef] | None = None):
        self.schemas = schemas or ENDPOINT_SCHEMAS

    def extract(self, gw2_api_schema: list[EndpointDef] | None = None) -> list[Rule]:
        rules: list[Rule] = []
        schemas = gw2_api_schema or self.schemas

        for endpoint in schemas:
            if endpoint.required_fields:
                rules.append(self._to_dependency_rule(endpoint))
            if endpoint.relations:
                for rel in endpoint.relations:
                    rules.append(self._to_graph_rule(endpoint, rel))

        return rules

    def _to_dependency_rule(self, endpoint: EndpointDef) -> Rule:
        return Rule(
            id=f"dep_{endpoint.name}",
            type=RuleType.DEPENDENCY,
            source=f"api:{endpoint.name}",
            condition={"required_fields": endpoint.required_fields, "permissions": list(endpoint.permissions)} if endpoint.permissions else {"required_fields": endpoint.required_fields},
            action=f"resolve_{endpoint.name}",
            confidence=0.95,
            metadata={"endpoint": endpoint.path, "method": endpoint.method, "source": "gw2_api_schema"},
        )

    def _to_graph_rule(self, endpoint: EndpointDef, relation: str) -> Rule:
        return Rule(
            id=f"graph_{endpoint.name}_{relation}",
            type=RuleType.GRAPH_EDGE,
            source=f"api:{endpoint.name}",
            condition={"relation": relation, "subject_type": endpoint.name.split("_")[0] if "_" in endpoint.name else endpoint.name},
            action=f"add_edge_{relation}",
            confidence=0.9,
            metadata={"endpoint": endpoint.path, "relation": relation, "source": "gw2_api_schema"},
        )

    def extract_all(self) -> dict[str, Any]:
        raw = self.extract()
        return {
            "rule_count": len(raw),
            "rules": [r.to_dict() for r in raw],
            "by_type": {t.value: len([r for r in raw if r.type == t]) for t in RuleType},
            "sources": list({r.source for r in raw}),
        }
