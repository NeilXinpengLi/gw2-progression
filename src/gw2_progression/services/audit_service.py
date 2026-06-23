"""Audit logging — record sensitive operations for security review."""

from gw2_progression.database import using_db


async def record_audit(
    actor: str = "",
    action: str = "",
    resource: str = "",
    detail: str = "",
    ip_address: str = "",
    success: bool = True,
) -> None:
    async with using_db() as conn:
        await conn.execute(
            """INSERT INTO audit_log (actor, action, resource, detail, ip_address, success)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (actor, action, resource, detail[:500], ip_address, 1 if success else 0),
        )


async def get_audit_log(limit: int = 50, action: str | None = None) -> list[dict]:
    rows = []
    async with using_db() as conn:
        if action:
            cursor = await conn.execute(
                "SELECT * FROM audit_log WHERE action = ? ORDER BY created_at DESC LIMIT ?",
                (action, limit),
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
    return [
        {
            "id": r[0],
            "actor": r[1],
            "action": r[2],
            "resource": r[3],
            "detail": r[4],
            "ip_address": r[5],
            "success": bool(r[6]),
            "created_at": r[7],
        }
        for r in rows
    ]
