"""Workspace service — multi-tenant team workspaces."""

import secrets

from gw2_progression.database import using_db


async def create_workspace(name: str, owner_account: str) -> dict:
    slug = name.lower().replace(" ", "-") + "-" + secrets.token_hex(3)
    async with using_db() as conn:
        cursor = await conn.execute(
            "INSERT INTO workspaces (name, slug, owner_account) VALUES (?, ?, ?)",
            (name, slug, owner_account),
        )
        ws_id = cursor.lastrowid
        await conn.execute(
            "INSERT INTO workspace_members (workspace_id, account_name, role) VALUES (?, ?, 'admin')",
            (ws_id, owner_account),
        )
        return {"id": ws_id, "name": name, "slug": slug, "owner": owner_account, "member_count": 1}


async def get_workspace(workspace_id: int) -> dict | None:
    async with using_db() as conn:
        cursor = await conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        cursor = await conn.execute(
            "SELECT account_name, role, created_at FROM workspace_members WHERE workspace_id = ? ORDER BY role, created_at",
            (workspace_id,),
        )
        members = await cursor.fetchall()
    return {
        "id": row[0],
        "name": row[1],
        "slug": row[2],
        "owner": row[3],
        "created_at": row[4],
        "members": [{"account_name": m[0], "role": m[1], "joined_at": m[2]} for m in members],
    }


async def list_workspaces(account_name: str) -> list[dict]:
    rows = []
    async with using_db() as conn:
        cursor = await conn.execute(
            """SELECT w.id, w.name, w.slug, wm.role FROM workspaces w
               JOIN workspace_members wm ON w.id = wm.workspace_id
               WHERE wm.account_name = ? ORDER BY wm.created_at DESC""",
            (account_name,),
        )
        rows = await cursor.fetchall()
    return [{"id": r[0], "name": r[1], "slug": r[2], "role": r[3]} for r in rows]


async def add_member(workspace_id: int, account_name: str, role: str = "member") -> bool:
    async with using_db() as conn:
        try:
            await conn.execute(
                "INSERT INTO workspace_members (workspace_id, account_name, role) VALUES (?, ?, ?)",
                (workspace_id, account_name, role),
            )
            return True
        except Exception:
            return False


async def update_role(workspace_id: int, account_name: str, role: str) -> bool:
    async with using_db() as conn:
        cursor = await conn.execute(
            "UPDATE workspace_members SET role = ? WHERE workspace_id = ? AND account_name = ?",
            (role, workspace_id, account_name),
        )
        return cursor.rowcount > 0


async def remove_member(workspace_id: int, account_name: str) -> bool:
    async with using_db() as conn:
        cursor = await conn.execute(
            "DELETE FROM workspace_members WHERE workspace_id = ? AND account_name = ? AND role != 'admin'",
            (workspace_id, account_name),
        )
        return cursor.rowcount > 0
