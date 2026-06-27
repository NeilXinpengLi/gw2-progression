"""Global test configuration — disables ontology persistence to avoid DB pool contention."""

from gw2_progression.ontology import object_store as ontology_store

# Disable fire-and-forget SQLite persistence during tests.
# Tests only need in-memory ontology operations.
ontology_store._PERSIST_ENABLED = False
