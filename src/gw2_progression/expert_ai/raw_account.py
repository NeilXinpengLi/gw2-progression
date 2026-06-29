"""ETL helpers for exported GW2 account raw JSON snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_raw_account(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def raw_account_to_runtime_payload(raw: dict[str, Any]) -> dict[str, Any]:
    account = raw.get("account", {})
    name = account.get("name", "unknown")
    account_id = f"account:{name}"
    entities = [{
        "id": account_id,
        "type": "account_snapshot",
        "properties": {
            "account_name": name,
            "world": account.get("world"),
            "created": account.get("created"),
            "age_hours": account.get("age_hours"),
            "exported_at": raw.get("exported_at"),
            **raw.get("kpis", {}),
        },
    }]
    relations: list[dict[str, Any]] = []

    for asset in raw.get("assets", []):
        asset_id = f"asset:{name}:{asset.get('category', 'unknown').lower().replace(' ', '_')}"
        entities.append({"id": asset_id, "type": "AccountAssetCategory", "properties": asset})
        relations.append({"source": account_id, "target": asset_id, "relation_type": "owns", "weight": float(asset.get("percentage", 0)) / 100})

    for character in raw.get("characters", []):
        char_name = character.get("name", "unknown")
        char_id = f"character:{char_name}"
        entities.append({"id": char_id, "type": "Character", "properties": character})
        relations.append({"source": account_id, "target": char_id, "relation_type": "owns", "weight": 1.0})

    return {"entities": entities, "relations": relations, "summary": {"account_id": account_id, "entities": len(entities), "relations": len(relations)}}


def raw_account_to_economy_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for idx, asset in enumerate(raw.get("assets", []), start=1):
        items.append({
            "item_id": idx,
            "price": asset.get("liquid_sell", asset.get("total_value", 0)),
            "supply": max(asset.get("count", 0), 0),
            "demand": max(asset.get("percentage", 0), 0) * 10,
            "category": asset.get("category"),
        })
    return items


def raw_account_to_meta_builds(raw: dict[str, Any]) -> list[dict[str, Any]]:
    builds = []
    for character in raw.get("characters", []):
        builds.append({
            "profession": character.get("profession"),
            "gear_completion_percent": character.get("gear_completion_percent", character.get("build_readiness", 0)),
            "role": character.get("role", "dps"),
            "review_status": character.get("review_status", "reviewed"),
            "character": character.get("name"),
        })
    return builds
