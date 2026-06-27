"""Tests for the session_middleware — token resolution across all routes."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gw2_progression.api.main import app

RESOLVED_KEY = "ABCDEF01-2345-6789-ABCD-EF0123456789AB"
SESSION_TOKEN = "a" * 48
SHORT_KEY = "ABCDEF01-2345-6789-ABCD-EF0123456789"


@pytest.fixture(autouse=True)
def _reset():
    """Clean up any state between tests."""
    from gw2_progression.api.main import _rate_limit_buckets

    _rate_limit_buckets.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _mock_get_api_key(resolved=None):
    """Patch get_api_key where it's imported (main.py) to resolve SESSION_TOKEN -> RESOLVED_KEY."""
    async def side_effect(key):
        if key == SESSION_TOKEN:
            return resolved or RESOLVED_KEY
        return key

    return patch("gw2_progression.api.main.get_api_key", AsyncMock(side_effect=side_effect))


# ── Middleware scope: which methods are intercepted ──


def test_middleware_skips_get_requests(client):
    """GET requests are not touched by the middleware."""
    resp = client.get("/health")
    assert resp.status_code == 200


def test_middleware_skips_delete_requests(client):
    resp = client.delete("/auth/session/test-token")
    assert resp.status_code == 404  # session not found, but crucially not a body-read error


# ── Token resolved on all key affected route groups ──


@pytest.mark.parametrize("route", [
    "/api/v1/decide",
    "/api/v1/feedback",
])
def test_production_routes_resolve_token(client, route):
    with _mock_get_api_key() as mock:
        body = {"api_key": SESSION_TOKEN, "account_name": "test", "action_key": "a1"} if route == "/api/v1/feedback" else {"api_key": SESSION_TOKEN}
        resp = client.post(route, json=body)
    assert resp.status_code in (200, 422, 500)
    mock.assert_called_once_with(SESSION_TOKEN)


@pytest.mark.parametrize("route", [
    "/builds/recommendations",
    "/builds/readiness/sc_dh",
])
def test_builds_routes_resolve_token(client, route):
    with _mock_get_api_key() as mock:
        resp = client.post(route, json={"api_key": SESSION_TOKEN})
    assert resp.status_code in (200, 401, 422, 500)
    mock.assert_called_once_with(SESSION_TOKEN)


@pytest.mark.parametrize("route", [
    "/crafting/calculate",
    "/crafting/calculate/cheapest",
    "/crafting/plan",
    "/crafting/optimize",
])
def test_crafting_routes_resolve_token(client, route):
    with _mock_get_api_key() as mock:
        body = {"api_key": SESSION_TOKEN, "target_item_id": 19976}
        if "calculate" in route or "plan" in route:
            body["quantity"] = 1
        resp = client.post(route, json=body)
    assert resp.status_code in (200, 401, 422, 500)
    mock.assert_called_once_with(SESSION_TOKEN)


@pytest.mark.parametrize("route", [
    "/goals",
    "/goals/test-goal-id/refresh",
])
def test_goals_routes_resolve_token(client, route):
    with _mock_get_api_key() as mock:
        body = {"api_key": SESSION_TOKEN, "target_item_id": 19976} if route == "/goals" else {"api_key": SESSION_TOKEN}
        resp = client.post(route, json=body)
    assert resp.status_code in (200, 401, 404, 422, 500)
    mock.assert_called_once_with(SESSION_TOKEN)


@pytest.mark.parametrize("route", [
    "/progression/plans",
])
def test_progression_route_resolve_token(client, route):
    with _mock_get_api_key() as mock:
        resp = client.post(route, json={"api_key": SESSION_TOKEN, "template_id": "test"})
    assert resp.status_code in (200, 401, 422, 500)
    mock.assert_called_once_with(SESSION_TOKEN)


@pytest.mark.parametrize("route", [
    "/agent/progression/advice",
    "/agent/progression/weekly-plan",
    "/agent/coach-plan",
])
def test_agent_routes_resolve_token(client, route):
    with _mock_get_api_key() as mock:
        resp = client.post(route, json={"api_key": SESSION_TOKEN})
    assert resp.status_code in (200, 401, 422, 500)
    mock.assert_called_once_with(SESSION_TOKEN)


