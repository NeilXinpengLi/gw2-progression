"""Graph traversal helpers for the ontology store.

Provides higher-level queries: find related objects, traverse relations,
compute safe surplus, find dependent goals for an asset.
"""

from . import object_store as store
from .models import OntologyObject


def find_related_objects(
    source_id: str,
    relation_type: str | None = None,
    target_class: str | None = None,
) -> list[OntologyObject]:
    rels = store.get_relations(source_id=source_id, relation_type=relation_type)
    results: list[OntologyObject] = []
    for rel in rels:
        obj = store.get_object(rel.target_id)
        if obj and (target_class is None or obj.class_name == target_class):
            results.append(obj)
    return results


def find_source_objects(
    target_id: str,
    relation_type: str | None = None,
    source_class: str | None = None,
) -> list[OntologyObject]:
    rels = store.get_relations(target_id=target_id, relation_type=relation_type)
    results: list[OntologyObject] = []
    for rel in rels:
        obj = store.get_object(rel.source_id)
        if obj and (source_class is None or obj.class_name == source_class):
            results.append(obj)
    return results


def get_reserved_quantities(account_name: str) -> dict[int, int]:
    reserved: dict[int, int] = {}
    seen_sources: set[str] = set()
    for rel in store.get_relations(relation_type="reserved_for"):
        if rel.source_id in seen_sources:
            continue
        seen_sources.add(rel.source_id)
        source = store.get_object(rel.source_id)
        if source and source.account_name == account_name:
            item_id = source.properties.get("item_id", 0)
            count = source.properties.get("reserved_count", 0)
            reserved[item_id] = reserved.get(item_id, 0) + count
    return reserved


def get_reserved_details(account_name: str) -> list[dict]:
    details: list[dict] = []
    for rel in store.get_relations(relation_type="reserved_for"):
        source = store.get_object(rel.source_id)
        target = store.get_object(rel.target_id)
        if source and source.account_name == account_name and target:
            details.append({
                "item_id": source.properties.get("item_id", 0),
                "reserved_count": source.properties.get("reserved_count", 0),
                "goal_id": target.object_id,
                "goal_name": target.properties.get("name", ""),
                "goal_template_id": target.properties.get("template_id", ""),
            })
    return details


def get_assets_for_account(account_name: str) -> list[OntologyObject]:
    return store.get_objects_by_account("account_asset", account_name)


def find_goals_for_item(item_id: int, account_name: str) -> list[dict]:
    goals: list[dict] = []
    for obj in store.get_objects_by_class("legendary_goal"):
        if obj.account_name != account_name:
            continue
        for req_rel in store.get_relations(source_id=obj.object_id, relation_type="requires"):
            req_obj = store.get_object(req_rel.target_id)
            if req_obj and req_obj.properties.get("item_id") == item_id:
                goals.append({
                    "goal_id": obj.object_id,
                    "goal_name": obj.properties.get("name", ""),
                    "template_id": obj.properties.get("template_id", ""),
                    "priority": obj.properties.get("priority", "normal"),
                    "required_count": req_obj.properties.get("required_count", 0),
                    "owned_count": req_obj.properties.get("owned_count", 0),
                    "status": obj.properties.get("status", "active"),
                })
    return goals


def compute_asset_safe_surplus(item_id: int, account_name: str) -> dict:
    owned = 0
    for asset in get_assets_for_account(account_name):
        if asset.properties.get("item_id") == item_id:
            owned += asset.properties.get("count", 0)
    reserved_count = get_reserved_quantities(account_name).get(item_id, 0)
    goals = find_goals_for_item(item_id, account_name)
    active_goal_count = sum(
        g.get("required_count", 0) for g in goals
        if g.get("status") == "active"
    )
    surplus = max(0, owned - max(reserved_count, active_goal_count))
    return {
        "item_id": item_id,
        "total_owned": owned,
        "total_reserved": max(reserved_count, active_goal_count),
        "safe_surplus": surplus,
        "goals": goals,
    }
