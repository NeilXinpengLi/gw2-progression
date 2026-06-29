"""GW2 API endpoint schema definitions and rule data model.

Defines the GW2 API endpoint structure and the Rule data model used
across all Rule Engine components (API rules, economy rules, behavior rules, LLM rules).
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RuleType(str, Enum):
    DEPENDENCY = "dependency"
    GRAPH_EDGE = "graph_edge"
    ECONOMY_TREND = "economy_trend"
    ECONOMY_ELASTICITY = "economy_elasticity"
    ECONOMY_SHOCK = "economy_shock"
    BEHAVIOR_PATTERN = "behavior_pattern"
    LLM_DISTILLED = "llm_distilled"
    VALIDATED = "validated"


@dataclass
class Rule:
    id: str
    type: RuleType
    source: str
    condition: dict[str, Any]
    action: str
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    validated_score: float | None = None
    simulation_deviation: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            type=RuleType(d.get("type", "dependency")),
            source=d.get("source", "unknown"),
            condition=d.get("condition", {}),
            action=d.get("action", "noop"),
            confidence=float(d.get("confidence", 0.5)),
            metadata=d.get("metadata", {}),
            validated_score=d.get("validated_score"),
            simulation_deviation=d.get("simulation_deviation"),
        )


@dataclass
class EndpointDef:
    name: str
    path: str
    method: str
    permissions: set[str] = field(default_factory=set)
    required_fields: list[str] = field(default_factory=list)
    relations: list[str] = field(default_factory=list)
    ttl_seconds: int = 1800
    is_public: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "EndpointDef":
        return cls(
            name=d.get("name", "unknown"),
            path=d.get("path", ""),
            method=d.get("method", "GET"),
            permissions=set(d.get("permissions", [])),
            required_fields=d.get("required_fields", []),
            relations=d.get("relations", []),
            ttl_seconds=int(d.get("ttl", 1800)),
            is_public=bool(d.get("public", False)),
        )


# ── Pre-defined GW2 API endpoint schemas ────────────────────────────────

ENDPOINT_SCHEMAS: list[EndpointDef] = [
    EndpointDef(name="tokeninfo", path="/v2/tokeninfo", method="GET", required_fields=["id", "name", "permissions"], relations=["grants_permission"], ttl_seconds=300),
    EndpointDef(
        name="account", path="/v2/account", method="GET", permissions={"account"},
        required_fields=["id", "name", "age", "world", "created"], relations=["owns_character", "owns_guild"], ttl_seconds=1800,
    ),
    EndpointDef(
        name="characters", path="/v2/characters", method="GET", permissions={"characters", "inventories"},
        required_fields=["name", "profession", "level", "race"], relations=["equips_item", "has_skill", "has_trait"], ttl_seconds=1800,
    ),
    EndpointDef(name="wallet", path="/v2/account/wallet", method="GET", permissions={"wallet"}, required_fields=["id", "value"], relations=["holds_currency"], ttl_seconds=1800),
    EndpointDef(
        name="materials", path="/v2/account/materials", method="GET", permissions={"inventories"},
        required_fields=["id", "count", "category"], relations=["contains_material"], ttl_seconds=1800,
    ),
    EndpointDef(name="bank", path="/v2/account/bank", method="GET", permissions={"inventories"}, required_fields=["id", "count"], relations=["holds_item"], ttl_seconds=1800),
    EndpointDef(name="inventory", path="/v2/account/inventory", method="GET", permissions={"inventories"}, required_fields=["id", "count"], relations=["holds_item"], ttl_seconds=1800),
    EndpointDef(
        name="achievements", path="/v2/account/achievements", method="GET", permissions={"progression"},
        required_fields=["id", "current", "done"], relations=["tracks_achievement"], ttl_seconds=1800,
    ),
    EndpointDef(name="commerce_prices", path="/v2/commerce/prices", method="GET", is_public=True, required_fields=["id", "buys", "sells"], relations=["has_price"], ttl_seconds=1800),
    EndpointDef(name="commerce_listings", path="/v2/commerce/listings", method="GET", is_public=True, required_fields=["id", "buys", "sells"], relations=["has_listing"], ttl_seconds=3600),
    EndpointDef(
        name="items", path="/v2/items", method="GET", is_public=True,
        required_fields=["id", "name", "type", "rarity"], relations=["has_type", "has_rarity", "requires_item"], ttl_seconds=259200,
    ),
    EndpointDef(
        name="recipes", path="/v2/recipes", method="GET", is_public=True,
        required_fields=["id", "type", "output_item_id", "ingredients"],
        relations=["produces_item", "consumes_item", "requires_discipline"], ttl_seconds=259200,
    ),
    EndpointDef(name="skins", path="/v2/skins", method="GET", is_public=True, required_fields=["id", "name", "type", "rarity"], relations=["unlocks_skin"], ttl_seconds=259200),
    EndpointDef(name="currencies", path="/v2/currencies", method="GET", is_public=True, required_fields=["id", "name", "description"], relations=["defines_currency"], ttl_seconds=259200),
    EndpointDef(name="traits", path="/v2/traits", method="GET", is_public=True, required_fields=["id", "name", "tier", "order"], relations=["requires_trait"], ttl_seconds=259200),
    EndpointDef(
        name="skills", path="/v2/skills", method="GET", is_public=True,
        required_fields=["id", "name", "type", "professions"], relations=["teaches_skill", "requires_skill"], ttl_seconds=259200,
    ),
]


def parse_endpoint_schema(raw: dict[str, Any]) -> EndpointDef:
    return EndpointDef.from_dict(raw)
