import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from .models import ItemHolding, ValueHistoryEntry, ValueSummary

logger = logging.getLogger("gw2.db")

DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DB_DIR / "gw2_progression.db"
DB_POOL_SIZE = 20
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")  # e.g. "file::memory:?cache=shared"

_pool: asyncio.Queue[aiosqlite.Connection] | None = None


def _ensure_db_dir():
    DB_DIR.mkdir(parents=True, exist_ok=True)


async def _create_connection() -> aiosqlite.Connection:
    db_url = _TEST_DB_URL or str(DB_PATH)
    conn = await aiosqlite.connect(db_url)
    conn.row_factory = aiosqlite.Row
    if not _TEST_DB_URL:
        await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.execute("PRAGMA synchronous=NORMAL")
    return conn


async def get_db(timeout: float = 30.0) -> aiosqlite.Connection:
    global _pool
    if _pool is None:
        _pool = asyncio.Queue(DB_POOL_SIZE)
        for _ in range(DB_POOL_SIZE):
            conn = await _create_connection()
            await _pool.put(conn)
    try:
        return await asyncio.wait_for(_pool.get(), timeout=timeout)
    except asyncio.TimeoutError:
        raise RuntimeError(f"DB pool exhausted: all {DB_POOL_SIZE} connections in use for >{timeout}s")


async def release_db(conn: aiosqlite.Connection):
    global _pool
    if _pool is not None and conn is not None:
        await _pool.put(conn)


async def close_pool():
    global _pool
    if _pool is not None:
        while not _pool.empty():
            try:
                conn = _pool.get_nowait()
                await conn.close()
            except asyncio.QueueEmpty:
                break
        _pool = None


@asynccontextmanager
async def using_db():
    """Async context manager that acquires and releases a DB connection.

    Automatically detects stale connections (closed by pool timeout during
    long-running operations) and replaces them with a fresh connection.
    """
    conn = await get_db()
    try:
        # Health check: verify connection is still alive
        try:
            c = await conn.execute("SELECT 1")
            await c.fetchone()
        except Exception:
            # Connection is stale — replace it
            try:
                await conn.close()
            except Exception:
                pass
            conn = await _create_connection()
        yield conn
        await conn.commit()
    except Exception:
        try:
            await conn.rollback()
        except Exception:
            pass
        raise
    finally:
        await release_db(conn)


CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS price_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    buy_unit_price INTEGER NOT NULL DEFAULT 0,
    buy_quantity INTEGER NOT NULL DEFAULT 0,
    sell_unit_price INTEGER NOT NULL DEFAULT 0,
    sell_quantity INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL,
    api_key_hash TEXT,
    total_value_buy INTEGER NOT NULL DEFAULT 0,
    total_value_sell INTEGER NOT NULL DEFAULT 0,
    net_sell_value INTEGER NOT NULL DEFAULT 0,
    wallet_value INTEGER NOT NULL DEFAULT 0,
    material_value_buy INTEGER NOT NULL DEFAULT 0,
    material_value_sell INTEGER NOT NULL DEFAULT 0,
    bank_value_buy INTEGER NOT NULL DEFAULT 0,
    bank_value_sell INTEGER NOT NULL DEFAULT 0,
    character_inventory_value_buy INTEGER NOT NULL DEFAULT 0,
    character_inventory_value_sell INTEGER NOT NULL DEFAULT 0,
    shared_inventory_value_buy INTEGER NOT NULL DEFAULT 0,
    shared_inventory_value_sell INTEGER NOT NULL DEFAULT 0,
    tradingpost_value INTEGER NOT NULL DEFAULT 0,
    priced_item_count INTEGER NOT NULL DEFAULT 0,
    unpriced_item_count INTEGER NOT NULL DEFAULT 0,
    account_bound_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS item_holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    location_type TEXT NOT NULL,
    location_ref TEXT,
    binding_status TEXT,
    tradable INTEGER NOT NULL DEFAULT 1,
    vendor_value INTEGER NOT NULL DEFAULT 0,
    price_buy INTEGER NOT NULL DEFAULT 0,
    price_sell INTEGER NOT NULL DEFAULT 0,
    value_buy INTEGER NOT NULL DEFAULT 0,
    value_sell INTEGER NOT NULL DEFAULT 0,
    valuation_status TEXT NOT NULL DEFAULT 'pending',
    quality_status TEXT NOT NULL DEFAULT 'unknown',
    liquidity_score TEXT NOT NULL DEFAULT 'unknown',
    liquidity_reason TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0,
    data_sources TEXT NOT NULL DEFAULT '[]',
    price_timestamp TEXT NOT NULL DEFAULT '',
    risk_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (snapshot_id) REFERENCES account_snapshots(id)
);

