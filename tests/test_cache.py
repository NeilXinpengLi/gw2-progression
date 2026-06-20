import time

import pytest

from gw2_progression.cache import TTLCache, cached, get_cache


def test_set_and_get():
    c = TTLCache(ttl=60)
    c.set("foo", 42)
    assert c.get("foo") == 42


def test_expiry():
    c = TTLCache(ttl=0.05)
    c.set("foo", 42)
    assert c.get("foo") == 42
    time.sleep(0.1)
    assert c.get("foo") is None


def test_maxsize():
    c = TTLCache(ttl=60, maxsize=2)
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3)
    assert c.size <= 2
    assert c.get("a") is None


def test_clear():
    c = TTLCache(ttl=60)
    c.set("foo", 42)
    c.clear()
    assert c.get("foo") is None


def test_singleton():
    c1 = get_cache()
    c2 = get_cache()
    assert c1 is c2


@pytest.mark.asyncio
async def test_cached_decorator():
    call_count = 0

    @cached(ttl=60)
    async def fetch_something(key: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"result-{key}"

    r1 = await fetch_something("a")
    r2 = await fetch_something("a")
    assert r1 == r2 == "result-a"
    assert call_count == 1

    r3 = await fetch_something("b")
    assert r3 == "result-b"
    assert call_count == 2
