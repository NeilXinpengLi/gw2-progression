"""Global test configuration — ensures DB file exists and disables ontology persistence."""

from pathlib import Path

# Ensure the data directory exists before any test runs.
DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)

from gw2_progression.ontology import object_store as ontology_store

# Disable fire-and-forget SQLite persistence during tests.
# Tests only need in-memory ontology operations.
ontology_store._PERSIST_ENABLED = False
