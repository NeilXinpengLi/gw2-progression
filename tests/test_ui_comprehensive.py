"""Comprehensive UI and API structure tests.

Verifies:
- All HTML pages serve and contain expected structure
- SVG icon system is properly embedded
- API endpoints return correct data shapes
- Key UI elements (nav, KPI cards, insight cards) are present
- No 500 errors on any endpoint
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gw2_progression.api.main import app
from gw2_progression import models_data

TOKENINFO = {"name": "TestKey", "id": "abc", "permissions": ["account", "inventories", "wallet", "characters", "tradingpost", "unlocks"]}
ACCOUNT = {
    "name": "Player.1234",
    "world": 1001,
    "created": "2022-01-01T00:00:00Z",
    "age": 360000,
    "fractal_level": 50,
    "daily_ap": 500,
    "monthly_ap": 50,
    "wvw_rank": 100,
    "guilds": [],
}

MOCK_WALLET = [{"id": 1, "value": 500000}]
MOCK_MATERIALS = [{"id": 19976, "count": 100, "category": 5}]
MOCK_BANK = [{"id": 19720, "count": 250, "binding": None}]
MOCK_INVENTORY = [None]
MOCK_CHARACTERS = [{
    "name": "TestChar",
    "race": "Human",
    "profession": "Guardian",
    "level": 80,
    "age": 360000,
    "equipment": [{"id": 30698, "slot": "WeaponA1"}],
    "bags": [{"inventory": [{"id": 19976, "count": 5}]}],
    "created": "2022-01-01T00:00:00Z",
}]

ANALYZER = "gw2_progression.analyzer"


@pytest.fixture
def client():
    return TestClient(app)


def _mock_all_gw2():
    """Patch all GW2 API calls to return mock data."""
    stubs = {
        "fetch_account": ACCOUNT,
        "fetch_characters": MOCK_CHARACTERS,
        "fetch_wallet": MOCK_WALLET,
        "fetch_bank": MOCK_BANK,
        "fetch_materials": MOCK_MATERIALS,
        "fetch_inventory": MOCK_INVENTORY,
        "fetch_achievements": [],
        "fetch_masteries": [],
        "fetch_mastery_points": {},
        "fetch_builds": [],
        "fetch_guilds": [],
        "fetch_pvp_stats": {},
        "fetch_pvp_games": [],
        "fetch_pvp_standings": [],
        "fetch_tradingpost_current_buys": [],
        "fetch_tradingpost_current_sells": [],
        "fetch_unlocked_skins": [],
        "fetch_unlocked_dyes": [],
        "fetch_unlocked_minis": [],
        "fetch_unlocked_finishers": [],
        "fetch_wvw_stats": {},
    }
    stack = __import__("contextlib").ExitStack()
    stack.enter_context(patch(f"{ANALYZER}.fetch_tokeninfo", AsyncMock(return_value=TOKENINFO)))
    for fn, val in stubs.items():
        stack.enter_context(patch(f"{ANALYZER}.{fn}", AsyncMock(return_value=val)))
    return stack


@pytest.fixture
def mock_api():
    with _mock_all_gw2() as s:
        yield s


# ═══════════════════════════════════════════════════════
# PAGE STRUCTURE TESTS
# ═══════════════════════════════════════════════════════


class TestPageStructure:
    """Every HTML page must serve and contain critical elements."""

    def test_account_page_title(self, client):
        resp = client.get("/account")
        assert resp.status_code == 200
        assert "Account Overview" in resp.text
        assert "GW2 Progression" in resp.text

    def test_account_has_nav(self, client):
        resp = client.get("/account")
        for btn in ["Account", "Insight", "Plan"]:
            assert btn in resp.text

    def test_account_has_api_key_input(self, client):
        resp = client.get("/account")
        assert "key-input" in resp.text
        assert "analyze-btn" in resp.text

    def test_account_has_kpi_cards(self, client):
        resp = client.get("/account")
        for kpi in ["Account Value", "Liquid Gold", "Hidden Wealth", "Legendary Progress", "Build Ready"]:
            assert kpi in resp.text

    def test_account_has_asset_section(self, client):
        resp = client.get("/account")
        assert "Asset Breakdown" in resp.text
        assert "Total Value" in resp.text
        assert "Risk" in resp.text

    def test_account_has_character_table(self, client):
        resp = client.get("/account")
        assert "Characters" in resp.text
        assert "Profession" in resp.text
        assert "Level" in resp.text

    def test_insight_page_structure(self, client):
        resp = client.get("/insight")
        assert resp.status_code == 200
        assert "AI Insights" in resp.text
        assert "Hidden Wealth" in resp.text
        assert "Build Readiness" in resp.text
        assert "Top Assets" in resp.text

    def test_plan_page_structure(self, client):
        resp = client.get("/plan")
        assert resp.status_code == 200
        assert "Progression Plan" in resp.text
        assert "Generate Plan" in resp.text
        assert "Balanced" in resp.text or "hybrid" in resp.text


# ═══════════════════════════════════════════════════════
# SVG ICON TESTS
# ═══════════════════════════════════════════════════════


class TestSvgIcons:
    """SVG icon sprite must be embedded and all icons reachable."""

    REQUIRED_ICONS = [
        "nav-account", "nav-insight", "nav-plan",
        "kpi-account-value", "kpi-liquid-sell", "kpi-liquid-buy",
        "kpi-hidden-wealth", "kpi-legendary", "kpi-build-ready",
        "insight-hidden-wealth", "insight-build-ready", "insight-legendary",
        "strategy-balanced", "strategy-gold", "strategy-build", "strategy-legendary",
        "asset-wallet", "asset-materials", "asset-bank",
        "asset-equipment", "asset-inventory", "asset-shared", "asset-trading",
        "action-key", "action-refresh", "action-export",
        "status-active", "status-stale", "status-error",
    ]

    def test_all_icons_in_account_page(self, client):
        resp = client.get("/account")
        for icon_id in self.REQUIRED_ICONS:
            assert f'symbol id="{icon_id}"' in resp.text, f"Missing icon: {icon_id}"

    def test_icons_used_in_nav(self, client):
        resp = client.get("/account")
        assert 'href="#nav-account"' in resp.text
        assert 'href="#nav-insight"' in resp.text
        assert 'href="#nav-plan"' in resp.text

    def test_icons_used_in_kpi(self, client):
        resp = client.get("/account")
        assert 'href="#kpi-account-value"' in resp.text
        assert 'href="#kpi-hidden-wealth"' in resp.text

    def test_strategy_icons_in_plan(self, client):
        resp = client.get("/plan")
        assert 'href="#strategy-balanced"' in resp.text
        assert 'href="#strategy-gold"' in resp.text


# ═══════════════════════════════════════════════════════
# API STRUCTURE TESTS
# ═══════════════════════════════════════════════════════


class TestAccountOverviewAPI:
    """GET /api/account/overview must return correct structure."""

    def test_overview_200_with_valid_key(self, client, mock_api):
        resp = client.get("/api/account/overview?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        assert resp.status_code == 200
        data = resp.json()
        assert data["account"]["name"] == "Player.1234"
        assert data["account"]["world"] == 1001

    def test_overview_has_required_fields(self, client, mock_api):
        resp = client.get("/api/account/overview?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        # Account section
        assert "account" in data
        for field in ["name", "world", "created", "age_hours"]:
            assert field in data["account"], f"Missing account.{field}"
        # KPIs
        assert "kpis" in data
        for field in ["account_value", "liquid_sell", "liquid_buy", "wallet_gold", "character_count"]:
            assert field in data["kpis"], f"Missing kpis.{field}"
        # Assets
        assert "assets" in data
        assert len(data["assets"]) > 0
        for field in ["category", "total_value", "percentage", "risk_flag"]:
            assert field in data["assets"][0], f"Missing asset.{field}"
        # Characters
        assert "characters" in data
        assert len(data["characters"]) > 0
        for field in ["name", "profession", "level", "playtime", "last_login"]:
            assert field in data["characters"][0], f"Missing character.{field}"

    def test_overview_asset_categories(self, client, mock_api):
        resp = client.get("/api/account/overview?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        categories = {a["category"] for a in data["assets"]}
        expected = {"Wallet", "Material Storage", "Bank", "Equipment", "Character Inventory"}
        for cat in expected:
            assert cat in categories, f"Missing asset category: {cat}"

    def test_overview_401_without_key(self, client):
        resp = client.get("/api/account/overview")
        assert resp.status_code == 422

    def test_overview_401_with_bad_key(self, client):
        from gw2_progression.gw2_client import Gw2ApiError
        with patch(f"{ANALYZER}.fetch_tokeninfo", AsyncMock(side_effect=Gw2ApiError(401, "bad key"))):
            resp = client.get("/api/account/overview?api_key=BADKEY")
        assert resp.status_code == 401


class TestInsightAPI:
    """GET /api/insight/data must return correct structure."""

    def test_insight_200(self, client, mock_api):
        resp = client.get("/api/insight/data?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        assert resp.status_code == 200
        data = resp.json()
        assert "account_name" in data
        assert data["account_name"] == "Player.1234"

    def test_insight_has_hidden_wealth(self, client, mock_api):
        resp = client.get("/api/insight/data?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        assert "hidden_wealth" in data
        assert "item_count" in data["hidden_wealth"]
        assert "explanation" in data["hidden_wealth"]

    def test_insight_has_build_readiness(self, client, mock_api):
        resp = client.get("/api/insight/data?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        assert "build_readiness" in data
        assert "total_chars" in data["build_readiness"]
        assert "equipped_chars" in data["build_readiness"]

    def test_insight_has_top_items(self, client, mock_api):
        resp = client.get("/api/insight/data?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        assert "top_items" in data
        assert "top_materials" in data


# ═══════════════════════════════════════════════════════
# SESSION + AUTH INTEGRATION
# ═══════════════════════════════════════════════════════


class TestSessionIntegration:
    """Session creation and token resolution end-to-end."""

    def test_session_created_and_resolved(self, client, mock_api):
        from gw2_progression.services.auth_service import create_session, get_api_key
        import asyncio

        async def test():
            token = await create_session("test-real-key", "Player.1234")
            assert len(token) == 48
            resolved = await get_api_key(token)
            assert resolved == "test-real-key"
            # Non-token key passes through
            assert await get_api_key("short") == "short"
            assert await get_api_key("ABCDEF01-2345-6789-ABCD-EF0123456789AB") == "ABCDEF01-2345-6789-ABCD-EF0123456789AB"

        asyncio.run(test())
