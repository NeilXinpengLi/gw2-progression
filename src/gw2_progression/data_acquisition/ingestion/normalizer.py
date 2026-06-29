from __future__ import annotations

from typing import Any

from gw2_progression.data_acquisition.registry.source_registry import SourceConfig


class Normalizer:
    """Normalizes raw fetched data into a unified format.

    Each source type produces a canonical structure:
      - entities: list of discovered entities
      - relations: list of entity relationships
      - properties: key-value attributes
    """

    def normalize(self, raw_data: dict[str, Any], source: SourceConfig) -> dict[str, Any]:
        data = raw_data.get("data", {})
        source_type = source.type.value
        timestamp = float(raw_data.get("timestamp", 0) or 0)

        if source_type == "api":
            return self._normalize_api(data, source, timestamp)
        if source_type == "wiki":
            return self._normalize_wiki(data, source, timestamp)
        if source_type == "market":
            return self._normalize_market(data, source, timestamp)
        return self._normalize_default(data, source, timestamp)

    def _normalize_api(self, data: Any, source: SourceConfig, timestamp: float) -> dict[str, Any]:
        entities: list[dict[str, Any]] = []
        relations: list[dict[str, Any]] = []

        if isinstance(data, list):
            for item in data:
                entity_type = source.metadata.get("entity_type", item.get("type", source.type.value))
                native_id = item.get("id", "unknown")
                if entity_type == "market_price_snapshot":
                    observed = item.get("snapshot_observed_at", timestamp)
                    eid = f"{source.id}:{native_id}:{observed}"
                else:
                    eid = f"{source.id}:{native_id}"
                entities.append({
                    "id": eid,
                    "type": entity_type,
                    "name": item.get("name", str(item.get("id", ""))),
                    "properties": {"native_id": item.get("id"), **{k: v for k, v in item.items() if k not in ("id", "name", "type")}},
                    "source": source.id,
                    "timestamp": timestamp,
                    "confidence": source.confidence_default,
                    "lineage": [source.id],
                })
        elif isinstance(data, dict):
            if self._looks_like_account_snapshot(data):
                account_name = str(data.get("account", {}).get("name") or data.get("name") or source.id)
                snapshot_id = f"{source.id}:account_snapshot:{account_name}"
                entities.append({
                    "id": snapshot_id,
                    "type": "account_snapshot",
                    "name": account_name,
                    "properties": {
                        "sections": sorted(data.keys()),
                        "wallet_count": len(data.get("wallet", []) or []),
                        "bank_count": len(data.get("bank", []) or []),
                        "material_count": len(data.get("materials", []) or []),
                        "character_count": len(data.get("characters", []) or []),
                    },
                    "source": source.id,
                    "timestamp": timestamp,
                    "confidence": source.confidence_default,
                    "lineage": [source.id],
                })
            for key, value in data.items():
                entities.append({
                    "id": f"{source.id}:{key}",
                    "type": self._section_entity_type(key),
                    "name": key,
                    "properties": {"value": value} if not isinstance(value, dict) else value,
                    "source": source.id,
                    "timestamp": timestamp,
                    "confidence": source.confidence_default,
                    "lineage": [source.id],
                })

        return {"entities": entities, "relations": relations, "source": source.id, "observed_at": timestamp}

    def _looks_like_account_snapshot(self, data: dict[str, Any]) -> bool:
        return any(key in data for key in ("account", "wallet", "bank", "materials", "characters"))

    def _section_entity_type(self, key: str) -> str:
        return {
            "account": "account_profile",
            "wallet": "account_wallet",
            "bank": "account_bank",
            "materials": "account_materials",
            "characters": "account_characters",
            "achievements": "account_achievements",
            "skins": "account_skins",
        }.get(key, "property")

    def _normalize_wiki(self, data: dict[str, Any], source: SourceConfig, timestamp: float) -> dict[str, Any]:
        entities = []
        pages = data.get("query", {}).get("pages", {}) if isinstance(data, dict) else {}
        if isinstance(pages, dict):
            for page_id, page in pages.items():
                if not isinstance(page, dict):
                    continue
                revision = self._latest_wiki_revision(page)
                entities.append({
                    "id": f"{source.id}:page:{page_id}",
                    "type": source.metadata.get("entity_type", "wiki_page"),
                    "name": page.get("title", str(page_id)),
                    "properties": {
                        "page_id": page.get("pageid", page_id),
                        "title": page.get("title", ""),
                        "namespace": page.get("ns", 0),
                        "revision_id": revision.get("revid"),
                        "revision_timestamp": revision.get("timestamp"),
                        "content_excerpt": self._wiki_revision_content(revision)[:2000],
                    },
                    "source": source.id,
                    "timestamp": timestamp,
                    "confidence": source.confidence_default,
                    "lineage": [source.id],
                })
            return {"entities": entities, "relations": [], "source": source.id, "observed_at": timestamp}

        for recipe in data.get("recipes", []):
            entities.append({
                "id": f"recipe:{recipe['id']}",
                "type": "recipe",
                "name": recipe.get("output", f"Recipe_{recipe['id']}"),
                "properties": {"disciplines": recipe.get("disciplines", [])},
                "source": source.id,
                "timestamp": timestamp,
                "confidence": source.confidence_default,
                "lineage": [source.id],
            })
        return {"entities": entities, "relations": [], "source": source.id, "observed_at": timestamp}

    def _latest_wiki_revision(self, page: dict[str, Any]) -> dict[str, Any]:
        revisions = page.get("revisions", [])
        if isinstance(revisions, list) and revisions:
            revision = revisions[0]
            return revision if isinstance(revision, dict) else {}
        return {}

    def _wiki_revision_content(self, revision: dict[str, Any]) -> str:
        slots = revision.get("slots", {})
        if isinstance(slots, dict):
            main = slots.get("main", {})
            if isinstance(main, dict):
                return str(main.get("*") or main.get("content") or "")
        return str(revision.get("*") or revision.get("content") or "")

    def _normalize_market(self, data: dict[str, Any], source: SourceConfig, timestamp: float) -> dict[str, Any]:
        entities = []
        relations = []
        for item_name, prices in data.items():
            eid = f"market:{item_name.lower().replace(' ', '_')}"
            entities.append({
                "id": eid,
                "type": "market_item",
                "name": item_name,
                "properties": prices,
                "source": source.id,
                "timestamp": timestamp,
                "confidence": source.confidence_default,
                "lineage": [source.id],
            })
        return {"entities": entities, "relations": relations, "source": source.id, "observed_at": timestamp}

    def _normalize_default(self, data: Any, source: SourceConfig, timestamp: float) -> dict[str, Any]:
        return {"entities": [], "relations": [], "source": source.id, "observed_at": timestamp}
