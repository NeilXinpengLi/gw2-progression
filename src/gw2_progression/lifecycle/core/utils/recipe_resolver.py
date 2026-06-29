from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp


@dataclass
class RecipeIngredient:
    item_id: int
    count: int


@dataclass
class RecipeInfo:
    recipe_id: int
    output_item_id: int
    output_count: int = 1
    ingredients: list[RecipeIngredient] = field(default_factory=list)
    discipline: str = ""
    min_rating: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "output_item_id": self.output_item_id,
            "output_count": self.output_count,
            "ingredients": [{"item_id": i.item_id, "count": i.count} for i in self.ingredients],
            "discipline": self.discipline,
            "min_rating": self.min_rating,
        }


class RecipeResolver:
    CACHE_DIR = Path(os.environ.get("RECIPE_CACHE_DIR", "data/recipe_cache"))
    PAGE_SIZE = 200

    def __init__(self) -> None:
        self._cache: dict[int, list[RecipeInfo]] = {}
        self._session: aiohttp.ClientSession | None = None
        self._last_fetch: float = 0
        self._rate_limit_delay = 0.15
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

    async def preheat_all(self) -> dict[str, Any]:
        """Fetch ALL GW2 recipes via pagination, cache each output item."""
        session = await self._get_session()
        start = time.monotonic()

        async with session.get("https://api.guildwars2.com/v2/recipes") as resp:
            if resp.status != 200:
                return {"status": "error", "error": f"HTTP {resp.status}"}
            all_recipe_ids: list[int] = await resp.json()
        self._last_fetch = time.monotonic()

        total = len(all_recipe_ids)
        fetched = 0
        output_items_seen: set[int] = set()

        for page_start in range(0, total, self.PAGE_SIZE):
            chunk = all_recipe_ids[page_start : page_start + self.PAGE_SIZE]
            ids_param = ",".join(str(rid) for rid in chunk)

            delay = max(0, self._rate_limit_delay - (time.monotonic() - self._last_fetch))
            if delay > 0:
                await asyncio.sleep(delay)

            async with session.get(f"https://api.guildwars2.com/v2/recipes?ids={ids_param}") as resp:
                if resp.status == 200:
                    recipes_data = await resp.json()
                else:
                    recipes_data = []
            self._last_fetch = time.monotonic()

            for rd in (recipes_data if isinstance(recipes_data, list) else [recipes_data]):
                if not isinstance(rd, dict):
                    continue
                output_id = rd.get("output_item_id")
                if not output_id:
                    continue
                recipe = RecipeInfo(
                    recipe_id=rd["id"],
                    output_item_id=output_id,
                    output_count=rd.get("output_item_count", 1),
                    ingredients=[
                        RecipeIngredient(item_id=ing["item_id"], count=ing["count"])
                        for ing in rd.get("ingredients", [])
                    ],
                    discipline=rd.get("disciplines", [""])[0] if rd.get("disciplines") else "",
                    min_rating=rd.get("min_rating", 0),
                )
                if output_id not in self._cache:
                    self._cache[output_id] = []
                self._cache[output_id].append(recipe)
                output_items_seen.add(output_id)
                self._save_to_disk(output_id, self._cache[output_id])

            fetched += len(recipes_data)
            pct = fetched / total * 100 if total else 100

            print(f"  Recipe preheat: {fetched}/{total} ({pct:.0f}%) "
                  f"- {len(output_items_seen)} unique output items", end="\r")

        elapsed = time.monotonic() - start
        print()
        return {
            "status": "ok",
            "total_recipes": total,
            "fetched": fetched,
            "unique_output_items": len(output_items_seen),
            "elapsed_seconds": round(elapsed, 1),
        }

    async def find_recipes(self, output_item_id: int) -> list[RecipeInfo]:
        if output_item_id in self._cache:
            return self._cache[output_item_id]

        cached = self._load_from_disk(output_item_id)
        if cached is not None:
            self._cache[output_item_id] = cached
            return cached

        session = await self._get_session()
        delay = max(0, self._rate_limit_delay - (time.monotonic() - self._last_fetch))
        if delay > 0:
            await asyncio.sleep(delay)

        try:
            async with session.get(f"https://api.guildwars2.com/v2/recipes/search?output={output_item_id}") as resp:
                if resp.status != 200:
                    self._cache[output_item_id] = []
                    self._save_to_disk(output_item_id, [])
                    return []
                recipe_ids = await resp.json()
            self._last_fetch = time.monotonic()

            if not recipe_ids:
                self._cache[output_item_id] = []
                self._save_to_disk(output_item_id, [])
                return []

            ids_param = ",".join(str(rid) for rid in recipe_ids[:50])
            delay2 = max(0, self._rate_limit_delay - (time.monotonic() - self._last_fetch))
            if delay2 > 0:
                await asyncio.sleep(delay2)

            async with session.get(f"https://api.guildwars2.com/v2/recipes?ids={ids_param}") as resp:
                if resp.status == 200:
                    recipes_data = await resp.json()
                else:
                    recipes_data = []
            self._last_fetch = time.monotonic()

            recipes = []
            for rd in (recipes_data if isinstance(recipes_data, list) else [recipes_data]):
                recipe = RecipeInfo(
                    recipe_id=rd["id"],
                    output_item_id=rd["output_item_id"],
                    output_count=rd.get("output_item_count", 1),
                    ingredients=[
                        RecipeIngredient(item_id=ing["item_id"], count=ing["count"])
                        for ing in rd.get("ingredients", [])
                    ],
                    discipline=rd.get("disciplines", [""])[0] if rd.get("disciplines") else "",
                    min_rating=rd.get("min_rating", 0),
                )
                recipes.append(recipe)

            self._cache[output_item_id] = recipes
            self._save_to_disk(output_item_id, recipes)
            return recipes

        except Exception:
            self._cache[output_item_id] = []
            return []

    async def find_recipes_batch(self, item_ids: list[int]) -> dict[int, list[RecipeInfo]]:
        results: dict[int, list[RecipeInfo]] = {}
        for iid in item_ids:
            if iid in self._cache:
                results[iid] = self._cache[iid]
            else:
                cached = self._load_from_disk(iid)
                if cached is not None:
                    self._cache[iid] = cached
                    results[iid] = cached

        uncached = [iid for iid in item_ids if iid not in results]
        for iid in uncached:
            recipes = await self.find_recipes(iid)
            results[iid] = recipes

        return results

    def get_recipes(self, output_item_id: int) -> list[RecipeInfo]:
        if output_item_id in self._cache:
            return self._cache[output_item_id]
        cached = self._load_from_disk(output_item_id)
        if cached is not None:
            self._cache[output_item_id] = cached
            return cached
        return []

    def has_recipe(self, output_item_id: int) -> bool:
        return bool(self.get_recipes(output_item_id))

    def get_ingredients(self, output_item_id: int) -> dict[int, int]:
        recipes = self.get_recipes(output_item_id)
        if not recipes:
            return {}
        recipe = recipes[0]
        return {ing.item_id: ing.count for ing in recipe.ingredients}

    def _cache_path(self, item_id: int) -> Path:
        return self.CACHE_DIR / f"{item_id}.json"

    def _save_to_disk(self, item_id: int, recipes: list[RecipeInfo]) -> None:
        try:
            data = [r.to_dict() for r in recipes]
            self._cache_path(item_id).write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass

    def _load_from_disk(self, item_id: int) -> list[RecipeInfo] | None:
        path = self._cache_path(item_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [
                RecipeInfo(
                    recipe_id=r["recipe_id"],
                    output_item_id=r["output_item_id"],
                    output_count=r.get("output_count", 1),
                    ingredients=[RecipeIngredient(**ing) for ing in r.get("ingredients", [])],
                    discipline=r.get("discipline", ""),
                    min_rating=r.get("min_rating", 0),
                )
                for r in data
            ]
        except Exception:
            return None

    def cache_stats(self) -> dict[str, int]:
        return {"in_memory": len(self._cache), "on_disk": len(list(self.CACHE_DIR.glob("*.json")))}


_recipe_instance: RecipeResolver | None = None


def get_recipe_resolver() -> RecipeResolver:
    global _recipe_instance
    if _recipe_instance is None:
        _recipe_instance = RecipeResolver()
    return _recipe_instance
