"""Quest / Achievement Tracking Ontology — maps quest progress, achievements,
and their relationships to goals and rewards.

Enables the system to answer: which achievements progress which legendary goals?
Which quests are blocked by incomplete achievements?
What rewards does a completed quest unlock?
"""

import logging
from datetime import datetime, timezone
from typing import Any

from . import object_store as store
from .models import OntologyObject

logger = logging.getLogger("gw2.ontology.quest")

COACH_QUEST_CLASS_MAP = {
    "sell_liquidate": "quest_sell",
    "goal_progress": "quest_goal",
    "build_gear": "quest_build",
    "map_completion": "quest_map",
    "fractal_push": "quest_fractal",
    "wvw_pvp": "quest_wvw",
    "review_plan": "quest_review",
}


def map_quest_to_ontology(
    quest_key: str,
    quest_label: str,
    account_name: str,
    completed: bool = False,
    day_index: int = -1,
) -> OntologyObject:
    class_name = COACH_QUEST_CLASS_MAP.get(quest_key, "quest")
    obj = store.register_object(
        class_name=class_name,
        account_name=account_name,
        properties={
            "quest_key": quest_key,
            "label": quest_label,
            "completed": completed,
            "day_index": day_index,
            "week_start": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
        privacy_scope="private",
    )
    return obj


def map_achievement_to_ontology(
    achievement_id: int,
    name: str,
    account_name: str,
    current: int = 0,
    max_count: int = 1,
    done: bool = False,
    required_for_goals: list[str] | None = None,
) -> OntologyObject:
    obj = store.register_object(
        class_name="achievement",
        account_name=account_name,
        properties={
            "achievement_id": achievement_id,
            "name": name,
            "current": current,
            "max": max_count,
            "done": done,
            "progress_pct": round(current / max_count * 100, 1) if max_count > 0 else 0.0,
            "required_for_goals": required_for_goals or [],
        },
        privacy_scope="private",
    )
    return obj


async def sync_quests_to_ontology(account_name: str) -> list[OntologyObject]:
    created: list[OntologyObject] = []

    from ..services.quest_service import get_week_quests
    quests = await get_week_quests(account_name)
    for q in quests:
        obj = map_quest_to_ontology(
            quest_key=q["key"],
            quest_label=q["label"],
            account_name=account_name,
            completed=q.get("completed", False),
            day_index=q.get("day_index", -1),
        )
        created.append(obj)

        goal_objs = store.get_objects_by_account("legendary_goal", account_name)
        for goal in goal_objs:
            store.register_relation(
                source_id=obj.object_id,
                target_id=goal.object_id,
                relation_type="progresses",
                confidence=0.60,
            )

    logger.info("Synced %d quests to ontology for %s", len(quests), account_name)
    return created


def get_quests_by_account(account_name: str) -> list[OntologyObject]:
    results: list[OntologyObject] = []
    for class_name in COACH_QUEST_CLASS_MAP.values():
        results.extend(store.get_objects_by_account(class_name, account_name))
    return results


def get_completed_quests(account_name: str) -> list[OntologyObject]:
    return [
        o for o in get_quests_by_account(account_name)
        if o.properties.get("completed")
    ]


def get_weekly_quest_progress(account_name: str) -> dict[str, Any]:
    quests = get_quests_by_account(account_name)
    total = len(quests)
    done = sum(1 for q in quests if q.properties.get("completed"))
    return {
        "account_name": account_name,
        "total": total,
        "completed": done,
        "progress_pct": round(done / total * 100, 1) if total else 0.0,
        "quests": [q.properties for q in quests],
    }
