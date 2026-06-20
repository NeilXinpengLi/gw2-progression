"""Progression goal template system and goal plan generator."""

import logging
import uuid
from datetime import datetime, timezone

from ..database import get_db
from ..models import GoalPlan, GoalRequirement, GoalRequirementStatus, ProgressionGoalTemplate
from .price_service import fetch_prices

logger = logging.getLogger("gw2.progression")


CURATED_TEMPLATES = [
    # 1. Bolt (Legendary Greatsword)
    ProgressionGoalTemplate(
        template_id="leg_greatsword_bolt",
        goal_type="legendary_weapon",
        name="Bolt (Legendary Greatsword)",
        target_item_id=46765,
        expansion="Core",
        category="Weapon",
        difficulty_level="medium",
        estimated_time_class="long",
    ),
    # 2. Twilight (Legendary Greatsword)
    ProgressionGoalTemplate(
        template_id="leg_greatsword_twilight",
        goal_type="legendary_weapon",
        name="Twilight (Legendary Greatsword)",
        target_item_id=30684,
        expansion="Core",
        category="Weapon",
        difficulty_level="medium",
        estimated_time_class="long",
    ),
    # 3. Nevermore (Legendary Staff)
    ProgressionGoalTemplate(
        template_id="leg_staff_nevermore",
        goal_type="legendary_weapon",
        name="Nevermore (Legendary Staff)",
        target_item_id=76158,
        expansion="HoT",
        category="Weapon",
        difficulty_level="hard",
        estimated_time_class="very_long",
    ),
    # 4. Astralaria (Legendary Axe)
    ProgressionGoalTemplate(
        template_id="leg_axe_astralaria",
        goal_type="legendary_weapon",
        name="Astralaria (Legendary Axe)",
        target_item_id=72066,
        expansion="HoT",
        category="Weapon",
        difficulty_level="hard",
        estimated_time_class="very_long",
    ),
    # 5. Ad Infinitum (Legendary Backpack)
    ProgressionGoalTemplate(
        template_id="leg_back_ad_infinitum",
        goal_type="legendary_trinket",
        name="Ad Infinitum (Legendary Backpack)",
        target_item_id=79906,
        expansion="HoT",
        category="Back",
        difficulty_level="hard",
        estimated_time_class="very_long",
    ),
    # 6. Vision (Legendary Ring)
    ProgressionGoalTemplate(
        template_id="leg_ring_vision",
        goal_type="legendary_trinket",
        name="Vision (Legendary Ring)",
        target_item_id=93031,
        expansion="LWS4",
        category="Trinket",
        difficulty_level="hard",
        estimated_time_class="very_long",
    ),
    # 7. Ascended Zojja's Greatsword (Berserker)
    ProgressionGoalTemplate(
        template_id="asc_gs_zojja",
        goal_type="ascended_weapon",
        name="Ascended Zojja's Greatsword (Berserker)",
        target_item_id=46765,
        expansion="Core",
        category="Weapon",
        difficulty_level="easy",
        estimated_time_class="medium",
    ),
    # 8. Ascended Heavy Armor Set (Berserker)
    ProgressionGoalTemplate(
        template_id="asc_heavy_berserker",
        goal_type="ascended_armor",
        name="Ascended Heavy Armor Set (Berserker)",
        target_item_id=0,
        expansion="Core",
        category="Armor",
        difficulty_level="medium",
        estimated_time_class="long",
    ),
]

CURATED_REQUIREMENTS = [
    # Bolt requirements
    GoalRequirement(
        requirement_id="bolt_gift",
        template_id="leg_greatsword_bolt",
        requirement_type="item",
        ref_id=19684,
        ref_name="Gift of Bolt",
        required_count=1,
        notes="Gift of Bolt combines Gift of Metal + Gift of Energy + Gift of Lightning + 100 Crystalline Ore",
    ),
    GoalRequirement(requirement_id="bolt_gift_metal", template_id="leg_greatsword_bolt", requirement_type="item", ref_id=19682, ref_name="Gift of Metal", required_count=1),
    GoalRequirement(requirement_id="bolt_gift_energy", template_id="leg_greatsword_bolt", requirement_type="item", ref_id=19683, ref_name="Gift of Energy", required_count=1),
    GoalRequirement(requirement_id="bolt_gift_lightning", template_id="leg_greatsword_bolt", requirement_type="item", ref_id=19685, ref_name="Gift of Lightning", required_count=1),
    GoalRequirement(requirement_id="bolt_gift_mastery", template_id="leg_greatsword_bolt", requirement_type="item", ref_id=19680, ref_name="Gift of Mastery", required_count=1),
    GoalRequirement(requirement_id="bolt_gift_might", template_id="leg_greatsword_bolt", requirement_type="item", ref_id=19679, ref_name="Gift of Might", required_count=1),
    GoalRequirement(requirement_id="bolt_gift_magic", template_id="leg_greatsword_bolt", requirement_type="item", ref_id=19676, ref_name="Gift of Magic", required_count=1),
    GoalRequirement(requirement_id="bolt_mystic_coin", template_id="leg_greatsword_bolt", requirement_type="item", ref_id=19976, ref_name="Mystic Coin", required_count=100, time_gated=True),
    GoalRequirement(requirement_id="bolt_gold", template_id="leg_greatsword_bolt", requirement_type="currency", ref_id=1, ref_name="Gold", required_count=500),
    GoalRequirement(
        requirement_id="bolt_skill",
        template_id="leg_greatsword_bolt",
        requirement_type="achievement",
        ref_id=0,
        ref_name="The Legendary Bolt achievement completed",
        required_count=1,
        notes="Requires crafting collection steps",
    ),
]