CREATE TABLE IF NOT EXISTS account_sessions (
    token TEXT PRIMARY KEY,
    api_key TEXT NOT NULL,
    account_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_used_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS protected_assets (
    account_name TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    protected_count INTEGER DEFAULT 1,
    reason TEXT DEFAULT 'manual_lock',
    linked_goal_id TEXT DEFAULT '',
    PRIMARY KEY (account_name, item_id)
);

CREATE TABLE IF NOT EXISTS progression_goal_templates (
    template_id TEXT PRIMARY KEY,
    goal_type TEXT NOT NULL,
    name TEXT NOT NULL,
    target_item_id INTEGER NOT NULL DEFAULT 0,
    expansion TEXT DEFAULT '',
    category TEXT DEFAULT '',
    difficulty_level TEXT DEFAULT 'medium',
    estimated_time_class TEXT DEFAULT 'long',
    enabled INTEGER NOT NULL DEFAULT 1,
    source_url TEXT DEFAULT '',
    patch_version TEXT DEFAULT '',
    review_status TEXT DEFAULT 'unreviewed',
    deprecated INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS goal_requirements (
    requirement_id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    requirement_type TEXT NOT NULL,
    ref_id INTEGER NOT NULL DEFAULT 0,
    ref_name TEXT DEFAULT '',
    required_count INTEGER NOT NULL DEFAULT 1,
    time_gated INTEGER NOT NULL DEFAULT 0,
    optional_group_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    FOREIGN KEY (template_id) REFERENCES progression_goal_templates(template_id)
);

CREATE TABLE IF NOT EXISTS tracked_goals (
    goal_id TEXT PRIMARY KEY,
    account_name TEXT NOT NULL,
    target_item_id INTEGER NOT NULL,
    target_count INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    priority TEXT NOT NULL DEFAULT 'normal',
    completion_percent REAL NOT NULL DEFAULT 0.0,
    owned_material_value INTEGER NOT NULL DEFAULT 0,
    missing_material_value INTEGER NOT NULL DEFAULT 0,
    missing_item_count INTEGER NOT NULL DEFAULT 0,
    estimated_remaining_cost INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_value_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL,
    snapshot_time TEXT NOT NULL,
    total_value_buy INTEGER NOT NULL DEFAULT 0,
    total_value_sell INTEGER NOT NULL DEFAULT 0,
    wallet_value INTEGER NOT NULL DEFAULT 0,
    material_value INTEGER NOT NULL DEFAULT 0,
    bank_value INTEGER NOT NULL DEFAULT 0,
    inventory_value INTEGER NOT NULL DEFAULT 0,
    tradingpost_value INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS static_items (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    icon TEXT,
    description TEXT,
    type TEXT,
    rarity TEXT,
    level INTEGER DEFAULT 0,
    vendor_value INTEGER DEFAULT 0,
    flags TEXT,
    game_types TEXT,
    restrictions TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS static_recipes (
    id INTEGER PRIMARY KEY,
    output_item_id INTEGER NOT NULL,
    output_item_count INTEGER DEFAULT 1,
    disciplines TEXT,
    min_rating INTEGER DEFAULT 0,
    flags TEXT,
    type TEXT,
    chat_link TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (recipe_id) REFERENCES static_recipes(id)
);

CREATE TABLE IF NOT EXISTS valuation_warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    warning_type TEXT NOT NULL,
    message TEXT NOT NULL,
    item_id INTEGER,
    FOREIGN KEY (snapshot_id) REFERENCES account_snapshots(id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL,
    report_type TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    total_value_buy INTEGER NOT NULL DEFAULT 0,
    total_value_sell INTEGER NOT NULL DEFAULT 0,
    wallet_gold INTEGER NOT NULL DEFAULT 0,
    character_count INTEGER NOT NULL DEFAULT 0,
    goal_count INTEGER NOT NULL DEFAULT 0,
    goal_progress_pct REAL NOT NULL DEFAULT 0.0,
    build_readiness_pct REAL NOT NULL DEFAULT 0.0,
    top_items TEXT NOT NULL DEFAULT '[]',
    goal_details TEXT NOT NULL DEFAULT '[]',
    build_details TEXT NOT NULL DEFAULT '[]',
    recommendations TEXT NOT NULL DEFAULT '[]',
    snapshot_time TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    auth_type TEXT NOT NULL DEFAULT 'api_key',
    capabilities TEXT NOT NULL DEFAULT '[]',
    cost_model TEXT NOT NULL DEFAULT 'free',
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    encrypted_value TEXT NOT NULL,
    fingerprint TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'unknown',
    scopes TEXT DEFAULT '',
    session_token TEXT,
    last_used_at TEXT,
    last_validated_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS credential_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    credential_id INTEGER NOT NULL,
    feature TEXT NOT NULL,
    provider TEXT NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 1,
    estimated_cost_copper INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'success',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (credential_id) REFERENCES credentials(id)
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    report_type TEXT NOT NULL DEFAULT 'weekly',
    active INTEGER NOT NULL DEFAULT 1,
    last_delivered_at TEXT,
    next_delivery_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS guild_workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    invite_code TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS guild_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    account_name TEXT NOT NULL,
    api_key_hash TEXT,
    role TEXT NOT NULL DEFAULT 'member',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (guild_id) REFERENCES guild_workspaces(id)
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price_copper INTEGER NOT NULL DEFAULT 0,
    type TEXT NOT NULL DEFAULT 'one_time',
    deliverables TEXT NOT NULL DEFAULT '[]',
    sample_url TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    customer_email TEXT NOT NULL,
    customer_name TEXT DEFAULT '',
    amount_copper INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    license_key TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS order_idempotency_keys (
    idempotency_key TEXT PRIMARY KEY,
    order_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'fulfilled',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    fulfilled_at TEXT,
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS payment_events (
    provider_event_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL DEFAULT 'stripe',
    event_type TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'received',
    idempotency_key TEXT NOT NULL DEFAULT '',
    order_id INTEGER,
    customer_email TEXT NOT NULL DEFAULT '',
    product_id INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    fulfilled_at TEXT,
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS licenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT NOT NULL UNIQUE,
    product_id INTEGER NOT NULL,
    order_id INTEGER,
    feature_flags TEXT NOT NULL DEFAULT '{}',
    max_uses INTEGER NOT NULL DEFAULT 0,
    used_count INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS delivery_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL UNIQUE,
    product_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    output_pdf_url TEXT DEFAULT '',
    output_csv_url TEXT DEFAULT '',
    dashboard_url TEXT DEFAULT '',
    error TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS delivery_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_job_id INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'email_report',
    recipient_email TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    sent_at TEXT,
    FOREIGN KEY (delivery_job_id) REFERENCES delivery_jobs(id),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    UNIQUE(delivery_job_id, event_type)
);

CREATE TABLE IF NOT EXISTS affiliates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    referral_code TEXT NOT NULL UNIQUE,
    commission_rate REAL NOT NULL DEFAULT 0.2,
    payout_email TEXT DEFAULT '',
    total_earned_copper INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS referral_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    affiliate_id INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    commission_copper INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (affiliate_id) REFERENCES affiliates(id),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    resource TEXT NOT NULL DEFAULT '',
    detail TEXT DEFAULT '',
    ip_address TEXT DEFAULT '',
    success INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    owner_account TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workspace_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    account_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    UNIQUE(workspace_id, account_name)
);

CREATE TABLE IF NOT EXISTS experiences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL,
    action_key TEXT NOT NULL,
    action_label TEXT NOT NULL DEFAULT '',
    strategy TEXT NOT NULL DEFAULT 'hybrid',
    reward REAL NOT NULL DEFAULT 0.0,
    outcome TEXT NOT NULL DEFAULT 'unknown',
    gold_impact INTEGER NOT NULL DEFAULT 0,
    build_impact REAL NOT NULL DEFAULT 0.0,
    legendary_impact REAL NOT NULL DEFAULT 0.0,
    time_spent_minutes INTEGER NOT NULL DEFAULT 0,
    success INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL UNIQUE,
    preferred_strategy TEXT NOT NULL DEFAULT 'hybrid',
    gold_weight REAL NOT NULL DEFAULT 0.3,
    build_weight REAL NOT NULL DEFAULT 0.3,
    legendary_weight REAL NOT NULL DEFAULT 0.3,
    time_weight REAL NOT NULL DEFAULT -0.2,
    risk_weight REAL NOT NULL DEFAULT -0.05,
    total_experiences INTEGER NOT NULL DEFAULT 0,
    avg_reward REAL NOT NULL DEFAULT 0.0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quest_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL,
    quest_key TEXT NOT NULL,
    quest_label TEXT NOT NULL DEFAULT '',
    day_index INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    week_start TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(account_name, quest_key, week_start)
);

CREATE TABLE IF NOT EXISTS user_goals (
    goal_id TEXT PRIMARY KEY,
    account_name TEXT NOT NULL,
    raw_text TEXT NOT NULL DEFAULT '',
    goal_type TEXT NOT NULL DEFAULT 'GENERIC',
    target_item_id INTEGER NOT NULL DEFAULT 0,
    target_item_name TEXT NOT NULL DEFAULT '',
    strategy TEXT NOT NULL DEFAULT 'balanced',
    time_budget_minutes INTEGER NOT NULL DEFAULT 0,
    gold_budget_copper INTEGER NOT NULL DEFAULT 0,
    game_mode TEXT NOT NULL DEFAULT '',
    constraints TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS progression_plans (
    plan_id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL DEFAULT '',
    account_name TEXT NOT NULL,
    strategy TEXT NOT NULL DEFAULT 'balanced',
    total_cost_copper INTEGER NOT NULL DEFAULT 0,
    estimated_days INTEGER NOT NULL DEFAULT 0,
    completion_percent REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'active',
    insight TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plan_actions (
    action_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    action_type TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    reward_gold INTEGER NOT NULL DEFAULT 0,
    cost_gold INTEGER NOT NULL DEFAULT 0,
    time_cost_minutes INTEGER NOT NULL DEFAULT 0,
    score REAL NOT NULL DEFAULT 0.0,
    priority INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    tab TEXT NOT NULL DEFAULT '',
    item_id INTEGER NOT NULL DEFAULT 0,
    day_index INTEGER NOT NULL DEFAULT -1,
    confidence REAL NOT NULL DEFAULT 0,
    data_sources TEXT NOT NULL DEFAULT '[]',
    risk_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (plan_id) REFERENCES progression_plans(plan_id)
);

CREATE TABLE IF NOT EXISTS plan_revisions (
    revision_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    user_request TEXT NOT NULL DEFAULT '',
    previous_strategy TEXT NOT NULL DEFAULT '',
    new_strategy TEXT NOT NULL DEFAULT '',
    delta_summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (plan_id) REFERENCES progression_plans(plan_id)
);

CREATE TABLE IF NOT EXISTS report_artifacts (
    report_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    account_name TEXT NOT NULL,
    report_type TEXT NOT NULL DEFAULT 'free',
    file_url TEXT NOT NULL DEFAULT '',
    access_level TEXT NOT NULL DEFAULT 'free',
    price_copper INTEGER NOT NULL DEFAULT 0,
    preview_html TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (plan_id) REFERENCES progression_plans(plan_id)
);

CREATE TABLE IF NOT EXISTS ontology_objects (
    object_id TEXT PRIMARY KEY,
    class_name TEXT NOT NULL,
    account_name TEXT NOT NULL DEFAULT '',
    properties TEXT NOT NULL DEFAULT '{}',
    qa_status TEXT NOT NULL DEFAULT 'pending',
    privacy_scope TEXT NOT NULL DEFAULT 'private',
    revision INTEGER NOT NULL DEFAULT 1,
    source_object_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ontology_relations (
    relation_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    properties TEXT NOT NULL DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ontology_actions (
    action_id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    account_name TEXT NOT NULL DEFAULT '',
    params TEXT NOT NULL DEFAULT '{}',
    preconditions_met INTEGER NOT NULL DEFAULT 0,
    affected_object_ids TEXT NOT NULL DEFAULT '[]',
    rollback_strategy TEXT NOT NULL DEFAULT 'manual',
    privacy_policy TEXT NOT NULL DEFAULT 'private',
    freshness_policy TEXT NOT NULL DEFAULT 'any',
    qa_status TEXT NOT NULL DEFAULT 'pending',
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ontology_kernel_states (
    tenant_id TEXT PRIMARY KEY,
    kernel_version TEXT NOT NULL,
    state_json TEXT NOT NULL DEFAULT '{}',
    state_hash TEXT NOT NULL,
    lineage_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ontology_kernel_lineage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    step INTEGER NOT NULL,
    action_hash TEXT NOT NULL,
    from_hash TEXT NOT NULL,
    to_hash TEXT NOT NULL,
    record_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tenant_id, step)
);

CREATE TABLE IF NOT EXISTS snapshot_registry (
    snapshot_id TEXT PRIMARY KEY,
    account_name TEXT NOT NULL,
    raw_data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


async def init_db():
    if not _TEST_DB_URL:
        _ensure_db_dir()
    conn = await _create_connection()
    try:
        for stmt in CREATE_TABLES.split(";"):
            s = stmt.strip()
            if s:
                await conn.execute(s)
        for migration_sql in [
            "ALTER TABLE credentials ADD COLUMN scopes TEXT DEFAULT ''",
            "ALTER TABLE credentials ADD COLUMN last_validated_at TEXT",
            "ALTER TABLE credentials ADD COLUMN workspace_id INTEGER DEFAULT NULL",
            "ALTER TABLE progression_goal_templates ADD COLUMN source_url TEXT DEFAULT ''",
            "ALTER TABLE progression_goal_templates ADD COLUMN patch_version TEXT DEFAULT ''",
            "ALTER TABLE progression_goal_templates ADD COLUMN review_status TEXT DEFAULT 'unreviewed'",
            "ALTER TABLE progression_goal_templates ADD COLUMN deprecated INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE item_holdings ADD COLUMN quality_status TEXT NOT NULL DEFAULT 'unknown'",
            "ALTER TABLE item_holdings ADD COLUMN liquidity_score TEXT NOT NULL DEFAULT 'unknown'",
            "ALTER TABLE item_holdings ADD COLUMN liquidity_reason TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE item_holdings ADD COLUMN confidence REAL NOT NULL DEFAULT 0",
            "ALTER TABLE item_holdings ADD COLUMN data_sources TEXT NOT NULL DEFAULT '[]'",
            "ALTER TABLE item_holdings ADD COLUMN price_timestamp TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE item_holdings ADD COLUMN risk_reason TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE plan_actions ADD COLUMN confidence REAL NOT NULL DEFAULT 0",
            "ALTER TABLE plan_actions ADD COLUMN data_sources TEXT NOT NULL DEFAULT '[]'",
            "ALTER TABLE plan_actions ADD COLUMN risk_reason TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE order_idempotency_keys ADD COLUMN status TEXT NOT NULL DEFAULT 'fulfilled'",
            "ALTER TABLE order_idempotency_keys ADD COLUMN error TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE order_idempotency_keys ADD COLUMN fulfilled_at TEXT",
            "ALTER TABLE delivery_jobs ADD COLUMN claimed_at TEXT",
        ]:
            try:
                await conn.execute(migration_sql)
            except Exception:
                pass  # Column already exists
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_recipes_output ON static_recipes(output_item_id)",
            "CREATE INDEX IF NOT EXISTS idx_ingredients_recipe ON recipe_ingredients(recipe_id)",
            "CREATE INDEX IF NOT EXISTS idx_ingredients_item ON recipe_ingredients(item_id)",
            "CREATE INDEX IF NOT EXISTS idx_snapshots_account ON account_snapshots(account_name)",
            "CREATE INDEX IF NOT EXISTS idx_holdings_snapshot ON item_holdings(snapshot_id)",
            "CREATE INDEX IF NOT EXISTS idx_history_account ON account_value_history(account_name)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_licenses_order_id_unique ON licenses(order_id) WHERE order_id IS NOT NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_delivery_jobs_order_id_unique ON delivery_jobs(order_id)",
            "CREATE INDEX IF NOT EXISTS idx_payment_events_status ON payment_events(status)",
            "CREATE INDEX IF NOT EXISTS idx_delivery_outbox_status ON delivery_outbox(status)",
            "CREATE INDEX IF NOT EXISTS idx_ontology_kernel_lineage_tenant ON ontology_kernel_lineage(tenant_id, step)",
        ]:
            try:
                await conn.execute(idx_sql)
            except Exception:
                pass
        await conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    finally:
        await conn.close()


async def save_price_snapshot(
    db: aiosqlite.Connection,
    item_id: int,
    buy_price: int,
    buy_qty: int,
    sell_price: int,
    sell_qty: int,
):
    now = datetime.now(timezone.utc).isoformat()
    sql = "INSERT INTO price_snapshots (item_id, buy_unit_price, buy_quantity, sell_unit_price, sell_quantity, fetched_at) VALUES (?, ?, ?, ?, ?, ?)"
    await db.execute(sql, (item_id, buy_price, buy_qty, sell_price, sell_qty, now))


async def save_account_snapshot(
    db: aiosqlite.Connection,
    account_name: str,
    api_key_hash: str | None,
    summary: ValueSummary,
    holdings: list[ItemHolding],
    warnings: list,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cursor = await db.execute(
        """INSERT INTO account_snapshots
        (account_name, api_key_hash, total_value_buy, total_value_sell, net_sell_value,
         wallet_value, material_value_buy, material_value_sell,
         bank_value_buy, bank_value_sell,
         character_inventory_value_buy, character_inventory_value_sell,
         shared_inventory_value_buy, shared_inventory_value_sell,
         tradingpost_value, priced_item_count, unpriced_item_count,
         account_bound_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            account_name,
            api_key_hash,
            summary.total_value_buy,
            summary.total_value_sell,
            summary.net_sell_value,
            summary.wallet_value,
            summary.material_value_buy,
            summary.material_value_sell,
            summary.bank_value_buy,
            summary.bank_value_sell,
            summary.character_inventory_value_buy,
            summary.character_inventory_value_sell,
            summary.shared_inventory_value_buy,
            summary.shared_inventory_value_sell,
            summary.tradingpost_value,
            summary.priced_item_count,
            summary.unpriced_item_count,
            summary.account_bound_count,
            now,
        ),
    )
    snapshot_id = cursor.lastrowid

    for h in holdings:
        await db.execute(
            """INSERT INTO item_holdings
            (snapshot_id, item_id, count, location_type, location_ref, binding_status,
             tradable, vendor_value, price_buy, price_sell, value_buy, value_sell, valuation_status,
             quality_status, liquidity_score, liquidity_reason, confidence, data_sources,
             price_timestamp, risk_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot_id,
                h.item_id,
                h.count,
                h.location_type,
                h.location_ref,
                h.binding_status,
                1 if h.tradable else 0,
                h.vendor_value,
                h.price_buy,
                h.price_sell,
                h.value_buy,
                h.value_sell,
                h.valuation_status,
                h.quality_status,
                h.liquidity_score,
                h.liquidity_reason,
                h.confidence,
                json.dumps(h.data_sources),
                h.price_timestamp,
                h.risk_reason,
            ),
        )

    await db.execute(
        """INSERT INTO account_value_history
        (account_name, snapshot_time, total_value_buy, total_value_sell,
         wallet_value, material_value, bank_value, inventory_value, tradingpost_value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            account_name,
            now,
            summary.total_value_buy,
            summary.total_value_sell,
            summary.wallet_value,
            summary.material_value_buy,
            summary.bank_value_buy,
            summary.character_inventory_value_buy + summary.shared_inventory_value_buy,
            summary.tradingpost_value,
        ),
    )

    for w in warnings:
        await db.execute(
            "INSERT INTO valuation_warnings (snapshot_id, warning_type, message, item_id) VALUES (?, ?, ?, ?)",
            (snapshot_id, w.warning_type, w.message, w.item_id),
        )

    await db.commit()
    return snapshot_id


def _decode_data_sources(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _row_value(row, key: str, default=None):
    try:
        if key in row.keys():
            return row[key]
    except AttributeError:
        if isinstance(row, dict) and key in row:
            return row[key]
    return default


async def load_latest_holdings(db: aiosqlite.Connection, account_name: str) -> list[ItemHolding]:
    cursor = await db.execute(
        """SELECT ih.item_id, ih.count, ih.location_type, ih.location_ref,
           ih.binding_status, ih.tradable, ih.vendor_value,
           ih.price_buy, ih.price_sell, ih.value_buy, ih.value_sell, ih.valuation_status,
           ih.quality_status, ih.liquidity_score, ih.liquidity_reason, ih.confidence,
           ih.data_sources, ih.price_timestamp, ih.risk_reason
           FROM item_holdings ih
           JOIN account_snapshots s ON ih.snapshot_id = s.id
           WHERE s.account_name = ?
           AND s.id = (SELECT MAX(id) FROM account_snapshots WHERE account_name = ?)""",
        (account_name, account_name),
    )
    rows = await cursor.fetchall()
    return [
        ItemHolding(
            item_id=row["item_id"],
            count=row["count"],
            location_type=row["location_type"],
            location_ref=row["location_ref"],
            binding_status=row["binding_status"],
            tradable=bool(row["tradable"]),
            vendor_value=row["vendor_value"],
            price_buy=row["price_buy"],
            price_sell=row["price_sell"],
            value_buy=row["value_buy"],
            value_sell=row["value_sell"],
            valuation_status=row["valuation_status"],
            quality_status=_row_value(row, "quality_status", "unknown"),
            liquidity_score=_row_value(row, "liquidity_score", "unknown"),
            liquidity_reason=_row_value(row, "liquidity_reason", ""),
            confidence=_row_value(row, "confidence", 0.0),
            data_sources=_decode_data_sources(_row_value(row, "data_sources", "[]")),
            price_timestamp=_row_value(row, "price_timestamp", ""),
            risk_reason=_row_value(row, "risk_reason", ""),
        )
        for row in rows
    ]


async def search_latest_holdings(
    db: aiosqlite.Connection,
    account_name: str,
    query: str | None = None,
    location_type: str | None = None,
    valuation_status: str | None = None,
    limit: int = 100,
) -> list[ItemHolding]:
    conditions = ["s.account_name = ?", "s.id = (SELECT MAX(id) FROM account_snapshots WHERE account_name = ?)"]
    params = [account_name, account_name]

    if query:
        try:
            item_id = int(query)
            conditions.append("ih.item_id = ?")
            params.append(item_id)
        except ValueError:
            pass
    if location_type:
        conditions.append("ih.location_type = ?")
        params.append(location_type)
    if valuation_status:
        conditions.append("ih.valuation_status = ?")
        params.append(valuation_status)

    sql = f"""SELECT ih.item_id, ih.count, ih.location_type, ih.location_ref,
           ih.binding_status, ih.tradable, ih.vendor_value,
           ih.price_buy, ih.price_sell, ih.value_buy, ih.value_sell, ih.valuation_status,
           ih.quality_status, ih.liquidity_score, ih.liquidity_reason, ih.confidence,
           ih.data_sources, ih.price_timestamp, ih.risk_reason
           FROM item_holdings ih
           JOIN account_snapshots s ON ih.snapshot_id = s.id
           WHERE {" AND ".join(conditions)}
           ORDER BY ih.value_buy DESC
           LIMIT ?"""
    params.append(limit)

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    return [
        ItemHolding(
            item_id=row["item_id"],
            count=row["count"],
            location_type=row["location_type"],
            location_ref=row["location_ref"],
            binding_status=row["binding_status"],
            tradable=bool(row["tradable"]),
            vendor_value=row["vendor_value"],
            price_buy=row["price_buy"],
            price_sell=row["price_sell"],
            value_buy=row["value_buy"],
            value_sell=row["value_sell"],
            valuation_status=row["valuation_status"],
            quality_status=_row_value(row, "quality_status", "unknown"),
            liquidity_score=_row_value(row, "liquidity_score", "unknown"),
            liquidity_reason=_row_value(row, "liquidity_reason", ""),
            confidence=_row_value(row, "confidence", 0.0),
            data_sources=_decode_data_sources(_row_value(row, "data_sources", "[]")),
            price_timestamp=_row_value(row, "price_timestamp", ""),
            risk_reason=_row_value(row, "risk_reason", ""),
        )
        for row in rows
    ]


SNAPSHOT_RETENTION = 20
HISTORY_RETENTION = 90  # days
PRICE_RETENTION = 7  # days


async def cleanup_old_data(account_name: str | None = None) -> dict:
    """Remove old snapshots, history, and price data beyond retention limits."""
    db = await get_db()
    result = {"snapshots_deleted": 0, "history_deleted": 0, "prices_deleted": 0}
    try:
        if account_name:
            # Keep only the most recent N snapshots for this account
            cursor = await db.execute(
                """DELETE FROM account_snapshots WHERE id NOT IN
                   (SELECT id FROM account_snapshots WHERE account_name = ? ORDER BY id DESC LIMIT ?)
                   AND account_name = ?""",
                (account_name, SNAPSHOT_RETENTION, account_name),
            )
            result["snapshots_deleted"] = cursor.rowcount

            # Clean orphaned holdings
            await db.execute("DELETE FROM item_holdings WHERE snapshot_id NOT IN (SELECT id FROM account_snapshots)")
            await db.execute("DELETE FROM valuation_warnings WHERE snapshot_id NOT IN (SELECT id FROM account_snapshots)")

        # Clean old price data
        cursor = await db.execute(
            "DELETE FROM price_snapshots WHERE fetched_at < datetime('now', ?)",
            (f"-{PRICE_RETENTION} days",),
        )
        result["prices_deleted"] = cursor.rowcount

        await db.commit()
    finally:
        await db.close()
    return result


async def load_value_history(db: aiosqlite.Connection, account_name: str, limit: int = 30) -> list[ValueHistoryEntry]:
    cursor = await db.execute(
        """SELECT snapshot_time, total_value_buy, total_value_sell, wallet_value,
           material_value, bank_value, inventory_value, tradingpost_value
           FROM account_value_history
           WHERE account_name = ?
           ORDER BY snapshot_time DESC
           LIMIT ?""",
        (account_name, limit),
    )
    rows = await cursor.fetchall()
    return [
        ValueHistoryEntry(
            snapshot_time=row["snapshot_time"],
            total_value_buy=row["total_value_buy"],
            total_value_sell=row["total_value_sell"],
            wallet_value=row["wallet_value"],
            material_value=row["material_value"],
            bank_value=row["bank_value"],
            inventory_value=row["inventory_value"],
            tradingpost_value=row["tradingpost_value"],
        )
        for row in rows
    ]
