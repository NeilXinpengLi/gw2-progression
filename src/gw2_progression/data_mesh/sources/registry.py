from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SourceType(str, enum.Enum):
    OFFICIAL_API = "official_api"
    OFFICIAL_WIKI = "official_wiki"
    OFFICIAL_FORUM = "official_forum"
    OFFICIAL_POLICY = "official_policy"
    PUBLIC_BUILD_SITE = "public_build_site"
    COMPETITOR_TOOL = "competitor_tool"
    LICENSE_REFERENCE = "license_reference"
    COMMUNITY = "community"


class AllowedUse(str, enum.Enum):
    API_JSON = "api_json"
    SUMMARY_AND_REFERENCE = "summary_and_reference"
    MANUAL_NOTE = "manual_note"
    METADATA_ONLY = "metadata_only"


class CrawlPolicy(str, enum.Enum):
    MANUAL_ONLY = "manual_only"
    API_ONLY = "api_only"
    MANUAL_OR_LOW_FREQUENCY = "manual_or_low_frequency"
    GATEWAY_MANAGED = "gateway_managed"


class KBDomain(str, enum.Enum):
    OFFICIAL = "official"
    GAME_SYSTEM = "game_system"
    LEGENDARY = "legendary"
    RETURNER = "returner"
    BUILD = "build"
    MARKET = "market"
    GUILD = "guild"
    CREATOR = "creator"
    SOURCE_REGISTRY = "source_registry"


@dataclass
class KnowledgeSource:
    source_id: str
    name: str
    source_type: SourceType
    source_url: str
    allowed_use: AllowedUse
    crawl_policy: CrawlPolicy
    default_confidence: float
    license_note: str
    recommended_kb_domain: KBDomain
    tags: list[str] = field(default_factory=list)
    last_reviewed: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "source_type": self.source_type.value,
            "source_url": self.source_url,
            "allowed_use": self.allowed_use.value,
            "crawl_policy": self.crawl_policy.value,
            "default_confidence": self.default_confidence,
            "license_note": self.license_note,
            "recommended_kb_domain": self.recommended_kb_domain.value,
            "tags": self.tags,
            "last_reviewed": self.last_reviewed,
        }


@dataclass
class KnowledgeArticle:
    kb_id: str
    title: str
    domain: str
    content_type: str
    summary: str
    linked_entities: list[str] = field(default_factory=list)
    linked_actions: list[str] = field(default_factory=list)
    linked_sources: list[str] = field(default_factory=list)
    confidence: float = 0.9
    review_status: str = "draft"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kb_id": self.kb_id,
            "title": self.title,
            "domain": self.domain,
            "content_type": self.content_type,
            "summary": self.summary,
            "linked_entities": self.linked_entities,
            "linked_actions": self.linked_actions,
            "linked_sources": self.linked_sources,
            "confidence": self.confidence,
            "review_status": self.review_status,
        }


class SourceRegistry:
    def __init__(self, path: str | Path | None = None):
        self._sources: dict[str, KnowledgeSource] = {}
        self._articles: dict[str, KnowledgeArticle] = {}
        if path is not None:
            self.load(path)

    def register(self, source: KnowledgeSource) -> KnowledgeSource:
        self._sources[source.source_id] = source
        return source

    def get(self, source_id: str) -> KnowledgeSource | None:
        return self._sources.get(source_id)

    def list_sources(
        self,
        source_type: SourceType | None = None,
        domain: KBDomain | None = None,
    ) -> list[KnowledgeSource]:
        results = list(self._sources.values())
        if source_type is not None:
            results = [s for s in results if s.source_type == source_type]
        if domain is not None:
            results = [s for s in results if s.recommended_kb_domain == domain]
        return results

    def add_article(self, article: KnowledgeArticle) -> KnowledgeArticle:
        self._articles[article.kb_id] = article
        return article

    def get_article(self, kb_id: str) -> KnowledgeArticle | None:
        return self._articles.get(kb_id)

    def list_articles(self, domain: str | None = None) -> list[KnowledgeArticle]:
        if domain is None:
            return list(self._articles.values())
        return [a for a in self._articles.values() if a.domain == domain]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": {k: v.to_dict() for k, v in self._sources.items()},
            "articles": {k: v.to_dict() for k, v in self._articles.items()},
        }

    def load(self, path: str | Path) -> None:
        path = Path(path)
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        for sid, sd in data.get("sources", {}).items():
            self._sources[sid] = KnowledgeSource(
                source_id=sd["source_id"],
                name=sd["name"],
                source_type=SourceType(sd["source_type"]),
                source_url=sd["source_url"],
                allowed_use=AllowedUse(sd["allowed_use"]),
                crawl_policy=CrawlPolicy(sd["crawl_policy"]),
                default_confidence=sd["default_confidence"],
                license_note=sd["license_note"],
                recommended_kb_domain=KBDomain(sd["recommended_kb_domain"]),
                tags=sd.get("tags", []),
                last_reviewed=sd.get("last_reviewed"),
            )
        for aid, ad in data.get("articles", {}).items():
            self._articles[aid] = KnowledgeArticle(
                kb_id=ad["kb_id"],
                title=ad["title"],
                domain=ad["domain"],
                content_type=ad["content_type"],
                summary=ad["summary"],
                linked_entities=ad.get("linked_entities", []),
                linked_actions=ad.get("linked_actions", []),
                linked_sources=ad.get("linked_sources", []),
                confidence=ad.get("confidence", 0.9),
                review_status=ad.get("review_status", "draft"),
            )

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def count(self) -> dict[str, int]:
        return {"sources": len(self._sources), "articles": len(self._articles)}


