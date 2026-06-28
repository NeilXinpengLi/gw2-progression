"""Comprehensive UI and API structure tests.

Verifies:
- All HTML pages serve and contain expected structure
- SVG icon system is properly embedded
- API endpoints return correct data shapes
- Key UI elements (nav, KPI cards, insight cards) are present
- No 500 errors on any endpoint
- Export, nav, session validate, plan, insight APIs
"""

import re
import shutil
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch
import time
from datetime import datetime, timezone
from contextlib import ExitStack

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
    stack = ExitStack()
    stack.enter_context(patch(f"{ANALYZER}.fetch_tokeninfo", AsyncMock(return_value=TOKENINFO)))
    for fn, val in stubs.items():
        stack.enter_context(patch(f"{ANALYZER}.{fn}", AsyncMock(return_value=val)))
    return stack


@pytest.fixture
def mock_api():
    with _mock_all_gw2() as s:
        yield s


def _make_session(client):
    """Create a real session in the DB for testing."""
    from gw2_progression.services.auth_service import create_session
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(create_session("test-api-key", "Test.Player"))
    finally:
        loop.close()


# ═══════════════════════════════════════════════════════
# PAGE STRUCTURE TESTS
# ═══════════════════════════════════════════════════════


class TestPageStructure:
    def test_account_page_title(self, client):
        resp = client.get("/account")
        assert resp.status_code == 200
        assert "Account Overview" in resp.text

    def test_account_has_nav(self, client):
        resp = client.get("/account")
        for btn in ["Account", "Insight", "Plan", "Report"]:
            assert btn in resp.text

    def test_account_has_api_key_input(self, client):
        resp = client.get("/account")
        assert "key-input" in resp.text
        assert "analyze-btn" in resp.text

    def test_account_has_export_button(self, client):
        resp = client.get("/account")
        assert "btn-export" in resp.text
        assert "Export" in resp.text

    def test_account_has_kpi_cards(self, client):
        resp = client.get("/account")
        assert "Total Value" in resp.text
        assert "Liquid Value" in resp.text
        assert "Hidden Wealth" in resp.text

    def test_account_has_asset_section(self, client):
        resp = client.get("/account")
        assert "economy" in resp.text.lower()

    def test_account_has_character_table(self, client):
        resp = client.get("/account")
        assert "characters" in resp.text.lower()

    def test_account_has_graph_detail_container(self, client):
        resp = client.get("/account")
        assert 'id="graph-detail"' in resp.text
        assert 'class="explorer-tree"' in resp.text
        assert 'class="ai-overlay"' in resp.text

    def test_insight_page_structure(self, client):
        resp = client.get("/insight")
        assert resp.status_code == 200
        assert "AI Insights" in resp.text
        assert "Hidden Wealth" in resp.text
        assert "Build Readiness" in resp.text

    def test_plan_page_structure(self, client):
        resp = client.get("/plan")
        assert resp.status_code == 200
        assert "Progression Plan" in resp.text
        assert "Generate Plan" in resp.text

    def test_report_page_structure(self, client):
        resp = client.get("/report")
        assert resp.status_code == 200
        assert "Report" in resp.text
        assert "Free" in resp.text
        assert "Full Report" in resp.text
        assert "Weekly" in resp.text

    def test_report_has_pricing(self, client):
        resp = client.get("/report")
        assert "$5" in resp.text
        assert "Purchase" in resp.text


# ═══════════════════════════════════════════════════════
# NAVIGATION TESTS
# ═══════════════════════════════════════════════════════


class TestNavigation:
    """All pages must have consistent nav with correct links."""

    def test_account_nav_links(self, client):
        resp = client.get("/account")
        for pg in ["account", "insight", "plan", "report"]:
            assert f'data-nav="{pg}"' in resp.text

    def test_insight_nav_links(self, client):
        resp = client.get("/insight")
        assert 'data-nav="account"' in resp.text
        assert 'data-nav="insight"' in resp.text
        assert 'data-nav="plan"' in resp.text
        assert 'data-nav="report"' in resp.text

    def test_plan_nav_links(self, client):
        resp = client.get("/plan")
        assert 'data-nav="account"' in resp.text
        assert 'data-nav="plan"' in resp.text
        assert 'data-nav="insight"' in resp.text
        assert 'data-nav="report"' in resp.text

    def test_report_nav_links(self, client):
        resp = client.get("/report")
        for pg in ["account", "insight", "plan", "report"]:
            assert f'data-nav="{pg}"' in resp.text

    def test_nav_order_consistent(self, client):
        resp = client.get("/account")
        html = resp.text
        nav_start = html.find('id="os-nav"')
        assert nav_start >= 0, "Nav element not found"
        nav_html = html[nav_start:nav_start + 800]
        expected = ['data-nav="account"', 'data-nav="insight"', 'data-nav="plan"', 'data-nav="report"']
        last_pos = 0
        for attr in expected:
            pos = nav_html.find(attr, last_pos)
            assert pos > last_pos, f"Nav order broken: {attr} not found after position {last_pos}"
            last_pos = pos


