"""Audit logging — record sensitive operations for security review.

Fire-and-forget via event bus. Never blocks the request path.
"""

import logging
from typing import Any

from gw2_progression.database import using_db
from gw2_progression.services.event_bus import EventType, emit, on

logger = logging.getLogger("gw2.audit")


async def record_audit(
    actor: str = "",
    action: str = "",
    resource: str = "",
    detail: str = "",
    ip_address: str = "",
    success: bool = True,
) -> None:
    """Push audit event to event bus (non-blocking, fire-and-forget)."""
    emit(
        EventType.AUDIT,
        payload={
            "actor": actor,
            "action": action,
            "resource": resource,
            "detail": detail[:500],
            "ip_address": ip_address,
            "success": 1 if success else 0,
        },
        source="audit_service",
    )


@on(EventType.AUDIT)
async def _handle_audit(event: Any) -> None:
    """Event bus consumer: write audit events to DB."""
    ev = event.payload
    try:
        async with using_db() as conn:
            await conn.execute(
                """INSERT INTO audit_log (actor, action, resource, detail, ip_address, success)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (ev["actor"], ev["action"], ev["resource"], ev["detail"], ev["ip_address"], ev["success"]),
            )
    except Exception as e:
        logger.warning("Audit write failed (dropping event): %s", e)


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