_template_cache: dict[str, ProgressionGoalTemplate] = {}


async def get_templates() -> list[ProgressionGoalTemplate]:
    try:
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM progression_goal_templates WHERE enabled = 1 ORDER BY goal_type, name")
            rows = await cursor.fetchall()
            if rows:
                return [ProgressionGoalTemplate(**dict(r)) for r in rows]
        finally:
            await db.close()
    except Exception:
        logger.warning("DB unavailable for templates, using curated")
    return CURATED_TEMPLATES


async def get_requirements(template_id: str) -> list[GoalRequirement]:
    try:
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM goal_requirements WHERE template_id = ?", (template_id,))
            rows = await cursor.fetchall()
            if rows:
                return [GoalRequirement(**dict(r)) for r in rows]
        finally:
            await db.close()
    except Exception:
        logger.warning("DB unavailable for requirements, using curated")
    return [r for r in CURATED_REQUIREMENTS if r.template_id == template_id]


async def seed_templates():
    """Insert curated templates into the database if empty."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM progression_goal_templates")
        row = await cursor.fetchone()
        if row and row["cnt"] > 0:
            return
        for t in CURATED_TEMPLATES:
            await db.execute(
                """INSERT INTO progression_goal_templates
                (template_id, goal_type, name, target_item_id, expansion, category, difficulty_level, estimated_time_class)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (t.template_id, t.goal_type, t.name, t.target_item_id, t.expansion, t.category, t.difficulty_level, t.estimated_time_class),
            )
        for r in CURATED_REQUIREMENTS:
            await db.execute(
                """INSERT INTO goal_requirements
                (requirement_id, template_id, requirement_type, ref_id, ref_name, required_count, time_gated, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (r.requirement_id, r.template_id, r.requirement_type, r.ref_id, r.ref_name, r.required_count, 1 if r.time_gated else 0, r.notes),
            )
        await db.commit()
        logger.info("Seeded %d templates and %d requirements", len(CURATED_TEMPLATES), len(CURATED_REQUIREMENTS))
    finally:
        await db.close()


async def generate_goal_plan(api_key: str, template_id: str) -> GoalPlan:
    from ..analyzer import fetch_all

    contents = await fetch_all(api_key)
    account_name = contents.account_name or "unknown"
    template = next((t for t in CURATED_TEMPLATES if t.template_id == template_id), None)
    if not template:
        raise ValueError(f"Template {template_id} not found")

    requirements = await get_requirements(template_id)

    # Build owned item map
    owned_counts: dict[int, int] = {}
    for h in contents.materials or []:
        if isinstance(h, dict):
            owned_counts[h["id"]] = owned_counts.get(h["id"], 0) + h.get("count", 0)
    for h in contents.bank or []:
        if isinstance(h, dict) and h.get("id"):
            owned_counts[h["id"]] = owned_counts.get(h["id"], 0) + h.get("count", 1)

    # Wallet gold
    wallet_gold = 0
    for w in contents.wallet or []:
        if w.get("id") == 1:
            wallet_gold = w.get("value", 0)

    # Fetch prices for item requirements
    item_ids = [r.ref_id for r in requirements if r.requirement_type == "item" and r.ref_id > 0]
    prices_raw = await fetch_prices(item_ids)
    prices = {iid: pd.sell_unit_price for iid, pd in prices_raw.items()}

    statuses: list[GoalRequirementStatus] = []
    total_owned_value = 0
    total_missing_cost = 0
    time_gated_count = 0
    blocked_count = 0

    for req in requirements:
        owned = 0
        if req.requirement_type == "item":
            owned = owned_counts.get(req.ref_id, 0)
        elif req.requirement_type == "currency" and req.ref_id == 1:
            owned = wallet_gold

        missing = max(0, req.required_count - owned)
        unit_price = prices.get(req.ref_id, 0)
        cost = missing * unit_price if req.requirement_type == "item" else 0
        pct = round(owned / req.required_count * 100, 1) if req.required_count > 0 else 0.0

        if owned >= req.required_count:
            st = "complete"
        elif owned > 0:
            st = "partial"
        elif req.requirement_type == "achievement":
            st = "blocked"
            blocked_count += 1
        else:
            st = "missing"

        if req.time_gated and st != "complete":
            time_gated_count += 1

        total_owned_value += owned * unit_price
        total_missing_cost += cost

        statuses.append(
            GoalRequirementStatus(
                requirement_id=req.requirement_id,
                template_id=req.template_id,
                requirement_type=req.requirement_type,
                ref_id=req.ref_id,
                ref_name=req.ref_name,
                required_count=req.required_count,
                owned_count=owned,
                missing_count=missing,
                completion_percent=pct,
                estimated_cost_buy=cost,
                status=st,
            )
        )

    total_pct = round(sum(s.completion_percent for s in statuses) / len(statuses), 1) if statuses else 0.0
    now = datetime.now(timezone.utc).isoformat()

    return GoalPlan(
        goal_id=uuid.uuid4().hex[:12],
        account_name=account_name,
        template_id=template_id,
        target_count=1,
        total_completion_percent=total_pct,
        total_missing_cost=total_missing_cost,
        total_owned_material_value=total_owned_value,
        time_gated_count=time_gated_count,
        blocked_requirement_count=blocked_count,
        requirements=statuses,
        created_at=now,
        updated_at=now,
    )
