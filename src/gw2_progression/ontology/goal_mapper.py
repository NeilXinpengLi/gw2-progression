"""Goal Mapper — maps tracked goals into ontology objects and relations.

When a player tracks a legendary goal, this mapper creates:
  - LegendaryGoal object
  - GoalRequirement objects per template requirement
  - ReservedAsset objects for owned quantities
  - "requires" and "reserved_for" relations
"""

import logging

from ..models import GoalRequirement as GoalReqModel
from ..models import TrackedGoal
from ..services.progression_service import CURATED_REQUIREMENTS, CURATED_TEMPLATES
from . import object_store as store
from .models import OntologyObject

logger = logging.getLogger("gw2.ontology.goal")


def map_goal_to_ontology(goal: TrackedGoal) -> list[OntologyObject]:
    created: list[OntologyObject] = []

    template = next(
        (t for t in CURATED_TEMPLATES if t.template_id == str(goal.target_item_id) or t.target_item_id == goal.target_item_id),
        None,
    )
    template_id = template.template_id if template else f"item_{goal.target_item_id}"

    goal_props = {
        "template_id": template_id,
        "target_item_id": goal.target_item_id,
        "name": template.name if template else f"Item #{goal.target_item_id}",
        "priority": goal.priority,
        "status": goal.status,
        "target_count": goal.target_count,
        "completion_percent": goal.completion_percent,
        "owned_value": goal.owned_material_value,
        "missing_value": goal.missing_material_value,
    }

    goal_obj = store.register_object(
        class_name="legendary_goal",
        account_name=goal.account_name,
        properties=goal_props,
        privacy_scope="private",
    )
    created.append(goal_obj)

    reqs = [r for r in CURATED_REQUIREMENTS if r.template_id == template_id]
    if not reqs and template_id.startswith("item_"):
        reqs = _generate_fallback_requirements(goal.target_item_id)

    for req in reqs:
        if req.requirement_type != "item":
            continue
        req_props = {
            "template_id": template_id,
            "item_id": req.ref_id,
            "item_name": req.ref_name,
            "required_count": req.required_count,
            "owned_count": 0,
            "time_gated": req.time_gated,
            "optional_group_id": req.optional_group_id or "",
        }
        req_obj = store.register_object(
            class_name="goal_requirement",
            account_name=goal.account_name,
            properties=req_props,
            privacy_scope="private",
            source_object_id=goal_obj.object_id,
        )
        created.append(req_obj)

        store.register_relation(
            source_id=goal_obj.object_id,
            target_id=req_obj.object_id,
            relation_type="requires",
            confidence=0.95,
        )

    logger.info("Mapped goal %s to ontology with %d requirements", goal.goal_id, len(reqs))
    return created


def _generate_fallback_requirements(target_item_id: int) -> list[GoalReqModel]:
    return [
        GoalReqModel(
            requirement_id=f"fallback_{target_item_id}",
            template_id=f"item_{target_item_id}",
            requirement_type="item",
            ref_id=target_item_id,
            ref_name=f"Item #{target_item_id}",
            required_count=1,
        ),
    ]


async def sync_goal_reservations(account_name: str) -> int:
    reservations_created = 0

    for goal_obj in store.get_objects_by_class("legendary_goal"):
        if goal_obj.account_name != account_name:
            continue
        if goal_obj.properties.get("status") != "active":
            continue

        for req_rel in store.get_relations(source_id=goal_obj.object_id, relation_type="requires"):
            req_obj = store.get_object(req_rel.target_id)
            if not req_obj or req_obj.class_name != "goal_requirement":
                continue

            item_id = req_obj.properties.get("item_id", 0)
            required = req_obj.properties.get("required_count", 0)

            if item_id <= 0 or required <= 0:
                continue

            existing = store.get_relations(
                source_id=goal_obj.object_id,
                relation_type="reserved_for",
            )
            already_reserved = any(
                store.get_object(r.source_id)
                and store.get_object(r.source_id).properties.get("item_id") == item_id
                for r in existing
            )
            if already_reserved:
                continue

            reserve_props = {
                "item_id": item_id,
                "item_name": req_obj.properties.get("item_name", ""),
                "reserved_count": required,
                "goal_id": goal_obj.object_id,
                "goal_name": goal_obj.properties.get("name", ""),
            }
            reserve_obj = store.register_object(
                class_name="reserved_asset",
                account_name=account_name,
                properties=reserve_props,
                privacy_scope="private",
                source_object_id=goal_obj.object_id,
            )
            store.register_relation(
                source_id=reserve_obj.object_id,
                target_id=goal_obj.object_id,
                relation_type="reserved_for",
                confidence=0.95,
            )
            store.register_relation(
                source_id=reserve_obj.object_id,
                target_id=req_obj.object_id,
                relation_type="reserved_for",
                confidence=0.90,
            )
            reservations_created += 1

    logger.info("Synced %d goal reservations for %s", reservations_created, account_name)
    return reservations_created
