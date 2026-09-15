"""Manual end-to-end checks for the Expert AI compose stack.

Run with:
  docker compose -f docker-compose.expert-ai.yml up --build
  $env:RUN_EXPERT_AI_E2E="1"; python -m pytest tests/test_expert_ai_compose_e2e.py -q
"""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.skipif(os.getenv("RUN_EXPERT_AI_E2E") != "1", reason="requires docker-compose.expert-ai.yml stack")


def test_expert_ai_compose_stack_persistence_and_queue():
    base_url = os.getenv("EXPERT_AI_E2E_BASE_URL", "http://localhost:8000")

    health = httpx.get(f"{base_url}/persistence/health", timeout=10)
    assert health.status_code == 200
    assert health.json()["services"]["postgres"]["configured"] is True
    assert health.json()["services"]["neo4j"]["configured"] is True
    assert health.json()["services"]["qdrant"]["configured"] is True
    assert health.json()["services"]["redis"]["configured"] is True

    migration = httpx.post(f"{base_url}/persistence/migrate", timeout=20)
    assert migration.status_code == 200
    assert migration.json()["postgres"]["migrated"] is True

    snapshot = httpx.post(
        f"{base_url}/runtime/snapshot",
        json={
            "entities": [{"id": "account:e2e", "type": "account_snapshot", "properties": {"name": "E2E"}}],
            "relations": [],
        },
        timeout=10,
    )
    assert snapshot.status_code == 200

    persisted = httpx.post(f"{base_url}/persistence/snapshot", timeout=20)
    assert persisted.status_code == 200
    assert persisted.json()["postgres"]["written"] is True

    graph = httpx.post(f"{base_url}/persistence/graph/write", timeout=20)
    assert graph.status_code == 200
    assert graph.json()["written"] is True

    queued = httpx.post(f"{base_url}/queue/enqueue", json={"type": "health"}, timeout=10)
    assert queued.status_code == 200
    assert queued.json()["queued"] is True
