"""v5 Self-Evolving Learning Engine — experience recording, reward computation, weight adaptation."""

import logging
from datetime import datetime, timezone

from gw2_progression.database import using_db

logger = logging.getLogger("gw2.v5")

DEFAULT_WEIGHTS = {
    "gold_weight": 0.3,
    "build_weight": 0.3,
    "legendary_weight": 0.3,
    "time_weight": -0.2,
    "risk_weight": -0.05,
}

LEARNING_RATE = 0.1


async def record_experience(
    account_name: str,
    action_key: str,
    action_label: str = "",
    strategy: str = "hybrid",
    gold_impact: int = 0,
    build_impact: float = 0.0,
    legendary_impact: float = 0.0,
    time_spent_minutes: int = 0,
    success: bool = True,
) -> dict:
    try:
        from ..ontology.action_registry import execute_action
        await execute_action(
            "sync_account_snapshot",
            account_name=account_name,
            params={"action_key": action_key, "success": success},
            force=True,
        )
    except Exception:
        pass

    reward = _compute_reward(gold_impact, build_impact, legendary_impact, time_spent_minutes, success)

    async with using_db() as conn:
        cursor = await conn.execute(
            """INSERT INTO experiences
               (account_name, action_key, action_label, strategy, reward, outcome, gold_impact, build_impact, legendary_impact, time_spent_minutes, success)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (account_name, action_key, action_label, strategy, reward, "success" if success else "failure", gold_impact, build_impact, legendary_impact, time_spent_minutes, 1 if success else 0),
        )
        exp_id = cursor.lastrowid

    # Update user model with new experience
    await _update_user_model(account_name)

    return {"experience_id": exp_id, "reward": round(reward, 3)}


async def get_user_model(account_name: str) -> dict:
    """Get or create a user model with personalized weights."""
    async with using_db() as conn:
        cursor = await conn.execute("SELECT * FROM user_models WHERE account_name = ?", (account_name,))
        row = await cursor.fetchone()

    if row:
        return {
            "account_name": row[1],
            "preferred_strategy": row[2],
            "gold_weight": row[3],
            "build_weight": row[4],
            "legendary_weight": row[5],
            "time_weight": row[6],
            "risk_weight": row[7],
            "total_experiences": row[8],
            "avg_reward": row[9],
        }

    # Create default model
    async with using_db() as conn:
        await conn.execute("INSERT INTO user_models (account_name) VALUES (?)", (account_name,))
    return {"account_name": account_name, **DEFAULT_WEIGHTS, "total_experiences": 0, "avg_reward": 0.0}


async def get_recent_experiences(account_name: str, limit: int = 20) -> list[dict]:
    """Get recent experiences for a user."""
    rows = []
    async with using_db() as conn:
        cursor = await conn.execute("SELECT * FROM experiences WHERE account_name = ? ORDER BY created_at DESC LIMIT ?", (account_name, limit))
        rows = await cursor.fetchall()
    return [
        {
            "id": r[0],
            "action_key": r[2],
            "action_label": r[3],
            "strategy": r[4],
            "reward": r[5],
            "outcome": r[6],
            "gold_impact": r[7],
            "build_impact": r[8],
            "legendary_impact": r[9],
            "time_spent_minutes": r[10],
            "success": bool(r[11]),
            "created_at": r[12],
        }
        for r in rows
    ]


async def get_personalized_weights(account_name: str) -> dict:
    """Get personalized weights, falling back to defaults if insufficient data."""
    model = await get_user_model(account_name)
    if model["total_experiences"] < 5:
        return DEFAULT_WEIGHTS
    return {
        "gold_weight": model["gold_weight"],
        "build_weight": model["build_weight"],
        "legendary_weight": model["legendary_weight"],
        "time_weight": model["time_weight"],
        "risk_weight": model["risk_weight"],
    }


async def update_preferred_strategy(account_name: str, strategy: str) -> None:
    """Update the user's preferred strategy based on behavior."""
    async with using_db() as conn:
        await conn.execute("UPDATE user_models SET preferred_strategy = ? WHERE account_name = ?", (strategy, account_name))


def _compute_reward(gold_impact: int, build_impact: float, legendary_impact: float, time_minutes: int, success: bool) -> float:
    """Compute a reward score from action outcome."""
    base = 0.0
    base += min(gold_impact / 10000 / 100, 1.0) * 0.4
    base += build_impact * 0.3
    base += legendary_impact * 0.3
    base -= (time_minutes / 120) * 0.1
    if not success:
        base *= -0.5
    return max(-1.0, min(1.0, base))


async def _update_user_model(account_name: str) -> None:
    """Update the user model from accumulated experiences."""
    async with using_db() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*), AVG(reward), AVG(CASE WHEN gold_impact > 0 THEN 1.0 ELSE 0.0 END), AVG(build_impact), AVG(legendary_impact) FROM experiences WHERE account_name = ? AND success = 1",
            (account_name,),
        )
        row = await cursor.fetchone()
        if not row or not row[0]:
            return

        total_exp = row[0]
        avg_reward = row[1] or 0.0
        gold_affinity = row[2] or 0.0
        build_affinity = row[3] or 0.0
        legendary_affinity = row[4] or 0.0

        # Adjust weights based on user affinity
        weights = {
            "gold_weight": 0.1 + gold_affinity * 0.5,
            "build_weight": 0.1 + build_affinity * 0.5,
            "legendary_weight": 0.1 + legendary_affinity * 0.5,
            "time_weight": -0.3 + (1 - gold_affinity) * 0.1,
            "risk_weight": -0.1 * (1 - gold_affinity * 0.5),
        }

        await conn.execute(
            """UPDATE user_models SET
               gold_weight = ?, build_weight = ?, legendary_weight = ?,
               time_weight = ?, risk_weight = ?,
               total_experiences = ?, avg_reward = ?, updated_at = ?
               WHERE account_name = ?""",
            (
                weights["gold_weight"],
                weights["build_weight"],
                weights["legendary_weight"],
                weights["time_weight"],
                weights["risk_weight"],
                total_exp,
                round(avg_reward, 3),
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                account_name,
            ),
        )
