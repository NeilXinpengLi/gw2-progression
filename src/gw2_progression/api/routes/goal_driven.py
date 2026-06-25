"""Goal-Driven API — Lovable-style goal interpretation, plan generation, and revision.

Endpoints:
  POST /goal-driven/interpret      — Parse natural language goal
  POST /goal-driven/generate       — Generate complete plan from goal
  POST /goal-driven/revise         — Revise existing plan
  GET  /goal-driven/plan/{id}      — Get full plan
  POST /goal-driven/progressive    — Progressive result streaming
"""

import logging

from fastapi import APIRouter, Body, HTTPException

from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.models import (
    GoalInterpretResponse,
    PlanAction,
    PlanGenerateResponse,
    PlanReviseResponse,
    ProgressionPlan,
    ProgressiveResult,
)
from gw2_progression.services.goal_driven_engine import (
    generate_plan_from_goal,
    generate_progressive_result,
)
from gw2_progression.services.goal_interpreter import generate_alternatives, interpret_goal
from gw2_progression.services.plan_iteration_engine import apply_revision

logger = logging.getLogger("gw2.goal_driven")
router = APIRouter(prefix="/goal-driven", tags=["goal-driven"])


@router.post("/interpret", response_model=GoalInterpretResponse)
async def post_interpret(body: dict = Body(...)):
    """Parse a natural language goal into a structured goal object."""
    goal_text = body.get("goal_text", "").strip()
    if not goal_text:
        raise HTTPException(status_code=422, detail="goal_text is required")

    try:
        parsed = await interpret_goal(goal_text)
        alternatives = await generate_alternatives(parsed)
        return GoalInterpretResponse(parsed=parsed, alternatives=alternatives[1:4])
    except Exception as e:
        logger.exception("Goal interpretation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=PlanGenerateResponse)
async def post_generate(body: dict = Body(...)):
    """Generate a complete progression plan from a goal."""
    api_key = body.get("api_key", "")
    goal_text = body.get("goal_text", "").strip()
    strategy = body.get("strategy", "balanced")
    time_budget = body.get("time_budget_minutes", 0)
    gold_budget = body.get("gold_budget_copper", 0)

    if not api_key:
        raise HTTPException(status_code=422, detail="api_key is required")
    if not goal_text:
        raise HTTPException(status_code=422, detail="goal_text is required")

    try:
        # Parse the goal
        parsed = await interpret_goal(goal_text)

        # Override with explicit parameters if provided
        if strategy and strategy != "balanced":
            parsed.strategy = strategy
        if time_budget:
            parsed.time_budget_minutes = time_budget
        if gold_budget:
            parsed.gold_budget_copper = gold_budget

        # Generate plan
        plan = await generate_plan_from_goal(api_key, parsed)
        top_actions = plan.actions[:3]

        # Build 7-day plan (actions grouped by day)
        seven_day: list[list[PlanAction]] = [[] for _ in range(7)]
        for a in plan.actions:
            day_idx = min(max(a.day_index, 0), 6)
            seven_day[day_idx].append(a)

        # Generate report preview
        wallet_gold = 0
        try:
            from gw2_progression.analyzer import fetch_all
            contents = await fetch_all(api_key)
            for w in contents.wallet or []:
                if w.get("id") == 1:
                    wallet_gold = w.get("value", 0) // 10000
        except Exception:
            pass

        report_preview = (
            f"Account: {plan.account_name} | "
            f"Wallet: {wallet_gold}g | "
            f"Goal: {parsed.target_item_name or goal_text[:50]} | "
            f"Completion: {plan.completion_percent:.0f}% | "
            f"Estimated: {plan.estimated_days} days | "
            f"Top actions: {len(top_actions)}"
        )

        return PlanGenerateResponse(
            plan=plan,
            insight=plan.insight,
            top_actions=top_actions,
            seven_day_plan=seven_day,
            report_preview=report_preview,
            tier="free",
        )
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except Exception as e:
        logger.exception("Plan generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/revise", response_model=PlanReviseResponse)
async def post_revise(body: dict = Body(...)):
    """Revise an existing plan based on user feedback."""
    plan_id = body.get("plan_id", "")
    revision_text = body.get("revision_text", "").strip()
    api_key = body.get("api_key", "")

    if not plan_id:
        raise HTTPException(status_code=422, detail="plan_id is required")
    if not revision_text:
        raise HTTPException(status_code=422, detail="revision_text is required")

    try:
        # Load stored plan
        plan = await _load_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # Apply revision
        revised_plan, revision = await apply_revision(plan, revision_text, api_key)

        # Save revision
        await _save_revision(plan, revision)

        return PlanReviseResponse(
            revised_plan=revised_plan,
            delta_summary=revision.delta_summary,
            changed_actions=[a.title for a in revised_plan.actions[:3]],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Plan revision failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plan/{plan_id}")
async def get_plan(plan_id: str):
    """Get a full plan by ID."""
    plan = await _load_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.post("/progressive", response_model=ProgressiveResult)
async def post_progressive(body: dict = Body(...)):
    """Get progressive account results (stage 1: instant wallet + characters)."""
    api_key = body.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key is required")

    try:
        result = await generate_progressive_result(api_key)
        return result
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except Exception as e:
        logger.exception("Progressive result failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/progressive/full")
async def post_progressive_full(body: dict = Body(...)):
    """Run full progressive analysis across all 4 stages and return all results.

    Stage 1 (1-3s):  account_name, wallet_gold, character_count
    Stage 2 (3-8s):  total_value_estimate, hidden_wealth, top_assets
    Stage 3 (8-15s): best_build, closest_goal, first_action
    Stage 4 (15-30s): full plan with actions and 7-day schedule
    """
    from gw2_progression.services.progressive_stream_service import run_progressive_analysis

    api_key = body.get("api_key", "")
    goal_text = body.get("goal_text", "")

    if not api_key:
        raise HTTPException(status_code=422, detail="api_key is required")

    try:
        results = await run_progressive_analysis(api_key, goal_text)
        return {"stages": results, "total_stages": len(results)}
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)
    except Exception as e:
        logger.exception("Progressive full analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


# ── Helper: In-memory plan storage (can be replaced with DB) ──

_plan_store: dict[str, ProgressionPlan] = {}
_revision_store: dict[str, list] = {}


async def _save_plan(plan: ProgressionPlan):
    """Save a plan to in-memory store."""
    _plan_store[plan.plan_id] = plan
    # Also persist to DB
    from gw2_progression.database import get_db
    try:
        db = await get_db()
        await db.execute(
            """INSERT OR REPLACE INTO progression_plans
            (plan_id, goal_id, account_name, strategy, total_cost_copper,
             estimated_days, completion_percent, status, insight, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (plan.plan_id, plan.goal_id or "", plan.account_name, plan.strategy,
             plan.total_cost_copper, plan.estimated_days, plan.completion_percent,
             plan.status, plan.insight, plan.created_at),
        )
        for a in plan.actions:
            await db.execute(
                """INSERT OR REPLACE INTO plan_actions
                (action_id, plan_id, action_type, title, reason, reward_gold,
                 cost_gold, time_cost_minutes, score, priority, status, tab,
                 item_id, day_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (a.action_id, plan.plan_id, a.action_type, a.title, a.reason,
                 a.reward_gold, a.cost_gold, a.time_cost_minutes, a.score,
                 a.priority, a.status, a.tab, a.item_id, a.day_index),
            )
        await db.commit()
    except Exception as e:
        logger.warning("Failed to persist plan: %s", e)
    finally:
        try:
            await db.close()
        except Exception:
            pass


async def _load_plan(plan_id: str) -> ProgressionPlan | None:
    """Load a plan from in-memory store or DB."""
    if plan_id in _plan_store:
        return _plan_store[plan_id]

    from gw2_progression.database import get_db
    try:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM progression_plans WHERE plan_id = ?", (plan_id,))
        row = await cursor.fetchone()
        if not row:
            return None

        plan = ProgressionPlan(
            plan_id=row["plan_id"],
            goal_id=row["goal_id"],
            account_name=row["account_name"],
            strategy=row["strategy"],
            total_cost_copper=row["total_cost_copper"],
            estimated_days=row["estimated_days"],
            completion_percent=row["completion_percent"],
            status=row["status"],
            insight=row["insight"],
            created_at=row["created_at"],
        )

        cursor2 = await db.execute(
            "SELECT * FROM plan_actions WHERE plan_id = ? ORDER BY priority",
            (plan_id,),
        )
        rows = await cursor2.fetchall()
        plan.actions = [
            PlanAction(
                action_id=r["action_id"],
                plan_id=r["plan_id"],
                action_type=r["action_type"],
                title=r["title"],
                reason=r["reason"],
                reward_gold=r["reward_gold"],
                cost_gold=r["cost_gold"],
                time_cost_minutes=r["time_cost_minutes"],
                score=r["score"],
                priority=r["priority"],
                status=r["status"],
                tab=r["tab"],
                item_id=r["item_id"],
                day_index=r["day_index"],
            )
            for r in rows
        ]

        _plan_store[plan_id] = plan
        return plan
    except Exception as e:
        logger.warning("Failed to load plan from DB: %s", e)
        return _plan_store.get(plan_id)
    finally:
        try:
            await db.close()
        except Exception:
            pass


async def _save_revision(plan: ProgressionPlan, revision):
    """Save a revision record."""
    if plan.plan_id not in _revision_store:
        _revision_store[plan.plan_id] = []
    _revision_store[plan.plan_id].append(revision)

    from gw2_progression.database import get_db
    try:
        db = await get_db()
        await db.execute(
            """INSERT INTO plan_revisions
            (revision_id, plan_id, user_request, previous_strategy, new_strategy, delta_summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (revision.revision_id, revision.plan_id, revision.user_request,
             revision.previous_strategy, revision.new_strategy,
             revision.delta_summary, revision.created_at),
        )
        await db.commit()
    except Exception as e:
        logger.warning("Failed to persist revision: %s", e)
    finally:
        try:
            await db.close()
        except Exception:
            pass
