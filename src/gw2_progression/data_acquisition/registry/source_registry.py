from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    API = "api"
    WIKI = "wiki"
    TOOL = "tool"
    COMMUNITY = "community"
    MARKET = "market"
    BEHAVIOR = "behavior"
    SYNTHETIC = "synthetic"


class SourcePriority(int, Enum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class SourceConfig:
    id: str
    type: SourceType
    priority: SourcePriority
    frequency: str
    endpoint: str = ""
    auth_required: bool = False
    enabled: bool = True
    freshness_sla_seconds: int = 86400
    confidence_default: float = 0.8
    privacy_scope: str = "public"
    license_note: str = ""
    rate_limit_per_minute: int = 60
    transformations: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "priority": self.priority.value,
            "frequency": self.frequency,
            "endpoint": self.endpoint,
            "auth_required": self.auth_required,
            "enabled": self.enabled,
            "freshness_sla_seconds": self.freshness_sla_seconds,
            "confidence_default": self.confidence_default,
            "privacy_scope": self.privacy_scope,
            "license_note": self.license_note,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "transformations": self.transformations,
            "tags": self.tags,
            "metadata": self.metadata,
        }


DEFAULT_SOURCES: list[dict[str, Any]] = [
    {
        "id": "gw2_api_account",
        "type": "api",
        "priority": 0,
        "frequency": "realtime",
        "endpoint": "/v2/account",
        "auth_required": True,
        "privacy_scope": "account",
        "freshness_sla_seconds": 3600,
        "confidence_default": 0.95,
    },
    {
        "id": "gw2_api_items",
        "type": "api",
        "priority": 0,
        "frequency": "realtime",
        "endpoint": "/v2/items",
        "freshness_sla_seconds": 86400,
        "confidence_default": 0.95,
    },
    {
        "id": "gw2_api_wallet",
        "type": "api",
        "priority": 0,
        "frequency": "realtime",
        "endpoint": "/v2/account/wallet",
        "auth_required": True,
        "privacy_scope": "account",
        "freshness_sla_seconds": 1800,
        "confidence_default": 0.95,
    },
    {
        "id": "gw2_api_achievements",
        "type": "api",
        "priority": 0,
        "frequency": "realtime",
        "endpoint": "/v2/account/achievements",
        "auth_required": True,
        "privacy_scope": "account",
        "freshness_sla_seconds": 3600,
        "confidence_default": 0.95,
    },
    {
        "id": "gw2_wiki_crafting",
        "type": "wiki",
        "priority": 1,
        "frequency": "daily",
        "endpoint": "https://wiki.guildwars2.com/api.php",
        "license_note": "GW2 Wiki content requires attribution.",
        "confidence_default": 0.85,
        "metadata": {
            "adapter": "mediawiki",
            "entity_type": "wiki_page",
            "titles": ["Crafting", "Recipe", "Trading Post"],
        },
    },
    {
        "id": "gw2_api_recipes",
        "type": "api",
        "priority": 0,
        "frequency": "daily",
        "endpoint": "/v2/recipes?ids=all",
        "freshness_sla_seconds": 86400,
        "confidence_default": 0.95,
        "metadata": {"adapter": "gw2_official", "entity_type": "recipe", "chunk_size": 200, "max_items": 500},
    },
    {
        "id": "gw2_efficiency_prices",
        "type": "tool",
        "priority": 1,
        "frequency": "hourly",
        "endpoint": "https://www.gw2efficiency.com/api/prices",
        "confidence_default": 0.75,
    },
    {
        "id": "gw2_api_tp",
        "type": "api",
        "priority": 1,
        "frequency": "hourly",
        "endpoint": "/v2/commerce/prices?ids=all",
        "freshness_sla_seconds": 1800,
        "confidence_default": 0.95,
        "metadata": {"adapter": "gw2_official", "entity_type": "market_item", "chunk_size": 200, "max_items": 500},
    },
    {
        "id": "gw2_api_commerce_listings",
        "type": "api",
        "priority": 1,
        "frequency": "hourly",
        "endpoint": "/v2/commerce/listings?ids=all",
        "freshness_sla_seconds": 1800,
        "confidence_default": 0.95,
        "metadata": {"adapter": "gw2_official", "entity_type": "market_listing", "chunk_size": 200, "max_items": 250},
    },
    {
        "id": "gw2_market_price_snapshots",
        "type": "api",
        "priority": 1,
        "frequency": "hourly",
        "endpoint": "/v2/commerce/prices?ids=all",
        "freshness_sla_seconds": 1800,
        "confidence_default": 0.95,
        "metadata": {
            "adapter": "market_timeseries",
            "entity_type": "market_price_snapshot",
            "chunk_size": 200,
            "max_items": 500,
        },
    },
    {
        "id": "gw2_spidy",
        "type": "tool",
        "priority": 2,
        "frequency": "hourly",
        "endpoint": "https://api.gw2spidy.com/v1",
        "confidence_default": 0.7,
    },
    {"id": "reddit_gw2", "type": "community", "priority": 3, "frequency": "daily", "confidence_default": 0.45},
    {"id": "gw2_guild_panel", "type": "community", "priority": 3, "frequency": "daily", "confidence_default": 0.55},
    {
        "id": "gw2_account_raw_replay",
        "type": "api",
        "priority": 0,
        "frequency": "daily",
        "endpoint": "",
        "privacy_scope": "account",
        "freshness_sla_seconds": 86400,
        "confidence_default": 0.9,
        "metadata": {"replay_path": "docs/gw2-account-Netro.7195-2026-06-28.json"},
        "tags": ["replay", "account_snapshot"],
    },
    {
        "id": "synthetic_world_trajectories",
        "type": "synthetic",
        "priority": 4,
        "frequency": "weekly",
        "confidence_default": 0.6,
        "tags": ["coverage_gap"],
    },
]

