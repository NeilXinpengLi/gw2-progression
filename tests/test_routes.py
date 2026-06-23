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
    assert resp.json() == {"status": "ok"}


def test_analyze_short_key_returns_422(client):
    """Key < 8 chars should fail validation before any HTTP call."""
    resp = client.post("/analyze", json={"api_key": "short"})
    assert resp.status_code == 422
    detail = resp.json()["detail"][0]
    assert "8 characters" in detail["msg"]


def test_analyze_invalid_chars_returns_422(client):
    """Key with non-hex characters should fail validation."""
    resp = client.post("/analyze", json={"api_key": "key-with-special-chars-!!!@#$"})
    assert resp.status_code == 422


def test_analyze_valid_key_returns_200(client):
    """Valid key format + mocked backend -> 200 with account data."""

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
    """Backend returns 401 -> route returns 401."""
    from gw2_progression.gw2_client import Gw2ApiError

    with patch(f"{BASE}.fetch_tokeninfo", _mock_async(side_effect=Gw2ApiError(401, "Invalid or expired API key."))):
        resp = client.post("/analyze", json={"api_key": "ABCDEF01-2345-6789-ABCD-EF0123456789AB"})
    assert resp.status_code == 401
    assert "Invalid" in resp.json()["detail"]


def test_health_returns_request_id(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers


def test_index_serves_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")


def test_static_css(client):
    resp = client.get("/static/style.css")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/css")


def test_static_js(client):
    resp = client.get("/static/app.js")
    assert resp.status_code == 200
    ct = resp.headers["content-type"]
    assert "javascript" in ct


def test_analyze_missing_body_returns_422(client):
    resp = client.post("/analyze", json={})
    # 429 if rate limited, 422 if validation fails — both acceptable
    assert resp.status_code in (422, 429)
