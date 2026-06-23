"""Product service — define sellable products."""

import json

from gw2_progression.database import using_db

SAMPLE_PRODUCTS = [
    {
        "slug": "account-value-report",
        "name": "Account Value Report",
        "description": "Complete Guild Wars 2 account valuation: total value breakdown by location, top valuable items, wallet, materials, and bank. Includes PDF export.",
        "price_copper": 30000,
        "type": "one_time",
        "deliverables": json.dumps(["PDF Report", "Value Breakdown Chart", "Top Items List", "7-Day Change Delta"], ensure_ascii=False),
    },
    {
        "slug": "legendary-gap-report",
        "name": "Legendary Gap Report",
        "description": "Pick a legendary target and get a complete material gap analysis: what you own, what you need, total cost, and crafting steps.",
        "price_copper": 50000,
        "type": "one_time",
        "deliverables": json.dumps(["PDF Gap Analysis", "Shopping List", "Crafting Steps", "Cost Breakdown"], ensure_ascii=False),
    },
    {
        "slug": "build-readiness-report",
        "name": "Build Readiness Report",
        "description": "See which meta builds you're closest to completing. Equipment gap analysis per build with missing item costs.",
        "price_copper": 50000,
        "type": "one_time",
        "deliverables": json.dumps(["Build Readiness Scores", "Equipment Gap per Build", "Missing Item Costs", "Priority Build Recommendation"], ensure_ascii=False),
    },
    {
        "slug": "weekly-progression",
        "name": "Weekly Progression Subscription",
        "description": "Get a weekly email with your account value changes, goal progress, build updates, and personalized recommendations.",
        "price_copper": 3000,
        "type": "subscription",
        "deliverables": json.dumps(["Weekly Email Report", "Value Delta", "Goal Progress", "Build Updates", "Action Plan"], ensure_ascii=False),
    },
    {
        "slug": "guild-audit",
        "name": "Guild Account Audit",
        "description": "Aggregate all guild member accounts: combined value, profession coverage, build readiness, and growth recommendations.",
        "price_copper": 499000,
        "type": "service",
        "deliverables": json.dumps(["Combined Value Report", "Profession Coverage Matrix", "Member Build Readiness", "Growth Recommendations"], ensure_ascii=False),
    },
]


async def seed_products():
    async with using_db() as conn:
        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM products")
        row = await cursor.fetchone()
        if row and row["cnt"] > 0:
            return
        for p in SAMPLE_PRODUCTS:
            await conn.execute(
                """INSERT INTO products (slug, name, description, price_copper, type, deliverables)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (p["slug"], p["name"], p["description"], p["price_copper"], p["type"], p["deliverables"]),
            )
        await conn.commit()


async def list_products(active_only: bool = True) -> list[dict]:
    rows = []
    async with using_db() as conn:
        if active_only:
            cursor = await conn.execute("SELECT * FROM products WHERE active = 1 ORDER BY price_copper")
        else:
            cursor = await conn.execute("SELECT * FROM products ORDER BY price_copper")
        rows = await cursor.fetchall()
    return [
        {
            "id": r[0],
            "slug": r[1],
            "name": r[2],
            "description": r[3],
            "price_copper": r[4],
            "price_gold": r[4] / 10000,
            "type": r[5],
            "deliverables": json.loads(r[6]) if r[6] else [],
            "sample_url": r[7],
        }
        for r in rows
    ]


async def get_product(product_id: int) -> dict | None:
    async with using_db() as conn:
        cursor = await conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = await cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "slug": row[1],
        "name": row[2],
        "description": row[3],
        "price_copper": row[4],
        "price_gold": row[4] / 10000,
        "type": row[5],
        "deliverables": json.loads(row[6]) if row[6] else [],
        "sample_url": row[7],
    }
