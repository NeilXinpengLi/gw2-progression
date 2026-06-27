"""Integration tests for the FastAPI route layer using TestClient."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gw2_progression.api.main import app


def _mock_async(return_value=None, side_effect=None):
    m = AsyncMock()
    if side_effect:
        m.side_effect = side_effect
    else:
        m.return_value = return_value
    return m


TOKENINFO = {"name": "TestKey", "id": "abc", "permissions": ["account"]}
ACCOUNT = {
    "name": "Player.1234",
    "world": 1001,
    "created": "2022-01-01T00:00:00Z",
    "age": 3600,
    "fractal_level": 10,
    "daily_ap": 100,
    "monthly_ap": 0,
    "wvw_rank": 1,
    "guilds": [],
}

BASE = "gw2_progression.analyzer"


@pytest.fixture
def client():
    return TestClient(app)


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Redirect ──

def test_root_serves_landing(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "GW2 Progression" in resp.text
    assert "Reimagined" in resp.text


# ── Static Pages ──

def test_account_page_served(client):
    resp = client.get("/account")
    assert resp.status_code == 200
    assert "Account Overview" in resp.text
    assert "nav-account" in resp.text  # SVG icon sprite


def test_insight_page_served(client):
    resp = client.get("/insight")
    assert resp.status_code == 200
    assert "AI Insights" in resp.text
    assert "nav-insight" in resp.text


def test_plan_page_served(client):
    resp = client.get("/plan")
    assert resp.status_code == 200
    assert "Progression Plan" in resp.text
    assert "nav-plan" in resp.text


# ── SVG Icons ──

def test_svg_sprite_inlined_in_account(client):
    resp = client.get("/account")
    assert '<symbol id="sym-nav-account"' in resp.text
    assert '<symbol id="sym-kpi-account-value"' in resp.text
    assert '<symbol id="sym-insight-hidden-wealth"' in resp.text


def test_svg_sprite_inlined_in_insight(client):
    resp = client.get("/insight")
    assert '<symbol id="sym-nav-insight"' in resp.text
    assert '<symbol id="sym-insight-hidden-wealth"' in resp.text
    assert '<symbol id="sym-strategy-balanced"' in resp.text


def test_svg_sprite_inlined_in_plan(client):
    resp = client.get("/plan")
    assert '<symbol id="sym-nav-plan"' in resp.text
    assert '<symbol id="sym-strategy-gold"' in resp.text
    assert '<symbol id="sym-kpi-legendary"' in resp.text


# ── Static Files ──

def test_static_css(client):
    resp = client.get("/static/style.css")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/css")


def test_static_js_account(client):
    resp = client.get("/static/app-account.v2.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]


def test_static_js_shared(client):
    resp = client.get("/static/app-shared.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]


def test_static_css_account(client):
    resp = client.get("/static/style-account.css")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/css")


# ── Health ──

def test_health_returns_request_id(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers


# ── Analyze endpoint ──

def test_analyze_short_key_returns_422(client):
    resp = client.post("/analyze", json={"api_key": "short"})
    assert resp.status_code == 422
    detail = resp.json()["detail"][0]
    assert "8 characters" in detail["msg"]


def test_analyze_invalid_chars_returns_422(client):
    resp = client.post("/analyze", json={"api_key": "key-with-special-chars-!!!@#$"})
    assert resp.status_code == 422


def test_analyze_valid_key_returns_200(client):
    with (
        patch(f"{BASE}.fetch_tokeninfo", _mock_async(TOKENINFO)),
        patch(f"{BASE}.fetch_account", _mock_async(ACCOUNT)),
    ):
        resp = client.post("/analyze", json={"api_key": "ABCDEF01-2345-6789-ABCD-EF0123456789AB"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["account_name"] == "Player.1234"
    assert body["token_name"] == "TestKey"


def test_analyze_invalid_key_returns_401(client):
    from gw2_progression.gw2_client import Gw2ApiError

    with patch(f"{BASE}.fetch_tokeninfo", _mock_async(side_effect=Gw2ApiError(401, "Invalid or expired API key."))):
        resp = client.post("/analyze", json={"api_key": "ABCDEF01-2345-6789-ABCD-EF0123456789AB"})
    assert resp.status_code in (401, 429)


def test_analyze_missing_body_returns_422(client):
    resp = client.post("/analyze", json={})
    assert resp.status_code in (422, 429)
