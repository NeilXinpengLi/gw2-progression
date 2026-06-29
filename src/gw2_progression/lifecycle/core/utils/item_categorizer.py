from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

ITEM_CATEGORY = {
    "Weapon": "equipment",
    "Armor": "equipment",
    "Trinket": "equipment",
    "Back": "equipment",
    "CraftingMaterial": "material",
    "Trophy": "material",
    "Consumable": "consumable",
    "Food": "consumable",
    "Utility": "consumable",
    "Gathering": "tool",
    "Tool": "tool",
    "Bag": "container",
    "Container": "container",
    "Gizmo": "special",
    "MiniPet": "cosmetic",
    "Skin": "cosmetic",
    "UpgradeComponent": "upgrade",
    "JadeTechModule": "upgrade",
    "PowerCore": "upgrade",
}

ITEM_RARITY = {
    "Basic": 1,
    "Fine": 2,
    "Masterwork": 3,
    "Rare": 4,
    "Exotic": 5,
    "Ascended": 6,
    "Legendary": 7,
}


@dataclass
class ItemInfo:
    id: int
    name: str
    api_type: str
    category: str
    rarity: str
    level: int
    sub_type: str = ""
    vendor_value: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "api_type": self.api_type,
            "category": self.category,
            "rarity": self.rarity,
            "level": self.level,
            "sub_type": self.sub_type,
            "vendor_value": self.vendor_value,
        }


class ItemCategorizer:
    CACHE_DIR = Path(os.environ.get("ITEM_CACHE_DIR", "data/item_cache"))
    CACHE_TTL = 86400 * 7

    def __init__(self) -> None:
        self._cache: dict[int, ItemInfo] = {}
        self._pending_ids: set[int] = set()
        self._last_fetch: float = 0
        self._rate_limit_delay = 0.25
        self._session: aiohttp.ClientSession | None = None
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def close_sync(self) -> None:
        if self._session and not self._session.closed:
            try:
                asyncio.run(self._session.close())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._session.close())
                loop.close()

    async def fetch_item(self, item_id: int) -> ItemInfo | None:
        if item_id in self._cache:
            return self._cache[item_id]

        cached = self._load_from_disk(item_id)
        if cached is not None:
            self._cache[item_id] = cached
            return cached

        session = await self._get_session()
        now = time.monotonic()
        delay = max(0, self._rate_limit_delay - (now - self._last_fetch))
        if delay > 0:
            await asyncio.sleep(delay)

        try:
            async with session.get(f"https://api.guildwars2.com/v2/items/{item_id}") as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
            self._last_fetch = time.monotonic()
            info = self._parse_item(data)
            self._save_to_disk(info)
            self._cache[item_id] = info
            return info
        except Exception:
            return None

    async def fetch_batch(self, item_ids: list[int]) -> dict[int, ItemInfo]:
        uncached = [iid for iid in item_ids if iid not in self._cache and self._load_from_disk(iid) is None]
        preloaded = {iid: self._cache[iid] for iid in item_ids if iid in self._cache}
        disk_loaded = {}
        for iid in item_ids:
            if iid not in preloaded:
                cached = self._load_from_disk(iid)
                if cached is not None:
                    disk_loaded[iid] = cached
                    self._cache[iid] = cached

        if not uncached:
            return {**preloaded, **disk_loaded}

        chunk_size = 200
        session = await self._get_session()
        for i in range(0, len(uncached), chunk_size):
            chunk = uncached[i : i + chunk_size]
            now = time.monotonic()
            delay = max(0, self._rate_limit_delay - (now - self._last_fetch))
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                ids_str = ",".join(str(iid) for iid in chunk)
                async with session.get(f"https://api.guildwars2.com/v2/items?ids={ids_str}") as resp:
                    if resp.status == 200:
                        items_data = await resp.json()
                        for item_data in items_data:
                            info = self._parse_item(item_data)
                            self._save_to_disk(info)
                            self._cache[info.id] = info
                self._last_fetch = time.monotonic()
            except Exception:
                pass

        return {iid: self._cache.get(iid) for iid in item_ids if iid in self._cache}

    def categorize(self, item_id: int) -> str | None:
        info = self._cache.get(item_id)
        if info is None:
            cached = self._load_from_disk(item_id)
            if cached is not None:
                self._cache[item_id] = cached
                info = cached
        return info.category if info else None

    def get_info(self, item_id: int) -> ItemInfo | None:
        return self._cache.get(item_id) or self._load_from_disk(item_id)

    def classify_items(self, item_ids: list[int]) -> dict[str, list[int]]:
        classified: dict[str, list[int]] = {}
        for iid in item_ids:
            info = self._cache.get(iid)
            cat = info.category if info else None
            if cat is None:
                cat = "unknown"
            classified.setdefault(cat, []).append(iid)
        return classified

    def _parse_item(self, data: dict) -> ItemInfo:
        api_type = data.get("type", "Unknown")
        category = ITEM_CATEGORY.get(api_type, "other")
        details = data.get("details", {}) or {}
        sub_type = ""
        if isinstance(details, dict):
            sub_type = details.get("type", "")
            if not sub_type:
                sub_type = details.get("damage_type", "")

        return ItemInfo(
            id=data["id"],
            name=data.get("name", f"Item_{data['id']}"),
            api_type=api_type,
            category=category,
            rarity=data.get("rarity", "Basic"),
            level=data.get("level", 0),
            sub_type=sub_type,
            vendor_value=data.get("vendor_value", 0),
        )

    def _cache_path(self, item_id: int) -> Path:
        return self.CACHE_DIR / f"{item_id}.json"

    def _save_to_disk(self, info: ItemInfo) -> None:
        try:
            path = self._cache_path(info.id)
            path.write_text(json.dumps(info.to_dict()), encoding="utf-8")
        except Exception:
            pass

    def _load_from_disk(self, item_id: int) -> ItemInfo | None:
        path = self._cache_path(item_id)
        if not path.exists():
            return None
        try:
            age = time.time() - path.stat().st_mtime
            if age > self.CACHE_TTL:
                path.unlink(missing_ok=True)
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            return ItemInfo(**data)
        except Exception:
            return None

    def cache_stats(self) -> dict[str, int]:
        return {"in_memory": len(self._cache), "on_disk": len(list(self.CACHE_DIR.glob("*.json")))}


_category_instance: ItemCategorizer | None = None


def get_categorizer() -> ItemCategorizer:
    global _category_instance
    if _category_instance is None:
        _category_instance = ItemCategorizer()
    return _category_instance
