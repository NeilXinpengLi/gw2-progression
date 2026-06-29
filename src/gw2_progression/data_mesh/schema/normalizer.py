from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DGSKStructure:
    id: str = ""
    account: str = ""
    wallet: list[dict] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)
    characters: list[dict] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)
    achievements: list[dict] = field(default_factory=list)
    recipes: list[dict] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=lambda: {
        "normalized_at": datetime.now(timezone.utc).isoformat(),
        "source": "unknown",
        "version": "1.0",
    })

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id or str(uuid.uuid4()),
            "account": self.account,
            "wallet": self.wallet,
            "items": self.items,
            "characters": self.characters,
            "relations": self.relations,
            "achievements": self.achievements,
            "recipes": self.recipes,
            "metadata": self.metadata,
        }


class SchemaNormalizer:
    NORMALIZERS: dict[str, str] = {
        "wallet": "wallet",
        "currencies": "wallet",
        "items": "items",
        "inventory": "items",
        "assets": "items",
        "entities": "items",
        "characters": "characters",
        "relations": "relations",
        "achievements": "achievements",
        "recipes": "recipes",
    }

    WALLET_NORMALIZER: dict[str, str] = {
        "id": "id",
        "currency": "id",
        "name": "name",
        "value": "value",
        "amount": "value",
        "quantity": "value",
        "count": "value",
    }

    ITEM_NORMALIZER: dict[str, str] = {
        "id": "id",
        "item_id": "id",
        "count": "count",
        "quantity": "count",
        "amount": "count",
        "name": "name",
        "rarity": "rarity",
        "level": "level",
        "type": "type",
        "icon": "icon",
        "binding": "binding",
        "details": "details",
    }

    RELATION_NORMALIZER: dict[str, str] = {
        "source": "source",
        "subject": "source",
        "from": "source",
        "target": "target",
        "object": "target",
        "to": "target",
        "relation_type": "relation_type",
        "predicate": "relation_type",
        "type": "relation_type",
        "label": "relation_type",
        "properties": "properties",
        "confidence": "confidence",
        "evidence": "evidence",
    }

    @classmethod
    def normalize(cls, raw: dict, source_type: str = "unknown") -> DGSKStructure:
        result = DGSKStructure()
        result.metadata["source"] = source_type
        result.metadata["raw_keys"] = list(raw.keys())

        result.account = raw.get("account") or raw.get("account_name") or "unknown"

        for raw_key, target_field in cls.NORMALIZERS.items():
            if raw_key not in raw:
                continue
            raw_data = raw[raw_key]
            if not isinstance(raw_data, list):
                raw_data = [raw_data]

            normalized_list = []
            for item in raw_data:
                if not isinstance(item, dict):
                    if target_field in ("items", "wallet"):
                        normalized_list.append({"id": str(item), "raw_value": item})
                    else:
                        normalized_list.append({"raw": str(item)})
                    continue

                if target_field == "wallet":
                    normalized_list.append(cls._normalize_wallet_entry(item))
                elif target_field == "items":
                    normalized_list.append(cls._normalize_item_entry(item))
                elif target_field == "relations":
                    normalized_list.append(cls._normalize_relation_entry(item))
                else:
                    normalized_list.append(dict(item))

            setattr(result, target_field, normalized_list)

        return result

    @classmethod
    def _normalize_wallet_entry(cls, entry: dict) -> dict:
        return {
            cls.WALLET_NORMALIZER.get(k, k): v
            for k, v in entry.items()
        }

    @classmethod
    def _normalize_item_entry(cls, entry: dict) -> dict:
        return {
            cls.ITEM_NORMALIZER.get(k, k): v
            for k, v in entry.items()
        }

    @classmethod
    def _normalize_relation_entry(cls, entry: dict) -> dict:
        return {
            cls.RELATION_NORMALIZER.get(k, k): v
            for k, v in entry.items()
        }

    @classmethod
    def merge(cls, structures: list[DGSKStructure]) -> DGSKStructure:
        merged = DGSKStructure()
        merged.metadata["merged_from"] = len(structures)
        merged.metadata["sources"] = []

        seen_wallet: set[int] = set()
        seen_items: set[str] = set()
        seen_relations: set[tuple[str, str, str]] = set()
        seen_achievements: set[int] = set()
        seen_recipes: set[int] = set()

        for s in structures:
            merged.metadata["sources"].append(s.metadata.get("source", "unknown"))
            if s.account != "unknown" and merged.account == "unknown":
                merged.account = s.account

            for w in s.wallet:
                wid = w.get("id", 0)
                if wid not in seen_wallet:
                    seen_wallet.add(wid)
                    merged.wallet.append(w)

            for item in s.items:
                iid = str(item.get("id", ""))
                if iid and iid not in seen_items:
                    seen_items.add(iid)
                    merged.items.append(item)

            for r in s.relations:
                key = (str(r.get("source", "")), str(r.get("relation_type", "")), str(r.get("target", "")))
                if key not in seen_relations:
                    seen_relations.add(key)
                    merged.relations.append(r)

            for a in s.achievements:
                aid = a.get("id", 0)
                if aid not in seen_achievements:
                    seen_achievements.add(aid)
                    merged.achievements.append(a)

            for rcp in s.recipes:
                rid = rcp.get("id", 0)
                if rid not in seen_recipes:
                    seen_recipes.add(rid)
                    merged.recipes.append(rcp)

        merged.id = str(uuid.uuid4())
        return merged
