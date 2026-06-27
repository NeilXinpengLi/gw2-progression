"""Session-based authentication with persistent DB storage."""

import secrets
import time
from datetime import datetime, timezone

from ..database import using_db

SESSION_TTL = 86400  # 24 hours


async def create_session(api_key: str, account_name: str) -> str:
    token = secrets.token_hex(24)
    now = datetime.now(timezone.utc).isoformat()
    async with using_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO account_sessions (token, api_key, account_name, created_at, last_used_at) VALUES (?, ?, ?, ?, ?)",
            (token, api_key, account_name, now, now),
        )
    return token


async def get_session(token: str) -> dict | None:
    async with using_db() as db:
        cursor = await db.execute("SELECT * FROM account_sessions WHERE token = ?", (token,))
        row = await cursor.fetchone()
        if not row:
            return None
        created = datetime.fromisoformat(row["created_at"])
        if time.time() - created.timestamp() > SESSION_TTL:
            await db.execute("DELETE FROM account_sessions WHERE token = ?", (token,))
            return None
        now = datetime.now(timezone.utc).isoformat()
        await db.execute("UPDATE account_sessions SET last_used_at = ? WHERE token = ?", (now, token))
        return {"api_key": row["api_key"], "account_name": row["account_name"]}


async def get_api_key(token_or_key: str) -> str | None:
    """Extract API key from token or return as-is if it looks like a key."""
    if len(token_or_key) >= 40 and not token_or_key.startswith("Bearer "):
        session = await get_session(token_or_key)
        if session:
            return session["api_key"]
    return token_or_key


async def list_sessions(account_name: str | None = None) -> list[dict]:
    async with using_db() as db:
        if account_name:
            cursor = await db.execute("SELECT token, account_name, created_at, last_used_at FROM account_sessions WHERE account_name = ? ORDER BY last_used_at DESC", (account_name,))
        else:
            cursor = await db.execute("SELECT token, account_name, created_at, last_used_at FROM account_sessions ORDER BY last_used_at DESC")
        rows = await cursor.fetchall()
        return [{"token": r["token"][:12] + "...", "account_name": r["account_name"], "created_at": r["created_at"], "last_used_at": r["last_used_at"]} for r in rows]


async def delete_session(token: str) -> bool:
    async with using_db() as db:
        cursor = await db.execute("DELETE FROM account_sessions WHERE token = ?", (token,))
        return cursor.rowcount > 0


async def cleanup_expired():
    async with using_db() as db:
        cutoff = datetime.now(timezone.utc).timestamp() - SESSION_TTL
        await db.execute("DELETE FROM account_sessions WHERE created_at < ?", (datetime.fromtimestamp(cutoff, timezone.utc).isoformat(),))
