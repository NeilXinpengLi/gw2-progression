"""Playwright E2E browser tests with page.route() API mocking."""

import json
import socket
import threading
import time
import urllib.request

import pytest


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


SERVER_PORT = _free_port()
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"

MOCK_SESSION = json.dumps({"token": "mock-token", "account_name": "P.Player", "expires_in": 86400})
MOCK_EMPTY = json.dumps({})
MOCK_ANALYZE = json.dumps(
    {
        "account_name": "Playwright.Player",
        "account_world": 1001,
        "characters": [{"name": "TestChar", "profession": "Guardian", "level": 80, "equipment": [], "bags": [], "crafting": [], "deaths": 0, "age": 1000}],
        "wallet": [{"id": 1, "value": 500000}],
        "bank": [],
        "materials": [],
        "inventory": [],
        "unlocked_skins": [],
        "unlocked_dyes": [],
        "unlocked_minis": [],
        "unlocked_finishers": [],
        "masteries": [],
        "mastery_points": {},
        "pvp_stats": {},
        "pvp_games": [],
        "pvp_standings": [],
        "builds": [],
        "guilds": [],
        "wvw_stats": {},
        "errors": {},
    }
)
MOCK_VALUE = json.dumps(
    {
        "summary": {"total_value_buy": 2000000, "wallet_value": 500000, "reliable_value": 1500000, "priced_item_count": 10},
        "top_items": [],
        "holdings": [],
        "breakdown": {"by_location": []},
        "history": [],
        "warnings": [],
    }
)


def _run_server():
    import uvicorn

    from gw2_progression.api.main import app

    uvicorn.run(app, host="127.0.0.1", port=SERVER_PORT, log_level="error")


@pytest.fixture(scope="module")
def live_server():
    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()
    for _ in range(20):
        try:
            urllib.request.urlopen(f"{BASE_URL}/health", timeout=2)
            break
        except Exception:
            time.sleep(1)
    yield BASE_URL


def _mock_route(route, request):
    url, method = request.url, request.method

    if url.endswith("/auth/session") and method == "POST":
        route.fulfill(status=200, content_type="application/json", body=MOCK_SESSION)
    elif url.endswith("/auth/sessions") and method == "GET":
        route.fulfill(status=200, content_type="application/json", body=f"[{MOCK_SESSION}]")
    elif "/value/analyze" in url and method == "POST":
        route.fulfill(status=200, content_type="application/json", body=MOCK_VALUE)
    elif url.endswith("/analyze") and method == "POST":
        route.fulfill(status=200, content_type="application/json", body=MOCK_ANALYZE)
    elif "/resolve" in url and method == "POST":
        route.fulfill(status=200, content_type="application/json", body="[]")
    elif "/progression/templates" in url or "/templates" in url:
        route.fulfill(status=200, content_type="application/json", body='[{"template_id":"test","name":"Test","goal_type":"legendary_weapon"}]')
    else:
        route.continue_()


@pytest.fixture(autouse=True)
def _setup_mocks(page):
    page.route("**/*", _mock_route)
    yield


class TestPlaywrightUI:
    def _goto(self, page):
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)

    def test_page_loads(self, page, live_server):
        self._goto(page)
        assert page.title() == "GW Progression"

    def test_key_input_visible(self, page, live_server):
        self._goto(page)
        assert page.is_visible("#key-input")

    def test_analyze_button_visible(self, page, live_server):
        self._goto(page)
        assert page.is_visible("#analyze-btn")

    def test_dark_theme(self, page, live_server):
        self._goto(page)
        bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
        rgb = [int(x) for x in bg.replace("rgb(", "").replace(")", "").split(", ")]
        assert sum(rgb) < 100

    def test_analyze_then_tab_navigation(self, page, live_server):
        """Full flow: page load → enter key → analyze → see tabs → navigate."""
        self._goto(page)
        page.fill("#key-input", "ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        page.click("#analyze-btn")
        # Wait for results to be visible (hidden class removed)
        page.wait_for_selector("#results:not(.hidden)", timeout=20000)
        assert page.is_visible("#overview-cards")
        # Now tabs should be visible
        page.wait_for_selector("#nav-tabs:not(.hidden)", timeout=5000)
        # Click Value tab
        page.click('button[data-tab="value"]')
        assert page.is_visible("#tab-value")
        # Click Crafting tab
        page.click('button[data-tab="crafting"]')
        assert page.is_visible("#craft-btn")

    def test_analyze_shows_overview_cards(self, page, live_server):
        self._goto(page)
        page.fill("#key-input", "ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        page.click("#analyze-btn")
        page.wait_for_selector("#results:not(.hidden)", timeout=20000)
        assert page.is_visible("#overview-cards")

    def test_settings_tab_has_credential_form(self, page, live_server):
        self._goto(page)
        page.fill("#key-input", "ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        page.click("#analyze-btn")
        page.wait_for_selector("#results:not(.hidden)", timeout=20000)
        page.click('button[data-tab="settings"]')
        assert page.is_visible("#cred-provider")
        assert page.is_visible("#cred-key")
        assert page.is_visible("#cred-save-btn")

    def test_products_tab_exists(self, page, live_server):
        self._goto(page)
        page.fill("#key-input", "ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        page.click("#analyze-btn")
        page.wait_for_selector("#results:not(.hidden)", timeout=20000)
        page.click('button[data-tab="products"]')
        assert page.is_visible("#tab-products")

    def test_guild_tab_has_forms(self, page, live_server):
        self._goto(page)
        page.fill("#key-input", "ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        page.click("#analyze-btn")
        page.wait_for_selector("#results:not(.hidden)", timeout=20000)
        page.click('button[data-tab="guild"]')
        assert page.is_visible("#guild-name")
        assert page.is_visible("#guild-invite")
        assert page.is_visible("#guild-create-btn")
        assert page.is_visible("#guild-join-btn")

    def test_export_report_button_exists(self, page, live_server):
        self._goto(page)
        page.fill("#key-input", "ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        page.click("#analyze-btn")
        page.wait_for_selector("#results:not(.hidden)", timeout=20000)
        export_btn = page.locator("#export-report-btn")
        assert export_btn.is_visible()

    def test_all_tabs_clickable_after_analysis(self, page, live_server):
        """Verify all major tabs can be clicked without error."""
        self._goto(page)
        page.fill("#key-input", "ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        page.click("#analyze-btn")
        page.wait_for_selector("#results:not(.hidden)", timeout=20000)
        tabs = ["overview", "value", "characters", "wallet", "inventory", "goals", "settings"]
        for tab in tabs:
            page.click(f'button[data-tab="{tab}"]')
            assert page.is_visible(f"#tab-{tab}")
