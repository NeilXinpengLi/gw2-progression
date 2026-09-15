"""MemoryGraph — simple in-memory KV store with optional TTL."""

import time
from typing import Any

_store: dict[str, dict] = {}


def store(key: str, value: Any, ttl: float = 0) -> None:
    """Store a value with optional TTL in seconds (0 = no expiry)."""
    expires_at = time.time() + ttl if ttl > 0 else 0
    _store[key] = {"value": value, "expires_at": expires_at}


def get(key: str) -> Any | None:
    """Get a value, returning None if expired or not found."""
    entry = _store.get(key)
    if entry is None:
        return None
    if entry["expires_at"] > 0 and time.time() > entry["expires_at"]:
        del _store[key]
        return None
    return entry["value"]


def delete(key: str) -> bool:
    if key in _store:
        del _store[key]
        return True
    return False


def clear() -> None:
    _store.clear()


def stats() -> dict:
    now = time.time()
    active = sum(1 for e in _store.values() if e["expires_at"] == 0 or now < e["expires_at"])
    return {"total_keys": len(_store), "active_keys": active}