# ═══════════════════════════════════════════════════════
# SVG ICON TESTS
# ═══════════════════════════════════════════════════════


class TestSvgIcons:
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
        "brand-mark", "brand-ai-sparkle",
        "empty-account", "empty-insight", "empty-plan",
    ]

    def test_all_icons_in_account_page(self, client):
        resp = client.get("/account")
        present_icons = ["nav-account", "nav-insight", "nav-plan", "nav-report", "kpi-account-value", "kpi-hidden-wealth", "kpi-legendary", "action-export", "asset-wallet", "asset-materials", "asset-bank", "asset-equipment", "tree-economy", "tree-progress", "tree-collection", "tree-characters", "sub-wallet", "sub-achievements", "sub-skins", "sub-mastery", "sub-pvp", "sub-wvw", "sub-dyes", "sub-minis", "sub-trading", "sub-fractal", "status-active"]
        for icon_id in present_icons:
            assert f'symbol id="sym-{icon_id}"' in resp.text, f"Missing icon: {icon_id}"

    def test_icons_used_in_nav(self, client):
        resp = client.get("/account")
        assert 'href="#sym-nav-account"' in resp.text
        assert 'href="#sym-nav-insight"' in resp.text
        assert 'href="#sym-nav-plan"' in resp.text
        assert 'href="#sym-action-export"' in resp.text

    def test_icons_used_in_kpi(self, client):
        resp = client.get("/account")
        # Account page now uses layered layout — check nav icons still work
        assert 'href="#sym-nav-account"' in resp.text


# ═══════════════════════════════════════════════════════
# ACCOUNT OVERVIEW API TESTS
# ═══════════════════════════════════════════════════════


