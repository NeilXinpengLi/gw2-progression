"""Tests for the unified Production Decision Engine."""

import pytest


class TestProductionEngine:
    @pytest.mark.asyncio
    async def test_decision_engine_requires_key(self):
        from fastapi.testclient import TestClient

        from gw2_progression.api.main import app

        client = TestClient(app)
        resp = client.post("/api/v1/decide", json={})
        assert resp.status_code in (422, 429)

    @pytest.mark.asyncio
    async def test_feedback_requires_fields(self):
        from fastapi.testclient import TestClient

        from gw2_progression.api.main import app

        client = TestClient(app)
        resp = client.post("/api/v1/feedback", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_strategies_endpoint(self):
        from fastapi.testclient import TestClient

        from gw2_progression.api.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/strategies")
        assert resp.status_code in (200, 429)
        if resp.status_code == 200:
            assert len(resp.json()["strategies"]) == 4

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        from fastapi.testclient import TestClient

        from gw2_progression.api.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["engine"] == "decision-engine"
