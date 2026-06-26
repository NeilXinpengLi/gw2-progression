"""Goal tracker service: create, update, refresh goals."""

import logging
import uuid
from datetime import datetime, timezone

from ..database import get_db
from ..models import TrackedGoal
from ..ontology import goal_mapper as ontology_goal
from .crafting_plan_service import create_plan

logger = logging.getLogger("gw2.goal")


async def create_goal(api_key: str, target_item_id: int, target_count: int = 1, priority: str = "normal") -> TrackedGoal:
    from ..analyzer import fetch_all

    contents = await fetch_all(api_key)
    account_name = contents.account_name or "unknown"
    now = datetime.now(timezone.utc).isoformat()

    goal = TrackedGoal(
        goal_id=uuid.uuid4().hex[:12],
        account_name=account_name,
        target_item_id=target_item_id,
        target_count=target_count,
        status="active",
        priority=priority,
        created_at=now,
        updated_at=now,
    )

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO tracked_goals
            (goal_id, account_name, target_item_id, target_count, status, priority,
             completion_percent, owned_material_value, missing_material_value,
             missing_item_count, estimated_remaining_cost, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                goal.goal_id,
                goal.account_name,
                goal.target_item_id,
                goal.target_count,
                goal.status,
                goal.priority,
                goal.completion_percent,
                goal.owned_material_value,
                goal.missing_material_value,
                goal.missing_item_count,
                goal.estimated_remaining_cost,
                goal.created_at,
                goal.updated_at,
            ),
        )
        await db.commit()
    finally:
        await db.close()

    try:
        ontology_goal.map_goal_to_ontology(goal)
        await ontology_goal.sync_goal_reservations(goal.account_name)
    except Exception as e:
        logger.warning("Ontology sync for goal %s failed (continuing): %s", goal.goal_id, e)

    return goal


async def get_goals(account_name: str) -> list[TrackedGoal]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM tracked_goals WHERE account_name = ? ORDER BY status, priority, created_at DESC",
            (account_name,),
        )
        rows = await cursor.fetchall()
        return [TrackedGoal(**dict(r)) for r in rows]
    finally:
        await db.close()


async def get_goal(goal_id: str) -> TrackedGoal | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM tracked_goals WHERE goal_id = ?", (goal_id,))
        row = await cursor.fetchone()
        return TrackedGoal(**dict(row)) if row else None
    finally:
        await db.close()


async def refresh_goal(api_key: str, goal_id: str) -> TrackedGoal:
    goal = await get_goal(goal_id)
    if not goal:
        raise ValueError(f"Goal {goal_id} not found")

    plan = await create_plan(
        api_key=api_key,
        target_item_id=goal.target_item_id,
        quantity=goal.target_count,
        use_owned=True,
    )

    total_material_value = plan.missing_material_cost + plan.owned_material_value_used
    completion = round(plan.owned_material_value_used / total_material_value * 100, 1) if total_material_value > 0 else 0.0

    now = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    try:
        await db.execute(
            """UPDATE tracked_goals SET
            completion_percent=?, owned_material_value=?, missing_material_value=?,
            missing_item_count=?, estimated_remaining_cost=?, updated_at=?
            WHERE goal_id=?""",
            (
                completion,
                plan.owned_material_value_used,
                plan.missing_material_cost,
                len([line for line in plan.lines if line.missing_count > 0]),
                plan.missing_material_cost,
                now,
                goal_id,
            ),
        )
        await db.commit()
    finally:
        await db.close()

    goal.completion_percent = completion
    goal.owned_material_value = plan.owned_material_value_used
    goal.missing_material_value = plan.missing_material_cost
    goal.missing_item_count = len([line for line in plan.lines if line.missing_count > 0])
    goal.estimated_remaining_cost = plan.missing_material_cost
    goal.updated_at = now

    if completion >= 100:
        goal.status = "completed"

    try:
        await ontology_goal.sync_goal_reservations(goal.account_name)
    except Exception as e:
        logger.warning("Ontology reservation sync after refresh failed (continuing): %s", e)

    return goal


async def delete_goal(goal_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM tracked_goals WHERE goal_id = ?", (goal_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
