"""Credential service — manage encrypted API keys for external providers."""

from gw2_progression.database import using_db
from gw2_progression.services.crypto import decrypt_value, encrypt_value, fingerprint


async def save_credential(
    provider: str,
    api_key: str,
    label: str = "",
    session_token: str | None = None,
) -> dict:
    encrypted = encrypt_value(api_key)
    fp = fingerprint(api_key)
    async with using_db() as conn:
        cursor = await conn.execute(
            """INSERT INTO credentials (provider, label, encrypted_value, fingerprint, session_token)
               VALUES (?, ?, ?, ?, ?)""",
            (provider, label, encrypted, fp, session_token),
        )
        return {
            "id": cursor.lastrowid,
            "provider": provider,
            "label": label,
            "fingerprint": fp,
        }


async def list_credentials(session_token: str | None = None) -> list[dict]:
    if session_token:
        query = "SELECT id, provider, label, fingerprint, last_used_at, created_at FROM credentials WHERE session_token = ? ORDER BY created_at DESC"
        params = (session_token,)
    else:
        query = "SELECT id, provider, label, fingerprint, last_used_at, created_at FROM credentials ORDER BY created_at DESC"
        params = ()

    rows = []
    async with using_db() as conn:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
    return [
        {
            "id": r[0],
            "provider": r[1],
            "label": r[2],
            "fingerprint": r[3],
            "last_used_at": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]


async def get_credential(credential_id: int) -> dict | None:
    async with using_db() as conn:
        cursor = await conn.execute(
            "SELECT id, provider, label, encrypted_value, fingerprint, session_token FROM credentials WHERE id = ?",
            (credential_id,),
        )
        row = await cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "provider": row[1],
        "label": row[2],
        "encrypted_value": row[3],
        "fingerprint": row[4],
        "session_token": row[5],
    }


async def get_decrypted_key(credential_id: int) -> str | None:
    cred = await get_credential(credential_id)
    if not cred:
        return None
    return decrypt_value(cred["encrypted_value"])


async def get_key_by_provider(provider: str, session_token: str | None = None) -> str | None:
    if session_token:
        query = "SELECT encrypted_value FROM credentials WHERE provider = ? AND session_token = ? ORDER BY created_at DESC LIMIT 1"
        params = (provider, session_token)
    else:
        query = "SELECT encrypted_value FROM credentials WHERE provider = ? ORDER BY created_at DESC LIMIT 1"
        params = (provider,)

    async with using_db() as conn:
        cursor = await conn.execute(query, params)
        row = await cursor.fetchone()
    if not row:
        return None
    return decrypt_value(row[0])


async def delete_credential(credential_id: int) -> bool:
    async with using_db() as conn:
        cursor = await conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
        return cursor.rowcount > 0


async def touch_credential(credential_id: int) -> None:
    from datetime import datetime

    async with using_db() as conn:
        await conn.execute(
            "UPDATE credentials SET last_used_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), credential_id),
        )


async def update_credential_status(credential_id: int, status: str, scopes: str = "") -> None:
    from datetime import datetime

    async with using_db() as conn:
        await conn.execute(
            "UPDATE credentials SET status = ?, scopes = ?, last_validated_at = ? WHERE id = ?",
            (status, scopes, datetime.utcnow().isoformat(), credential_id),
        )


async def record_usage(credential_id: int, feature: str, provider: str, cost_copper: int = 0) -> None:
    async with using_db() as conn:
        await conn.execute(
            """INSERT INTO credential_usage (credential_id, feature, provider, estimated_cost_copper)
               VALUES (?, ?, ?, ?)""",
            (credential_id, feature, provider, cost_copper),
        )


async def get_usage_stats(credential_id: int) -> dict:
    async with using_db() as conn:
        cursor = await conn.execute(
            """SELECT COUNT(*) as total_uses, COALESCE(SUM(estimated_cost_copper), 0) as total_cost
               FROM credential_usage WHERE credential_id = ?""",
            (credential_id,),
        )
        row = await cursor.fetchone()
    return {"total_uses": row[0] if row else 0, "total_cost_copper": row[1] if row else 0}