FREQUENCY_RANK = {"realtime": 0, "hourly": 1, "daily": 2, "weekly": 3}


class SourceRegistry:
    """Config-driven data source registry.

    Manages available data sources, their metadata, and provides
    query/filter operations for the ingestion orchestrator.
    """

    def __init__(self, sources: list[dict[str, Any]] | None = None) -> None:
        self.sources: dict[str, SourceConfig] = {}
        if sources is None:
            sources = DEFAULT_SOURCES
        for src in sources:
            self.register(src)

    def register(self, config: dict[str, Any]) -> SourceConfig:
        sc = SourceConfig(
            id=config["id"],
            type=SourceType(config.get("type", "api")),
            priority=SourcePriority(config.get("priority", 3)),
            frequency=config.get("frequency", "daily"),
            endpoint=config.get("endpoint", ""),
            auth_required=config.get("auth_required", False),
            enabled=config.get("enabled", True),
            freshness_sla_seconds=int(config.get("freshness_sla_seconds", 86400)),
            confidence_default=float(config.get("confidence_default", 0.8)),
            privacy_scope=config.get("privacy_scope", "public"),
            license_note=config.get("license_note", ""),
            rate_limit_per_minute=int(config.get("rate_limit_per_minute", 60)),
            transformations=config.get("transformations", []),
            tags=config.get("tags", []),
            metadata=config.get("metadata", {}),
        )
        self.sources[sc.id] = sc
        return sc

    def get(self, source_id: str) -> SourceConfig | None:
        return self.sources.get(source_id)

    def get_by_type(self, source_type: SourceType) -> list[SourceConfig]:
        return [s for s in self.sources.values() if s.type == source_type]

    def get_by_priority(self, max_priority: SourcePriority) -> list[SourceConfig]:
        return [s for s in self.sources.values() if s.priority.value <= max_priority.value]

    def get_by_frequency(self, frequency: str) -> list[SourceConfig]:
        return [s for s in self.sources.values() if s.frequency == frequency]

    def get_enabled(self) -> list[SourceConfig]:
        return [s for s in self.sources.values() if s.enabled]

    def get_sorted(self) -> list[SourceConfig]:
        """Sorted by priority then frequency."""
        return sorted(
            self.get_enabled(),
            key=lambda s: (s.priority.value, FREQUENCY_RANK.get(s.frequency, 99)),
        )

    def remove(self, source_id: str) -> bool:
        return self.sources.pop(source_id, None) is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": len(self.sources),
            "enabled": len(self.get_enabled()),
            "by_type": {t.value: len(self.get_by_type(t)) for t in SourceType},
            "sources": [s.to_dict() for s in self.get_sorted()],
        }
