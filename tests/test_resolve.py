"""Tests for the resolve proxy endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from gw2_progression.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@patch("gw2_progression.api.routes.resolve._gw2_fetch")
def test_resolve_items(mock_fetch, client):
    mock_fetch.return_value = [{"id": 123, "name": "Test Item", "icon": "test.png"}]
    resp = client.post("/resolve", json={"type": "items", "ids": ["123"]})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "Test Item"


@patch("gw2_progression.api.routes.resolve._gw2_fetch")
def test_resolve_materials(mock_fetch, client):
    mock_fetch.return_value = [{"id": 1, "name": "Bank"}]
    resp = client.post("/resolve", json={"type": "materials", "ids": []})
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Bank"


@patch("gw2_progression.api.routes.resolve._gw2_fetch")
def test_resolve_guild(mock_fetch, client):
    mock_fetch.return_value = {"id": "guild-id", "name": "Test Guild", "tag": "TEST"}
    resp = client.post("/resolve", json={"type": "guild", "id": "guild-id"})
    assert resp.status_code == 200
    assert resp.json()["tag"] == "TEST"


def test_resolve_unknown_type(client):
    resp = client.post("/resolve", json={"type": "unknown", "ids": []})
    assert resp.status_code == 400


@patch("gw2_progression.api.routes.resolve._gw2_fetch")
def test_resolve_empty_ids(mock_fetch, client):
    resp = client.post("/resolve", json={"type": "items", "ids": []})
    assert resp.status_code == 200
    assert resp.json() == []
