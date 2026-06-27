"""End-to-end integration tests for the full analysis pipeline.

Tests the complete flow: analyze → value → items → crafting using
the FastAPI TestClient with mocked GW2 API responses.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gw2_progression.api.main import app

client = TestClient(app)

MOCK_TOKENINFO = {"name": "TestKey", "id": "abc", "permissions": ["account", "inventories", "wallet", "tradingpost", "characters", "unlocks"]}
MOCK_ACCOUNT = {"name": "E2E.Player.1234", "world": 1001, "created": "2022-01-01T00:00:00Z", "age": 360000, "fractal_level": 50, "daily_ap": 500, "monthly_ap": 50, "wvw_rank": 100, "guilds": []}
MOCK_WALLET = [{"id": 1, "value": 500000}]
MOCK_MATERIALS = [{"id": 19976, "count": 100, "category": 5}]
MOCK_BANK = [{"id": 19720, "count": 250, "binding": None}]
MOCK_INVENTORY = [None]
MOCK_CHARACTERS = [
    {
        "name": "TestChar",
        "race": "Human",
        "profession": "Guardian",
        "level": 80,
        "gender": "Male",
        "age": 360000,
        "deaths": 100,
        "crafting": [{"discipline": "Artificer", "rating": 400}],
        "bags": [{"inventory": [{"id": 12345, "count": 5, "binding": None}]}],
        "equipment": [{"id": 30684, "slot": "Greatsword"}],
        "guild": None,
    }
]

BASE = "gw2_progression.analyzer"


@pytest.fixture(autouse=True)
def _mock_gw2():
    """Mock all GW2 API calls for the full test session."""
    patches = [
        patch(f"{BASE}.fetch_tokeninfo", AsyncMock(return_value=MOCK_TOKENINFO)),
        patch(f"{BASE}.fetch_account", AsyncMock(return_value=MOCK_ACCOUNT)),
        patch(f"{BASE}.fetch_characters", AsyncMock(return_value=MOCK_CHARACTERS)),
        patch(f"{BASE}.fetch_wallet", AsyncMock(return_value=MOCK_WALLET)),
        patch(f"{BASE}.fetch_bank", AsyncMock(return_value=MOCK_BANK)),
        patch(f"{BASE}.fetch_materials", AsyncMock(return_value=MOCK_MATERIALS)),
        patch(f"{BASE}.fetch_inventory", AsyncMock(return_value=MOCK_INVENTORY)),
        patch(f"{BASE}.fetch_achievements", AsyncMock(return_value=[])),
        patch(f"{BASE}.fetch_masteries", AsyncMock(return_value=[])),
        patch(f"{BASE}.fetch_mastery_points", AsyncMock(return_value={})),
        patch(f"{BASE}.fetch_builds", AsyncMock(return_value=[])),
        patch(f"{BASE}.fetch_guilds", AsyncMock(return_value=[])),
        patch(f"{BASE}.fetch_pvp_stats", AsyncMock(return_value={})),
        patch(f"{BASE}.fetch_pvp_games", AsyncMock(return_value=[])),
        patch(f"{BASE}.fetch_pvp_standings", AsyncMock(return_value=[])),
        patch(f"{BASE}.fetch_tradingpost_current_buys", AsyncMock(return_value=[])),
        patch(f"{BASE}.fetch_tradingpost_current_sells", AsyncMock(return_value=[])),
        patch(f"{BASE}.fetch_unlocked_skins", AsyncMock(return_value=[])),
        patch(f"{BASE}.fetch_unlocked_dyes", AsyncMock(return_value=[])),
        patch(f"{BASE}.fetch_unlocked_minis", AsyncMock(return_value=[])),
        patch(f"{BASE}.fetch_unlocked_finishers", AsyncMock(return_value=[])),
        patch(f"{BASE}.fetch_wvw_stats", AsyncMock(return_value={})),
        # Mock price and listing services
        patch(
            "gw2_progression.services.price_service.fetch_prices",
            AsyncMock(
                return_value={
                    19976: type("PD", (), {"buy_unit_price": 20000, "sell_unit_price": 21600, "buy_quantity": 5000, "sell_quantity": 3000})(),
                    19720: type("PD", (), {"buy_unit_price": 3000, "sell_unit_price": 3500, "buy_quantity": 2000, "sell_quantity": 1500})(),
                }
            ),
        ),
        patch("gw2_progression.services.listing_service.fetch_listings", AsyncMock(return_value={})),
        patch("gw2_progression.database.get_db", AsyncMock()),
        patch("gw2_progression.database.save_account_snapshot", AsyncMock(return_value=1)),
        patch("gw2_progression.database.load_value_history", AsyncMock(return_value=[])),
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


class TestE2EPipeline:
    def test_analyze_returns_account(self):
        resp = client.post("/analyze", json={"api_key": "ABCDEF01-2345-6789-ABCD-EF0123456789AB"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["account_name"] == "E2E.Player.1234"
        assert data["wallet"] is not None
        assert data["materials"] is not None

    def test_value_analyze_returns_summary(self):
        resp = client.post("/value/analyze", json={"api_key": "ABCDEF01-2345-6789-ABCD-EF0123456789AB"})
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert data["summary"]["total_value_buy"] > 0
        assert data["summary"]["wallet_value"] >= 0
        assert data["summary"]["priced_item_count"] >= 2

    def test_value_analyze_has_top_items(self):
        resp = client.post("/value/analyze", json={"api_key": "ABCDEF01-2345-6789-ABCD-EF0123456789AB"})
        data = resp.json()
        assert len(data["top_items"]) > 0
        assert data["top_items"][0]["item_id"] in (19976, 19720, 12345)

    def test_value_analyze_has_breakdown(self):
        resp = client.post("/value/analyze", json={"api_key": "ABCDEF01-2345-6789-ABCD-EF0123456789AB"})
        data = resp.json()
        assert len(data["breakdown"]["by_location"]) > 0

    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("ok", "degraded")

    def test_metrics_endpoint(self):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        assert "requests_total" in data

    def test_resolve_items_empty(self):
        resp = client.post("/resolve", json={"type": "items", "ids": []})
        assert resp.status_code == 200
        assert resp.json() == []
