"""Guild Workspace Ontology — maps guild data, members, and shared goals.

Enables cross-account analysis: which guild members share which legendary
goals, what materials the guild collectively owns, and how guild assets
relate to individual member goals.
"""

import logging

from . import object_store as store
from .models import OntologyObject

logger = logging.getLogger("gw2.ontology.guild")


async def map_guild_to_ontology(guild_data: dict) -> list[OntologyObject]:
    created: list[OntologyObject] = []
    guild_id = guild_data.get("id", 0)
    guild_name = guild_data.get("name", f"guild_{guild_id}")

    guild_obj = store.register_object(
        class_name="guild_workspace",
        properties={
            "guild_id": guild_id,
            "name": guild_name,
            "invite_code": guild_data.get("invite_code", ""),
            "member_count": len(guild_data.get("members", [])),
        },
        privacy_scope="shared",
    )
    created.append(guild_obj)

    for member in guild_data.get("members", []):
        acct = member.get("account_name", "unknown")
        member_obj = store.register_object(
            class_name="guild_member",
            account_name=acct,
            properties={
                "guild_id": guild_id,
                "role": member.get("role", "member"),
                "joined_at": member.get("joined_at", ""),
            },
            privacy_scope="shared",
            source_object_id=guild_obj.object_id,
        )
        created.append(member_obj)
        store.register_relation(
            source_id=member_obj.object_id,
            target_id=guild_obj.object_id,
            relation_type="member_of",
            confidence=1.0,
        )

    return created


async def sync_guild_goals(guild_id: int, account_names: list[str]) -> int:
    cross_goals: dict[int, dict] = {}
    for acct in account_names:
        for goal_obj in store.get_objects_by_account("legendary_goal", acct):
            tid = goal_obj.properties.get("template_id", "")
            if tid not in cross_goals:
                cross_goals[tid] = {
                    "template_id": tid,
                    "name": goal_obj.properties.get("name", ""),
                    "members": [],
                    "total_progress": 0.0,
                }
            cross_goals[tid]["members"].append(acct)
            cross_goals[tid]["total_progress"] += goal_obj.properties.get("completion_percent", 0)

    guild_objs = [o for o in store.get_objects_by_class("guild_workspace") if o.properties.get("guild_id") == guild_id]
    if not guild_objs:
        return 0

    guild_obj = guild_objs[0]
    count = 0
    for tid, info in cross_goals.items():
        if len(info["members"]) < 2:
            continue
        shared_props = {
            "template_id": tid,
            "name": info["name"],
            "member_count": len(info["members"]),
            "members": info["members"],
            "avg_progress": round(info["total_progress"] / len(info["members"]), 1),
        }
        shared = store.register_object(
            class_name="guild_goal",
            properties=shared_props,
            privacy_scope="shared",
            source_object_id=guild_obj.object_id,
        )
        store.register_relation(
            source_id=shared.object_id,
            target_id=guild_obj.object_id,
            relation_type="contributes_to",
            confidence=0.85,
        )
        count += 1

    logger.info("Synced %d shared guild goals for guild %d", count, guild_id)
    return count


def get_guild_member_objects(guild_id: int) -> list[OntologyObject]:
    members: list[OntologyObject] = []
    for obj in store.get_objects_by_class("guild_member"):
        if obj.properties.get("guild_id") == guild_id:
            members.append(obj)
    return members


def get_shared_guild_goals(guild_id: int) -> list[OntologyObject]:
    goals: list[OntologyObject] = []
    for rel in store.get_relations(relation_type="contributes_to"):
        guild_objs = [o for o in store.get_objects_by_class("guild_workspace") if o.properties.get("guild_id") == guild_id]
        if not guild_objs:
            continue
        if rel.target_id == guild_objs[0].object_id:
            obj = store.get_object(rel.source_id)
            if obj and obj.class_name == "guild_goal":
                goals.append(obj)
    return goals
