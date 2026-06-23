"""Guild workspace service — group accounts for aggregated analysis."""

import hashlib
import logging
import secrets

from gw2_progression.database import using_db

logger = logging.getLogger("gw2.guild")


def _hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:16]


async def create_guild(name: str, creator_account: str, creator_api_key: str) -> dict:
    invite_code = secrets.token_hex(6)
    async with using_db() as conn:
        cursor = await conn.execute(
            "INSERT INTO guild_workspaces (name, invite_code) VALUES (?, ?)",
            (name, invite_code),
        )
        guild_id = cursor.lastrowid
        await conn.execute(
            """INSERT INTO guild_members (guild_id, account_name, api_key_hash, role)
               VALUES (?, ?, ?, 'leader')""",
            (guild_id, creator_account, _hash_api_key(creator_api_key)),
        )
    return {"id": guild_id, "name": name, "invite_code": invite_code, "member_count": 1}


async def join_guild(invite_code: str, account_name: str, api_key: str) -> dict | None:
    async with using_db() as conn:
        cursor = await conn.execute("SELECT id FROM guild_workspaces WHERE invite_code = ?", (invite_code,))
        row = await cursor.fetchone()
        if not row:
            return None
        guild_id = row[0]
        await conn.execute(
            """INSERT OR IGNORE INTO guild_members (guild_id, account_name, api_key_hash)
               VALUES (?, ?, ?)""",
            (guild_id, account_name, _hash_api_key(api_key)),
        )
    return await get_guild(guild_id)


async def get_guild(guild_id: int) -> dict | None:
    async with using_db() as conn:
        cursor = await conn.execute("SELECT * FROM guild_workspaces WHERE id = ?", (guild_id,))
        guild = await cursor.fetchone()
        if not guild:
            return None
        cursor = await conn.execute(
            "SELECT account_name, role, created_at FROM guild_members WHERE guild_id = ? ORDER BY created_at",
            (guild_id,),
        )
        members = await cursor.fetchall()
    return {
        "id": guild[0],
        "name": guild[1],
        "invite_code": guild[2],
        "created_at": guild[3],
        "members": [{"account_name": m[0], "role": m[1], "joined_at": m[2]} for m in members],
    }


async def get_guild_by_account(account_name: str) -> dict | None:
    async with using_db() as conn:
        cursor = await conn.execute(
            """SELECT g.id, g.name, g.invite_code FROM guild_workspaces g
               JOIN guild_members m ON g.id = m.guild_id
               WHERE m.account_name = ?""",
            (account_name,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return await get_guild(row[0])


async def leave_guild(account_name: str) -> bool:
    async with using_db() as conn:
        cursor = await conn.execute(
            "DELETE FROM guild_members WHERE account_name = ? AND role != 'leader'",
            (account_name,),
        )
        return cursor.rowcount > 0


async def get_member_accounts(guild_id: int) -> list[str]:
    async with using_db() as conn:
        cursor = await conn.execute("SELECT account_name FROM guild_members WHERE guild_id = ?", (guild_id,))
        rows = await cursor.fetchall()
    return [r[0] for r in rows]