BUILTIN_SOURCES: list[KnowledgeSource] = [
    KnowledgeSource(
        source_id="source:official:guildwars2_home",
        name="Guild Wars 2 Official Website",
        source_type=SourceType.OFFICIAL_POLICY,
        source_url="https://www.guildwars2.com/",
        allowed_use=AllowedUse.SUMMARY_AND_REFERENCE,
        crawl_policy=CrawlPolicy.MANUAL_OR_LOW_FREQUENCY,
        default_confidence=0.99,
        license_note="ArenaNet/NCSoft official content, copyright and trademark apply.",
        recommended_kb_domain=KBDomain.OFFICIAL,
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:official:game_update_notes",
        name="Official Forum — Game Update Notes",
        source_type=SourceType.OFFICIAL_FORUM,
        source_url="https://en-forum.guildwars2.com/forum/6-game-update-notes/",
        allowed_use=AllowedUse.SUMMARY_AND_REFERENCE,
        crawl_policy=CrawlPolicy.MANUAL_OR_LOW_FREQUENCY,
        default_confidence=0.95,
        license_note="Forum posts are official communication, subject to ArenaNet forum policy.",
        recommended_kb_domain=KBDomain.OFFICIAL,
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:official:arenanet_content_terms",
        name="ArenaNet Content Terms of Use",
        source_type=SourceType.OFFICIAL_POLICY,
        source_url="https://www.arena.net/legal/content-terms-of-use",
        allowed_use=AllowedUse.SUMMARY_AND_REFERENCE,
        crawl_policy=CrawlPolicy.MANUAL_ONLY,
        default_confidence=0.99,
        license_note="ArenaNet/NCSoft legal terms, governs fan project content boundaries.",
        recommended_kb_domain=KBDomain.OFFICIAL,
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:gw2wiki:api_main",
        name="Guild Wars 2 API Main",
        source_type=SourceType.OFFICIAL_WIKI,
        source_url="https://wiki.guildwars2.com/wiki/API:Main",
        allowed_use=AllowedUse.SUMMARY_AND_REFERENCE,
        crawl_policy=CrawlPolicy.MANUAL_OR_LOW_FREQUENCY,
        default_confidence=0.95,
        license_note="GW2 Wiki contributor content and ArenaNet/NCSoft content require attribution.",
        recommended_kb_domain=KBDomain.OFFICIAL,
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:gw2wiki:api_v2",
        name="Guild Wars 2 Wiki API:2",
        source_type=SourceType.OFFICIAL_WIKI,
        source_url="https://wiki.guildwars2.com/wiki/API:2",
        allowed_use=AllowedUse.SUMMARY_AND_REFERENCE,
        crawl_policy=CrawlPolicy.MANUAL_OR_LOW_FREQUENCY,
        default_confidence=0.95,
        license_note="GW2 Wiki contributor content and ArenaNet/NCSoft content require attribution.",
        recommended_kb_domain=KBDomain.OFFICIAL,
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:gw2wiki:api_best_practices",
        name="API Best Practices",
        source_type=SourceType.OFFICIAL_WIKI,
        source_url="https://wiki.guildwars2.com/wiki/API:Best_practices",
        allowed_use=AllowedUse.SUMMARY_AND_REFERENCE,
        crawl_policy=CrawlPolicy.MANUAL_OR_LOW_FREQUENCY,
        default_confidence=0.95,
        license_note="Rate limit and 429 handling documented per ArenaNet API policy.",
        recommended_kb_domain=KBDomain.OFFICIAL,
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:gw2wiki:api_key",
        name="API Key",
        source_type=SourceType.OFFICIAL_WIKI,
        source_url="https://wiki.guildwars2.com/wiki/API:API_key",
        allowed_use=AllowedUse.SUMMARY_AND_REFERENCE,
        crawl_policy=CrawlPolicy.MANUAL_OR_LOW_FREQUENCY,
        default_confidence=0.95,
        license_note="API key permissions and scope documentation.",
        recommended_kb_domain=KBDomain.OFFICIAL,
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:gw2wiki:api_tokeninfo",
        name="API tokeninfo",
        source_type=SourceType.OFFICIAL_WIKI,
        source_url="https://wiki.guildwars2.com/wiki/API:2/tokeninfo",
        allowed_use=AllowedUse.SUMMARY_AND_REFERENCE,
        crawl_policy=CrawlPolicy.MANUAL_OR_LOW_FREQUENCY,
        default_confidence=0.95,
        license_note="Scope validation endpoint documentation.",
        recommended_kb_domain=KBDomain.OFFICIAL,
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:gw2api:account",
        name="GW2 API /v2/account",
        source_type=SourceType.OFFICIAL_API,
        source_url="https://wiki.guildwars2.com/wiki/API:2/account",
        allowed_use=AllowedUse.API_JSON,
        crawl_policy=CrawlPolicy.GATEWAY_MANAGED,
        default_confidence=1.0,
        license_note="Personal account data endpoint, requires API key with account scope.",
        recommended_kb_domain=KBDomain.OFFICIAL,
        tags=["private", "account"],
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:gw2api:characters",
        name="GW2 API /v2/characters",
        source_type=SourceType.OFFICIAL_API,
        source_url="https://wiki.guildwars2.com/wiki/API:2/characters",
        allowed_use=AllowedUse.API_JSON,
        crawl_policy=CrawlPolicy.GATEWAY_MANAGED,
        default_confidence=1.0,
        license_note="Personal character data endpoint, requires API key with characters scope.",
        recommended_kb_domain=KBDomain.OFFICIAL,
        tags=["private", "characters"],
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:gw2api:account_wallet",
        name="GW2 API /v2/account/wallet",
        source_type=SourceType.OFFICIAL_API,
        source_url="https://wiki.guildwars2.com/wiki/API:2/account/wallet",
        allowed_use=AllowedUse.API_JSON,
        crawl_policy=CrawlPolicy.GATEWAY_MANAGED,
        default_confidence=1.0,
        license_note="Personal wallet data endpoint, requires API key with wallet scope.",
        recommended_kb_domain=KBDomain.OFFICIAL,
        tags=["private", "wallet"],
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:gw2api:account_bank",
        name="GW2 API /v2/account/bank",
        source_type=SourceType.OFFICIAL_API,
        source_url="https://wiki.guildwars2.com/wiki/API:2/account/bank",
        allowed_use=AllowedUse.API_JSON,
        crawl_policy=CrawlPolicy.GATEWAY_MANAGED,
        default_confidence=1.0,
        license_note="Personal bank data endpoint, requires API key with inventory scope.",
        recommended_kb_domain=KBDomain.OFFICIAL,
        tags=["private", "inventory"],
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:gw2api:recipes",
        name="GW2 API /v2/recipes",
        source_type=SourceType.OFFICIAL_API,
        source_url="https://wiki.guildwars2.com/wiki/API:2/recipes",
        allowed_use=AllowedUse.API_JSON,
        crawl_policy=CrawlPolicy.GATEWAY_MANAGED,
        default_confidence=1.0,
        license_note="Public recipe data endpoint, no API key required.",
        recommended_kb_domain=KBDomain.GAME_SYSTEM,
        tags=["public", "recipes", "crafting"],
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:gw2api:commerce",
        name="GW2 API /v2/commerce",
        source_type=SourceType.OFFICIAL_API,
        source_url="https://wiki.guildwars2.com/wiki/API:2/commerce",
        allowed_use=AllowedUse.API_JSON,
        crawl_policy=CrawlPolicy.GATEWAY_MANAGED,
        default_confidence=1.0,
        license_note="Commerce API endpoint for market data.",
        recommended_kb_domain=KBDomain.MARKET,
        tags=["public", "commerce", "trading"],
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:snowcrows:home",
        name="Snow Crows Home",
        source_type=SourceType.PUBLIC_BUILD_SITE,
        source_url="https://snowcrows.com/",
        allowed_use=AllowedUse.SUMMARY_AND_REFERENCE,
        crawl_policy=CrawlPolicy.MANUAL_OR_LOW_FREQUENCY,
        default_confidence=0.8,
        license_note="Snow Crows community build reference, not official ArenaNet content. Attribution required.",
        recommended_kb_domain=KBDomain.BUILD,
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:gw2efficiency:home",
        name="gw2efficiency Home",
        source_type=SourceType.COMPETITOR_TOOL,
        source_url="https://gw2efficiency.com/",
        allowed_use=AllowedUse.METADATA_ONLY,
        crawl_policy=CrawlPolicy.MANUAL_ONLY,
        default_confidence=0.7,
        license_note="Third-party competitor tool reference. Store metadata and links only.",
        recommended_kb_domain=KBDomain.SOURCE_REGISTRY,
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
    KnowledgeSource(
        source_id="source:community:reddit_guildwars2",
        name="Reddit r/Guildwars2",
        source_type=SourceType.COMMUNITY,
        source_url="https://www.reddit.com/r/Guildwars2/",
        allowed_use=AllowedUse.SUMMARY_AND_REFERENCE,
        crawl_policy=CrawlPolicy.MANUAL_ONLY,
        default_confidence=0.4,
        license_note="Community content, treated as low-confidence trend input only.",
        recommended_kb_domain=KBDomain.CREATOR,
        last_reviewed=datetime.now(timezone.utc).isoformat(),
    ),
]
