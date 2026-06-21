"""Simple session-based authentication service."""

import secrets
import time

_session_store: dict[str, dict] = {}
SESSION_TTL = 3600  # 1 hour


def create_session(api_key: str, account_name: str) -> str:
    token = secrets.token_hex(24)
    _session_store[token] = {
        "api_key": api_key,
        "account_name": account_name,
        "created_at": time.time(),
    }
    return token


def get_session(token: str) -> dict | None:
    session = _session_store.get(token)
    if not session:
        return None
    if time.time() - session["created_at"] > SESSION_TTL:
        del _session_store[token]
        return None
    return session


def get_api_key(token_or_key: str) -> str | None:
    """Extract API key from a token or return as-is if it looks like a key."""
    if len(token_or_key) >= 40 and not token_or_key.startswith("Bearer "):
        session = get_session(token_or_key)
        if session:
            return session["api_key"]
    return token_or_key


def cleanup_expired():
    now = time.time()
    expired = [t for t, s in _session_store.items() if now - s["created_at"] > SESSION_TTL]
    for t in expired:
        del _session_store[t]
