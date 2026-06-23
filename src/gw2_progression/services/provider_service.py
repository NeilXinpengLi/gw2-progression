"""Provider service — define and seed external API providers."""

from gw2_progression.database import using_db

SEED_PROVIDERS = [
    {"id": "gw2", "category": "game", "name": "Guild Wars 2 API", "auth_type": "api_key",
     "capabilities": '["account","characters","wallet","inventories","progression","builds","tradingpost","unlocks","pvp","wvw"]',
     "cost_model": "free"},
    {"id": "openai", "category": "llm", "name": "OpenAI", "auth_type": "api_key", "capabilities": '["chat","completion","embedding"]', "cost_model": "token_based"},
    {"id": "anthropic", "category": "llm", "name": "Anthropic Claude", "auth_type": "api_key", "capabilities": '["chat","completion"]', "cost_model": "token_based"},
    {"id": "deepseek", "category": "llm", "name": "DeepSeek", "auth_type": "api_key", "capabilities": '["chat","completion"]', "cost_model": "token_based"},
    {"id": "gemini", "category": "llm", "name": "Google Gemini", "auth_type": "api_key", "capabilities": '["chat","completion"]', "cost_model": "token_based"},
    {"id": "ollama", "category": "llm", "name": "Ollama (Local)", "auth_type": "endpoint", "capabilities": '["chat","completion"]', "cost_model": "free"},
]

SCOPE_EXPLANATIONS = {
    "account": "Account name, world, WvW rank, guild membership",
    "characters": "Characters, equipment, bags, crafting disciplines",
    "wallet": "Gold, karma, and other currencies",
    "inventories": "Bank, material storage, shared inventory slots",
    "progression": "Achievements, masteries, mastery points",
    "builds": "Saved build templates and equipment templates",
    "tradingpost": "Current buy/sell orders on the Trading Post",
    "unlocks": "Unlocked skins, dyes, minis, finishers",
    "pvp": "PvP stats, rank, match history, standings",
    "wvw": "WvW stats, rank, ability points",
}


async def seed_providers():
    async with using_db() as conn:
        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM providers")
        row = await cursor.fetchone()
        if row and row["cnt"] > 0:
            return
        for p in SEED_PROVIDERS:
            await conn.execute(
                "INSERT INTO providers (id, category, name, auth_type, capabilities, cost_model) VALUES (?, ?, ?, ?, ?, ?)",
                (p["id"], p["category"], p["name"], p["auth_type"], p["capabilities"], p["cost_model"]),
            )
        await conn.commit()


async def list_providers(category: str | None = None) -> list[dict]:
    rows = []
    async with using_db() as conn:
        if category:
            cursor = await conn.execute("SELECT * FROM providers WHERE category = ? AND enabled = 1 ORDER BY id", (category,))
        else:
            cursor = await conn.execute("SELECT * FROM providers WHERE enabled = 1 ORDER BY category, id")
        rows = await cursor.fetchall()
    return [
        {
            "id": r[0],
            "category": r[1],
            "name": r[2],
            "auth_type": r[3],
            "capabilities": r[4].split(",") if isinstance(r[4], str) else [],
            "cost_model": r[5],
        }
        for r in rows
    ]


async def get_scope_explanations() -> dict:
    return SCOPE_EXPLANATIONS