@pytest.mark.parametrize("route", [
    "/engine/decide",
    "/engine/plan",
])
def test_engine_routes_resolve_token(client, route):
    with _mock_get_api_key() as mock:
        resp = client.post(route, json={"api_key": SESSION_TOKEN})
    assert resp.status_code in (200, 401, 422, 500)
    mock.assert_called_once_with(SESSION_TOKEN)


@pytest.mark.parametrize("route", [
    "/goal-driven/generate",
    "/goal-driven/revise",
    "/goal-driven/progressive",
    "/goal-driven/progressive/full",
])
def test_goal_driven_routes_resolve_token(client, route):
    with _mock_get_api_key() as mock:
        body = {"api_key": SESSION_TOKEN, "goal_text": "make gold"} if route == "/goal-driven/generate" \
            else {"api_key": SESSION_TOKEN, "plan_id": "p1", "revision_text": "cheaper"} if route == "/goal-driven/revise" \
            else {"api_key": SESSION_TOKEN}
        resp = client.post(route, json=body)
    assert resp.status_code in (200, 401, 404, 422, 500)
    mock.assert_called_once_with(SESSION_TOKEN)


def test_v4_decide_resolves_token(client):
    with _mock_get_api_key() as mock:
        resp = client.post("/v4/decide", json={"api_key": SESSION_TOKEN})
    assert resp.status_code in (200, 422, 500)
    mock.assert_called_once_with(SESSION_TOKEN)


def test_v5_decide_resolves_token(client):
    with _mock_get_api_key() as mock:
        resp = client.post("/v5/decide", json={"api_key": SESSION_TOKEN})
    assert resp.status_code in (200, 422, 500)
    mock.assert_called_once_with(SESSION_TOKEN)


# ── /analyze and /value/analyze still work (regression) ──


def test_analyze_resolves_token(client):
    """Backward compat: /analyze still resolves session tokens."""
    from gw2_progression.gw2_client import Gw2ApiError

    with _mock_get_api_key() as mock:
        resp = client.post("/analyze", json={"api_key": SESSION_TOKEN})
    # tokeninfo fetch will fail because mocked key is not the real one from DB
    assert resp.status_code in (200, 401, 422)
    mock.assert_called_once_with(SESSION_TOKEN)


def test_value_analyze_resolves_token(client):
    with _mock_get_api_key() as mock:
        resp = client.post("/value/analyze", json={"api_key": SESSION_TOKEN})
    assert resp.status_code in (200, 401, 422)
    mock.assert_called_once_with(SESSION_TOKEN)


# ── Short / non-token keys pass through unchanged ──


def test_short_key_passthrough_on_analyze(client):
    """A short (< 40 char) api_key is NOT resolved — passed as-is."""
    with patch(
        "gw2_progression.api.main.get_api_key",
        AsyncMock(side_effect=lambda k: k),
    ) as mock:
        resp = client.post("/analyze", json={"api_key": SHORT_KEY})
    assert resp.status_code in (200, 401, 422)
    mock.assert_called_once_with(SHORT_KEY)


# ── Middleware handles non-JSON / missing body gracefully ──


def test_middleware_on_non_json_body(client):
    """If the body is not valid JSON, the middleware should not crash."""
    with patch("gw2_progression.api.main.get_api_key") as mock:
        resp = client.post(
            "/agent/progression/advice",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code in (422, 500)  # FastAPI validation catches it
    mock.assert_not_called()


def test_middleware_on_empty_body(client):
    """If the body is empty JSON, the middleware should not crash."""
    with patch("gw2_progression.api.main.get_api_key") as mock:
        resp = client.post("/agent/progression/advice", json={})
    assert resp.status_code == 422
    mock.assert_not_called()


# ── Resolved key actually reaches the route handler ──


def test_resolved_key_propagates_to_agent_route(client):
    """Verify the resolved key reaches the route handler (401 means GW2 API was called with resolved key)."""
    from gw2_progression.gw2_client import Gw2ApiError

    with _mock_get_api_key(RESOLVED_KEY):
        with patch("gw2_progression.api.routes.agent.generate_advice") as svc:
            svc.side_effect = Gw2ApiError(401, "Invalid or expired API key.")
            client.post("/agent/progression/advice", json={"api_key": SESSION_TOKEN})
    call_key = svc.call_args[0][0] if svc.call_args else None
    assert call_key == RESOLVED_KEY, f"Expected {RESOLVED_KEY}, got {call_key}"
