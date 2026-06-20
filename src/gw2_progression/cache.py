import time
from collections import OrderedDict
from typing import Any, Callable, Optional


class TTLCache:
    """Simple TTL-based cache with max size eviction."""

    def __init__(self, ttl: float = 3600, maxsize: int = 512):
        self._ttl = ttl
        self._maxsize = maxsize
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None
        expires, value = self._store[key]
        if time.monotonic() > expires:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic() + self._ttl, value)
        self._store.move_to_end(key)
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        now = time.monotonic()
        expired = [k for k, (e, _) in self._store.items() if now > e]
        for k in expired:
            del self._store[k]
        return len(self._store)


_instance: Optional[TTLCache] = None


def get_cache(ttl: float = 3600, maxsize: int = 512) -> TTLCache:
    global _instance
    if _instance is None:
        _instance = TTLCache(ttl=ttl, maxsize=maxsize)
    return _instance


def cached(ttl: float = 3600, maxsize: int = 512):
    """Decorator: caches async function results by first positional arg."""

    def decorator(fn: Callable) -> Callable:
        local_cache = TTLCache(ttl=ttl, maxsize=maxsize)

        async def wrapper(key: str, *args, **kwargs):
            cached = local_cache.get(key)
            if cached is not None:
                return cached
            result = await fn(key, *args, **kwargs)
            local_cache.set(key, result)
            return result

        wrapper.cache = local_cache
        return wrapper

    return decorator
