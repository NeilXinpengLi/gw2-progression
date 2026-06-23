"""API integration tests — pure endpoints, no DB dependency needed."""

from fastapi.testclient import TestClient

from gw2_progression.api.main import app

client = TestClient(app)


class TestSystemEndpoints:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_metrics(self):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        assert "requests_total" in data

    def test_root_serves_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestBuildEndpoints:
    def test_templates(self):
        resp = client.get("/builds/templates")
        assert resp.status_code == 200
        assert len(resp.json()) >= 15

    def test_template_by_id(self):
        # Get first template from list to find a valid ID
        templates = client.get("/builds/templates").json()
        if templates:
            tid = templates[0]["build_id"]
            resp = client.get(f"/builds/templates/{tid}")
            assert resp.status_code == 200
            assert resp.json()["build_id"] == tid

    def test_template_not_found(self):
        resp = client.get("/builds/templates/nonexistent")
        assert resp.status_code == 404


class TestCommerceEndpoints:
    def test_products(self):
        resp = client.get("/commerce/products")
        assert resp.status_code == 200
        assert len(resp.json()) >= 4

    def test_order_requires_email(self):
        resp = client.post("/commerce/orders", json={"product_id": 1})
        assert resp.status_code == 422


class TestResolveEndpoints:
    def test_resolve_empty(self):
        resp = client.post("/resolve", json={"type": "items", "ids": []})
        assert resp.status_code == 200
        assert resp.json() == []


class TestGoalsEndpoints:
    def test_create_missing_fields(self):
        resp = client.post("/goals", json={"account_name": "test"})
        assert resp.status_code == 422


class TestAgentEndpoints:
    def test_advice_requires_key(self):
        resp = client.post("/agent/progression/advice", json={"api_key": ""})
        assert resp.status_code == 422

    def test_weekly_plan_requires_key(self):
        resp = client.post("/agent/progression/weekly-plan", json={"api_key": ""})
        assert resp.status_code == 422


class TestCredentialsEndpoints:
    def test_list_empty(self):
        resp = client.get("/credentials")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestProgressionEndpoints:
    def test_template_not_found(self):
        resp = client.get("/progression/templates/nonexistent")
        assert resp.status_code == 404
