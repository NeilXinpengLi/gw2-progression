"""Quest tracking service — track daily quest completion for the coach plan."""

from datetime import datetime, timedelta, timezone

from gw2_progression.database import using_db

COACH_QUESTS = [
    {"key": "sell_liquidate", "label": "Sell & Liquidate — Review TP, sell excess, consolidate gold"},
    {"key": "goal_progress", "label": "Goal Progress — Farm materials, craft time-gated items"},
    {"key": "build_gear", "label": "Build Gear — Acquire missing items, run fractals"},
    {"key": "map_completion", "label": "Map Completion — Gather volatile magic, farm currencies"},
    {"key": "fractal_push", "label": "Fractal Push — Run T4 dailies + recs"},
    {"key": "wvw_pvp", "label": "WvW / PvP — Complete weekly rewards, earn tickets"},
    {"key": "review_plan", "label": "Review & Plan — Assess progress, plan next week"},
]


def _week_start() -> str:
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.strftime("%Y-%m-%d")


async def get_week_quests(account_name: str) -> list[dict]:
    ws = _week_start()
    rows = []
    async with using_db() as conn:
        cursor = await conn.execute(
            "SELECT quest_key, quest_label, day_index, completed FROM quest_progress WHERE account_name = ? AND week_start = ?",
            (account_name, ws),
        )
        rows = await cursor.fetchall()
    saved = {r[0]: {"label": r[1], "day": r[2], "done": bool(r[3])} for r in rows}

    result = []
    for q in COACH_QUESTS:
        if q["key"] in saved:
            result.append({**q, "day_index": saved[q["key"]]["day"], "completed": saved[q["key"]]["done"]})
        else:
            result.append({**q, "day_index": -1, "completed": False})
    return result


async def toggle_quest(account_name: str, quest_key: str, completed: bool, day_index: int = -1) -> dict:
    ws = _week_start()
    async with using_db() as conn:
        cursor = await conn.execute(
            "SELECT id FROM quest_progress WHERE account_name = ? AND quest_key = ? AND week_start = ?",
            (account_name, quest_key, ws),
        )
        existing = await cursor.fetchone()
        if existing:
            await conn.execute(
                "UPDATE quest_progress SET completed = ?, day_index = ? WHERE id = ?",
                (1 if completed else 0, day_index, existing[0]),
            )
        else:
            label = next((q["label"] for q in COACH_QUESTS if q["key"] == quest_key), quest_key)
            await conn.execute(
                "INSERT INTO quest_progress (account_name, quest_key, quest_label, day_index, completed, week_start) VALUES (?, ?, ?, ?, ?, ?)",
                (account_name, quest_key, label, day_index, 1 if completed else 0, ws),
            )
    return {"quest_key": quest_key, "completed": completed}


async def get_week_summary(account_name: str) -> dict:
    quests = await get_week_quests(account_name)
    total = len(quests)
    done = sum(1 for q in quests if q["completed"])
    return {
        "total": total,
        "completed": done,
        "progress_pct": round(done / total * 100) if total else 0,
        "quests": quests,
    }
