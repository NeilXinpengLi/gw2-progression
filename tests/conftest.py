"""Global test configuration — ensures DB file exists and disables ontology persistence."""

from pathlib import Path

import pytest

# Ensure the data directory exists before any test runs.
DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)

from gw2_progression.ontology import object_store as ontology_store  # noqa: E402

# Disable fire-and-forget SQLite persistence during tests.
# Tests only need in-memory ontology operations.
ontology_store._PERSIST_ENABLED = False


@pytest.fixture
async def commerce_db(tmp_path: Path, monkeypatch):
    from gw2_progression import database

    await database.close_pool()
    db_path = tmp_path / "commerce.db"
    monkeypatch.setattr(database, "_TEST_DB_URL", str(db_path))
    await database.init_db()
    async with database.using_db() as conn:
        await conn.execute(
            """INSERT INTO products (id, slug, name, description, price_copper, type, deliverables, active)
               VALUES (1, 'test-report', 'Test Report', 'A test report', 30000, 'one_time', '[]', 1)"""
        )
    try:
        yield db_path
    finally:
        await database.close_pool()
        monkeypatch.setattr(database, "_TEST_DB_URL", "")