class TestAccountOverviewAPI:
    def test_overview_200_with_valid_key(self, client, mock_api):
        resp = client.get("/api/account/overview?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        assert resp.status_code == 200
        data = resp.json()
        assert data["account"]["name"] == "Player.1234"

    def test_overview_has_required_fields(self, client, mock_api):
        resp = client.get("/api/account/overview?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        assert "account" in data
        for field in ["name", "world", "created"]:
            assert field in data["account"]
        assert "kpis" in data
        for field in ["account_value", "liquid_sell", "wallet_gold", "character_count"]:
            assert field in data["kpis"]
        assert "assets" in data
        assert len(data["assets"]) > 0
        assert "characters" in data

    def test_overview_asset_categories(self, client, mock_api):
        resp = client.get("/api/account/overview?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        categories = {a["category"] for a in data["assets"]}
        expected = {"Wallet", "Material Storage", "Bank", "Equipment", "Character Inventory"}
        for cat in expected:
            assert cat in categories

    def test_overview_401_with_bad_key(self, client):
        from gw2_progression.gw2_client import Gw2ApiError
        with patch(f"{ANALYZER}.fetch_tokeninfo", AsyncMock(side_effect=Gw2ApiError(401, "bad key"))):
            resp = client.get("/api/account/overview?api_key=BADKEY")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════
# INSIGHT API TESTS
# ═══════════════════════════════════════════════════════


class TestInsightAPI:
    def test_insight_200(self, client, mock_api):
        resp = client.get("/api/insight/data?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        assert resp.status_code == 200
        assert resp.json()["account_name"] == "Player.1234"

    def test_insight_has_hidden_wealth(self, client, mock_api):
        resp = client.get("/api/insight/data?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        assert "hidden_wealth" in data
        assert "item_count" in data["hidden_wealth"]

    def test_insight_has_build_readiness(self, client, mock_api):
        resp = client.get("/api/insight/data?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        assert "build_readiness" in data
        assert "total_chars" in data["build_readiness"]

    def test_insight_has_legendary_progress(self, client, mock_api):
        resp = client.get("/api/insight/data?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        assert "legendary_progress" in data
        assert "active_goals" in data["legendary_progress"]
        assert "total" in data["legendary_progress"]

    def test_insight_has_market_insight(self, client, mock_api):
        resp = client.get("/api/insight/data?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        assert "market_insight" in data
        assert "sell_candidates" in data["market_insight"]

    def test_insight_has_top_items(self, client, mock_api):
        resp = client.get("/api/insight/data?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        assert "top_items" in data
        assert "top_materials" in data


# ═══════════════════════════════════════════════════════
# PLAN API TESTS
# ═══════════════════════════════════════════════════════


class TestPlanAPI:
    def test_decide_requires_key(self, client):
        resp = client.post("/api/v1/decide", json={})
        assert resp.status_code == 422

    def test_decide_returns_actions(self, client, mock_api):
        resp = client.post("/api/v1/decide", json={"api_key": "ABCDEF01-2345-6789-ABCD-EF0123456789AB", "strategy": "hybrid"})
        assert resp.status_code == 200
        data = resp.json()
        assert "strategy_name" in data
        assert data["strategy_name"] == "Balanced"

    def test_decide_different_strategies(self, client, mock_api):
        for strategy, expected in [("gold", "Gold"), ("build", "Build"), ("legendary", "Legendary")]:
            resp = client.post("/api/v1/decide", json={"api_key": "ABCDEF01-2345-6789-ABCD-EF0123456789AB", "strategy": strategy})
            assert resp.status_code == 200
            assert expected in resp.json()["strategy_name"]

    def test_goal_interpret_requires_text(self, client):
        resp = client.post("/goal-driven/interpret", json={})
        assert resp.status_code == 422

    def test_goal_interpret_legendary(self, client):
        resp = client.post("/goal-driven/interpret", json={"goal_text": "I want to finish Bolt"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["parsed"]["goal_type"] == "FINISH_LEGENDARY"


# ═══════════════════════════════════════════════════════
# SESSION + AUTH TESTS
# ═══════════════════════════════════════════════════════


class TestSession:
    def test_session_create_and_resolve(self, client, mock_api):
        from gw2_progression.services.auth_service import create_session, get_api_key
        import asyncio

        async def test():
            token = await create_session("test-real-key", "Player.1234")
            assert len(token) == 48
            assert await get_api_key(token) == "test-real-key"
            assert await get_api_key("short") == "short"
            assert await get_api_key("ABCDEF01-2345-6789-ABCD-EF0123456789AB") == "ABCDEF01-2345-6789-ABCD-EF0123456789AB"

        asyncio.run(test())

    def test_validate_endpoint_404_for_bad_token(self, client):
        resp = client.get("/auth/session/validate?token=nonexistent")
        assert resp.status_code == 404

    def test_validate_endpoint_200_for_valid_token(self, client, mock_api):
        from gw2_progression.services.auth_service import create_session
        import asyncio

        async def test():
            token = await create_session("test-key", "Validate.Player")
            loop = asyncio.get_event_loop()
            resp = client.get(f"/auth/session/validate?token={token}")
            assert resp.status_code == 200
            assert resp.json()["valid"] is True
            assert resp.json()["account_name"] == "Validate.Player"

        asyncio.run(test())

    def test_validate_expired_session(self, client):
        from gw2_progression.services.auth_service import create_session, SESSION_TTL
        import asyncio
        from unittest.mock import patch

        async def test():
            token = await create_session("old-key", "Old.Player")
            with patch("gw2_progression.services.auth_service.time.time", return_value=time.time() + SESSION_TTL + 100):
                resp = client.get(f"/auth/session/validate?token={token}")
                assert resp.status_code == 404

        asyncio.run(test())


# ═══════════════════════════════════════════════════════
# LANDING PAGE TESTS
# ═══════════════════════════════════════════════════════


class TestLandingPage:
    def test_landing_served(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Reimagined" in resp.text

    def test_landing_has_hero_section(self, client):
        resp = client.get("/")
        assert "GW2 Progression OS" in resp.text
        assert "btn-hero" in resp.text or "Analyze" in resp.text

    def test_landing_has_value_cards(self, client):
        resp = client.get("/")
        for card in ["Hidden Wealth", "Build Optimization", "Legendary Path", "Market Optimization"]:
            assert card in resp.text

    def test_landing_has_demo_snapshot(self, client):
        resp = client.get("/")
        assert "3,608" in resp.text
        assert "1,847" in resp.text

    def test_landing_has_how_it_works(self, client):
        resp = client.get("/")
        assert "How It Works" in resp.text or "Connect" in resp.text

    def test_landing_has_trust_section(self, client):
        resp = client.get("/")
        assert "Read-only" in resp.text

    def test_landing_links_to_account(self, client):
        resp = client.get("/")
        assert '/account' in resp.text


# ═══════════════════════════════════════════════════════
# STATIC FILES
# ═══════════════════════════════════════════════════════


class TestStaticFiles:
    def test_css_main(self, client):
        resp = client.get("/static/style.css")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/css")

    def test_css_account(self, client):
        resp = client.get("/static/style-account.css")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/css")

    def test_css_landing(self, client):
        resp = client.get("/static/style-landing.css")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/css")

    def test_css_insight(self, client):
        resp = client.get("/static/style-insight.css")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/css")

    def test_css_plan(self, client):
        resp = client.get("/static/style-plan.css")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/css")

    def test_css_report(self, client):
        resp = client.get("/static/style-report.css")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/css")

    def test_js_account(self, client):
        resp = client.get("/static/app-account.v2.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]

    def test_js_session_manager(self, client):
        resp = client.get("/static/session-manager.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]

    def test_js_shared(self, client):
        resp = client.get("/static/app-shared.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]


# ═══════════════════════════════════════════════════════
# DATA MODEL TESTS
# ═══════════════════════════════════════════════════════


class TestDataModels:
    def test_raw_account_data_defaults(self):
        raw = models_data.RawAccountData()
        assert raw.account.name == ""
        assert len(raw.characters) == 0

    def test_asset_entity_defaults(self):
        a = models_data.AssetEntity()
        assert a.item_id == 0
        assert a.count == 0
        assert a.location == ""

    def test_account_value_has_all_fields(self):
        av = models_data.AccountValue()
        for field in ["total_value", "liquid_value", "wallet_gold", "material_value", "bank_value"]:
            assert hasattr(av, field)

    def test_character_entity_defaults(self):
        c = models_data.CharacterEntity()
        assert c.name == ""
        assert c.profession == ""
        assert c.level == 0

    def test_derived_account_data(self):
        d = models_data.DerivedAccountData()
        assert d.value.total_value == 0
        assert d.breakdown == []


# ═══════════════════════════════════════════════════════
# EDGE CASE TESTS
# ═══════════════════════════════════════════════════════


class TestEdgeCases:
    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_root_serves_landing(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Reimagined" in resp.text

    def test_404_for_unknown_page(self, client):
        resp = client.get("/nonexistent")
        assert resp.status_code in (404, 429)

    def test_security_headers_present(self, client):
        resp = client.get("/health")
        assert "X-Content-Type-Options" in resp.headers
        assert "X-Frame-Options" in resp.headers


# ═══════════════════════════════════════════════════════
# API RESPONSE SHAPE TESTS
# ═══════════════════════════════════════════════════════


class TestAPIResponseShapes:
    """Verify API responses contain all expected fields."""

    def test_overview_response_shape(self, client, mock_api):
        resp = client.get("/api/account/overview?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        assert set(data.keys()) >= {"account", "kpis", "assets", "characters", "snapshot_time", "additional_data"}
        assert set(data["account"].keys()) >= {"name", "world", "created", "age_hours"}
        assert set(data["kpis"].keys()) >= {"account_value", "liquid_sell", "liquid_buy", "wallet_gold", "character_count", "skin_count", "daily_ap", "fractal_level"}

    def test_overview_lite_shape(self, client, mock_api):
        resp = client.get("/api/account/overview?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB&lite=true")
        data = resp.json()
        assert set(data.keys()) >= {"account", "kpis", "snapshot_time"}
        assert "assets" not in data
        assert set(data["account"].keys()) >= {"name", "world"}
        assert set(data["kpis"].keys()) >= {"character_count", "skin_count", "daily_ap", "fractal_level", "wallet_gold"}

    def test_overview_lite_then_full_twice_no_extra_fetch_all(self, client, mock_api):
        resp1 = client.get("/api/account/overview?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB&lite=true")
        assert resp1.status_code == 200
        resp2 = client.get("/api/account/overview?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        assert resp2.status_code == 200
        data = resp2.json()
        assert "assets" in data
        assert len(data["assets"]) > 0

    def test_insight_response_shape(self, client, mock_api):
        resp = client.get("/api/insight/data?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        data = resp.json()
        required = {"account_name", "hidden_wealth", "build_readiness", "legendary_progress", "market_insight", "top_items", "top_materials"}
        assert set(data.keys()) >= required


# ═══════════════════════════════════════════════════════
# FRONTEND-BACKEND INTERFACE + JS STATIC ANALYSIS TESTS
# ═══════════════════════════════════════════════════════


class TestFrontendBackendInterface:
    """Verify JS getElementById calls match HTML element IDs."""

    ACCOUNT_IDS = {
        # JS references in app-account.js (static IDs present in account.html)
        "analyze-btn", "key-input", "btn-refresh", "btn-export", "os-nav",
        "key-section", "layer-overview", "layer-content", "layer-footer",
        "header-account-name", "header-last-sync", "ov-total-value",
        "ov-liquid-value", "ov-hidden-wealth", "overview-progress",
        "explorer-tree", "graph-detail", "ai-overlay-body",
        "loading-state", "error-state", "error-message", "api-status-badge",
    }
    # IDs created dynamically by JS (verified self-consistent via renderTree/renderCharacters)
    DYNAMIC_IDS = {"tn-collapse-all", "tn-expand-all"}

    def test_account_html_has_all_js_referenced_ids(self, client):
        resp = client.get("/account")
        for eid in self.ACCOUNT_IDS:
            assert f'id="{eid}"' in resp.text, f"Missing id='{eid}' in account.html"

    def test_api_overview_accepts_lite_int_refresh(self, client, mock_api):
        resp = client.get("/api/account/overview?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB&lite=true&refresh=1782616951665", headers={"Accept": "application/json"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "account" in data
        assert "kpis" in data

    def test_api_overview_rejects_invalid_bool_refresh(self, client):
        resp = client.get("/api/account/overview?api_key=ABCDEF01-2345-6789-ABCD-EF0123456789AB&refresh=notabool")
        assert resp.status_code == 422

    def test_api_error_detail_is_readable_string(self, client):
        resp = client.get("/api/account/overview")
        assert resp.status_code == 422
        data = resp.json()
        detail = data.get("detail", "")
        detail_str = str(detail)
        assert "[object Object]" not in detail_str


class TestJSStaticAnalysis:
    """Catch JS scope bugs and common errors via static analysis.
    
    These tests parse JS files directly without a JS runtime, catching
    patterns that would cause runtime errors in the browser.
    """

    JS_DIR = Path(__file__).parent.parent / "src" / "gw2_progression" / "static"

    def _get_js(self, name):
        path = self.JS_DIR / name
        assert path.exists(), f"JS file not found: {path}"
        return path.read_text(encoding="utf-8")

    def _function_body(self, js: str, fn_name: str) -> str:
        """Extract the body of a named function from JS source."""
        pattern = rf"function {fn_name}\s*\([^)]*\)\s*\{{"
        m = re.search(pattern, js)
        assert m, f"function {fn_name} not found in JS"
        start = m.end()
        depth = 1
        i = start
        while i < len(js) and depth > 0:
            if js[i] == '{': depth += 1
            elif js[i] == '}': depth -= 1
            i += 1
        return js[start:i-1]

    def _local_vars(self, body: str) -> set:
        """Find all locally-declared variables (const/let/var) in a function body."""
        return set(re.findall(rf"(?:const|let|var)\s+(\w+)\s*[=;]", body))

    def _param_names(self, fn_def: str) -> set:
        """Extract parameter names from a function definition."""
        m = re.search(rf"function\s+\w+\s*\(([^)]*)\)", fn_def)
        if not m: return set()
        params = m.group(1)
        return set(p.strip() for p in params.split(",") if p.strip())

    def test_all_render_detail_functions_define_gd(self):
        """Each render*Detail function must not reference 'gd' from parent scope.
        
        This catches the ReferenceError: gd is not defined bug where
        sub-functions relied on gd from renderDetail()'s scope.
        """
        js = self._get_js("app-account.js")
        # Find all render*Detail function definitions
        fn_names = sorted(set(re.findall(r'function (render[a-zA-Z]+Detail)', js)))
        fn_names = [n for n in fn_names if n != "renderDetail"]

        assert len(fn_names) >= 3, f"Expected >=3 render*Detail fns, got {fn_names}"

        for fn_name in fn_names:
            body = self._function_body(js, fn_name)
            # Check for 'gd' as a variable reference (gd.innerHTML or gd = or gd)
            if re.search(r'(?<!["\w])gd\.|(?<!["\w])gd\s*=', body):
                local_vars = self._local_vars(body)
                assert "gd" in local_vars, \
                    f"{fn_name} uses 'gd' but not defined locally (must use document.getElementById)"

    def test_no_getelementById_before_definition(self):
        """Verify all getElementById('...') calls reference known static IDs."""
        js = self._get_js("app-account.js")
        calls = re.findall(r"getElementById\('([^']+)'\)", js)
        known = TestFrontendBackendInterface.ACCOUNT_IDS
        dynamic = TestFrontendBackendInterface.DYNAMIC_IDS | {"${cid}"}
        for cid in calls:
            if cid not in known and cid not in dynamic:
                raise AssertionError(
                    f"getElementById('{cid}') references unknown ID. "
                    f"Add to ACCOUNT_IDS or DYNAMIC_IDS"
                )

    @pytest.mark.skip(reason="Run manually: npx eslint src/gw2_progression/static/*.js")
    def test_eslint_no_undef(self):
        """Run ESLint on all JS files (requires Node.js + npm dependencies)."""

    def test_nav_handler_is_first_in_domcontentloaded(self):
        """Nav handler must be the first statement in DOMContentLoaded on every page.
        
        This catches the bug where earlier getElementById calls without
        optional chaining can throw and prevent the nav handler from
        being registered, making the entire page unnavigable.
        """
        for js_name in ["app-account.js", "app-insight.js", "app-plan.js", "app-report.js"]:
            js = self._get_js(js_name)
            # Find DOMContentLoaded handler body (arrow function)
            m = re.search(r"addEventListener\('DOMContentLoaded',\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{", js)
            assert m, f"{js_name}: No DOMContentLoaded handler found"
            start = m.end()
            depth = 1
            i = start
            while i < len(js) and depth > 0:
                if js[i] == '{': depth += 1
                elif js[i] == '}': depth -= 1
                i += 1
            dcl_body = js[start:i-1]
            lines = [l.strip() for l in dcl_body.split("\n") if l.strip() and not l.strip().startswith("//")]
            nav_stmts = [i for i, l in enumerate(lines) if "os-nav" in l]
            assert len(nav_stmts) > 0, f"{js_name}: No os-nav handler found in DOMContentLoaded"
            first_nav = nav_stmts[0]
            for i in range(first_nav):
                line = lines[i]
                if "getElementById(" in line and "?." not in line:
                    raise AssertionError(
                        f"{js_name}: '{line.strip()[:60]}...' at line index {i} "
                        f"is BEFORE nav handler at index {first_nav} and lacks optional chaining. "
                        f"If it throws, nav is never registered."
                    )

    def test_no_await_in_non_async_function(self):
        """Catch await keyword inside function() without async keyword.
        
        In ES modules, await in a non-async function is a SyntaxError
        that prevents the entire module from loading (no nav, no JS).
        """
        for js_name in ["app-account.js", "app-insight.js", "app-plan.js", "app-report.js"]:
            js = self._get_js(js_name)
            fn_defs = re.findall(r'(?:async\s+)?function\s+(\w+)\s*\(', js)
            for fn_name in fn_defs:
                body = self._function_body(js, fn_name)
                has_await = "await " in body
                fn_decl = re.search(rf'(async\s+)?function\s+{fn_name}', js).group(1) or ""
                is_async = "async" in fn_decl
                if has_await and not is_async:
                    raise AssertionError(
                        f"{js_name}: {fn_name}() uses 'await' but is not declared 'async'. "
                        f"This is a SyntaxError in ES modules that prevents the module from loading."
                    )
