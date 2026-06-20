"""Fetch and store static data from GW2 API: items and recipes."""

import json
import logging
from datetime import datetime, timezone

import httpx

from ..database import get_db

logger = logging.getLogger("gw2.static")

GW2_BASE = "https://api.guildwars2.com"
CHUNK_SIZE = 200


async def _fetch_json(path: str) -> list | dict | None:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{GW2_BASE}{path}")
    if not resp.is_success:
        logger.warning("Static data fetch failed: HTTP %d %s", resp.status_code, path)
        return None
    return resp.json()


async def refresh_items(max_pages: int = 0):
    """Fetch all items from /v2/items (paginated) and store in static_items table."""
    logger.info("Starting item refresh...")
    db = await get_db()
    try:
        count = 0
        page = 0
        while True:
            data = await _fetch_json(f"/v2/items?page={page}&page_size={CHUNK_SIZE}")
            if not data or not isinstance(data, list) or len(data) == 0:
                break
            now = datetime.now(timezone.utc).isoformat()
            for item in data:
                item_id = item.get("id")
                if not item_id:
                    continue
                flags = item.get("flags", [])
                game_types = item.get("game_types", [])
                restrictions = item.get("restrictions", [])
                await db.execute(
                    """INSERT OR REPLACE INTO static_items
                    (id, name, icon, description, type, rarity, level, vendor_value, flags, game_types, restrictions, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item_id,
                        item.get("name", ""),
                        item.get("icon", ""),
                        item.get("description", ""),
                        item.get("type", ""),
                        item.get("rarity", ""),
                        item.get("level", 0),
                        item.get("vendor_value", 0),
                        json.dumps(flags),
                        json.dumps(game_types),
                        json.dumps(restrictions),
                        now,
                    ),
                )
                count += 1
            page += 1
            if max_pages and page >= max_pages:
                break
        await db.commit()
        logger.info("Item refresh complete: %d items stored", count)
    finally:
        await db.close()
    return count


async def refresh_recipes(max_pages: int = 0):
    """Fetch all recipes from /v2/recipes and store in static_recipes + recipe_ingredients."""
    logger.info("Starting recipe refresh...")
    db = await get_db()
    try:
        # Clear existing data
        await db.execute("DELETE FROM recipe_ingredients")
        await db.execute("DELETE FROM static_recipes")

        count = 0
        page = 0
        while True:
            data = await _fetch_json(f"/v2/recipes?page={page}&page_size={CHUNK_SIZE}")
            if not data or not isinstance(data, list) or len(data) == 0:
                break
            now = datetime.now(timezone.utc).isoformat()
            for recipe in data:
                recipe_id = recipe.get("id")
                if not recipe_id:
                    continue
                await db.execute(
                    """INSERT INTO static_recipes
                    (id, output_item_id, output_item_count, disciplines, min_rating, flags, type, chat_link, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        recipe_id,
                        recipe.get("output_item_id", 0),
                        recipe.get("output_item_count", 1),
                        json.dumps(recipe.get("disciplines", [])),
                        recipe.get("min_rating", 0),
                        json.dumps(recipe.get("flags", [])),
                        recipe.get("type", ""),
                        recipe.get("chat_link", ""),
                        now,
                    ),
                )
                for ing in recipe.get("ingredients", []):
                    await db.execute(
                        "INSERT INTO recipe_ingredients (recipe_id, item_id, count) VALUES (?, ?, ?)",
                        (recipe_id, ing.get("item_id", 0), ing.get("count", 1)),
                    )
                count += 1
            page += 1
            if max_pages and page >= max_pages:
                break
        await db.commit()
        logger.info("Recipe refresh complete: %d recipes stored", count)
    finally:
        await db.close()
    return count


async def find_recipes_by_output(output_item_id: int) -> list[dict]:
    """Look up recipes that produce a given item, from the static store."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, output_item_id, output_item_count, disciplines, min_rating, flags, type FROM static_recipes WHERE output_item_id = ?",
            (output_item_id,),
        )
        recipes = await cursor.fetchall()
        result = []
        for r in recipes:
            ing_cursor = await db.execute(
                "SELECT item_id, count FROM recipe_ingredients WHERE recipe_id = ?",
                (r["id"],),
            )
            ingredients = await ing_cursor.fetchall()
            result.append(
                {
                    "id": r["id"],
                    "output_item_id": r["output_item_id"],
                    "output_item_count": r["output_item_count"],
                    "disciplines": json.loads(r["disciplines"]) if r["disciplines"] else [],
                    "min_rating": r["min_rating"],
                    "flags": json.loads(r["flags"]) if r["flags"] else [],
                    "type": r["type"],
                    "ingredients": [{"item_id": i["item_id"], "count": i["count"]} for i in ingredients],
                }
            )
        return result
    finally:
        await db.close()
