"""Adapters from existing GW2 account/object graph data into Expert AI runtime."""

from __future__ import annotations

from typing import Any

from gw2_progression.analyzer import AccountContents
from gw2_progression.object_graph.mapper import map_to_graph


def account_contents_to_runtime_payload(contents: AccountContents, item_limit: int = 200) -> dict[str, Any]:
    """Convert fetched account contents into OOSK runtime entities and relations."""
    graph = map_to_graph(contents)
    account_id = f"account:{graph.account_name}"
    entities: list[dict[str, Any]] = [{
        "id": account_id,
        "type": "account_snapshot",
        "properties": {
            "account_name": graph.account_name,
            "world": graph.world,
            "created": graph.created,
            "age_hours": graph.age_hours,
            "total_items": len(graph.items),
            "character_count": len(graph.characters),
        },
    }]
    relations: list[dict[str, Any]] = []

    for currency in _nonzero_currencies(graph):
        cid = f"currency:{currency.currency_id}"
        entities.append({
            "id": cid,
            "type": "Currency",
            "properties": {"name": currency.name, "value": currency.value, "gold": currency.gold, "silver": currency.silver, "copper": currency.copper},
        })
        relations.append({"source": account_id, "target": cid, "relation_type": "owns", "weight": 1.0})

    for character in graph.characters:
        char_id = f"character:{character.name}"
        entities.append({
            "id": char_id,
            "type": "Character",
            "properties": {
                "name": character.name,
                "profession": character.profession,
                "race": character.race,
                "level": character.level,
                "playtime_hours": character.playtime_hours,
                "bag_count": character.bag_count,
                "equipment_count": len(character.equipment),
                "build_tabs": character.build_tabs,
            },
        })
        relations.append({"source": account_id, "target": char_id, "relation_type": "owns", "weight": 1.0})

    for idx, item in enumerate(graph.items[: max(0, item_limit)]):
        item_node_id = f"item:{item.item_id}:{idx}"
        entities.append({
            "id": item_node_id,
            "type": "Item",
            "properties": {
                "item_id": item.item_id,
                "count": item.count,
                "location": item.location,
                "location_ref": item.location_ref,
                "binding": item.binding,
                "tradable": item.tradable,
                "value_after_fee": item.value_after_fee,
            },
        })
        owner_id = _owner_for_item(account_id, item.location_ref)
        relations.append({"source": owner_id, "target": item_node_id, "relation_type": "owns", "weight": 1.0})
        if item.location:
            location_id = f"location:{item.location}"
            entities.append({"id": location_id, "type": "StorageLocation", "properties": {"name": item.location}})
            relations.append({"source": item_node_id, "target": location_id, "relation_type": "stored_in", "weight": 0.8})

    unlock_id = f"unlocks:{graph.account_name}"
    entities.append({
        "id": unlock_id,
        "type": "UnlockSummary",
        "properties": {
            "skins": graph.unlocks.skin_count,
            "dyes": graph.unlocks.dye_count,
            "minis": graph.unlocks.mini_count,
            "finishers": graph.unlocks.finisher_count,
        },
    })
    relations.append({"source": account_id, "target": unlock_id, "relation_type": "has_unlocks", "weight": 0.7})

    progression_id = f"progression:{graph.account_name}"
    entities.append({
        "id": progression_id,
        "type": "Progression",
        "properties": {
            "daily_ap": graph.progression.daily_ap,
            "monthly_ap": graph.progression.monthly_ap,
            "wvw_rank": graph.progression.wvw_rank,
            "fractal_level": graph.progression.fractal_level,
            "mastery_count": graph.progression.mastery_count,
            "build_count": graph.progression.build_count,
        },
    })
    relations.append({"source": account_id, "target": progression_id, "relation_type": "has_progression", "weight": 0.7})

    summary = {
        "account_id": account_id,
        "entities": len(entities),
        "relations": len(relations),
        "items_included": min(len(graph.items), max(0, item_limit)),
        "items_total": len(graph.items),
    }
    return {"entities": _dedupe_entities(entities), "relations": relations, "summary": summary}


def _nonzero_currencies(graph) -> list:
    return [currency for currency in graph.currencies.__dict__.values() if getattr(currency, "value", 0) > 0]


def _owner_for_item(account_id: str, location_ref: str) -> str:
    if location_ref and "/" in location_ref:
        return f"character:{location_ref.split('/', 1)[0]}"
    return account_id


def _dedupe_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for entity in entities:
        by_id[entity["id"]] = entity
    return list(by_id.values())

