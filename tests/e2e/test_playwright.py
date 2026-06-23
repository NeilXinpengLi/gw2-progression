"""Playwright E2E tests for the new 4-page behavior-driven UX."""

import json
import os
import socket
import threading
import time
import urllib.request

import pytest

os.environ["RATE_LIMIT_REQUESTS"] = "9999"


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


SERVER_PORT = _free_port()
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"

MOCK_SESSION = json.dumps({"token": "mock-token", "account_name": "P.Player", "expires_in": 86400})
MOCK_ANALYZE = json.dumps(
    {
        "account_name": "Playwright.Player",
        "account_world": 1001,
        "characters": [{"name": "TestChar", "profession": "Guardian", "level": 80}],
        "wallet": [{"id": 1, "value": 500000}],
        "bank": [],
        "materials": [],
        "errors": {},
    }
)
MOCK_VALUE = json.dumps(
    {
        "summary": {"total_value_buy": 2000000, "wallet_value": 500000, "priced_item_count": 10},
        "top_items": [],
        "holdings": [],
        "breakdown": {},
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
    elif "/credentials/providers" in url:
        route.fulfill(status=200, content_type="application/json", body='{"providers":[],"scope_explanations":{"account":"info"}}')
    elif "/reports" in url:
        route.fulfill(status=200, content_type="application/json", body="[]")
    elif "/subscriptions/" in url:
        route.fulfill(status=200, content_type="application/json", body='{"active":false}')
    elif "/guild/by-account/" in url:
        route.fulfill(status=200, content_type="application/json", body="null")
    elif "/quests/" in url:
        route.fulfill(status=200, content_type="application/json", body='{"total":7,"completed":0,"progress_pct":0,"quests":[]}')
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

    def test_nav_has_4_tabs(self, page, live_server):
        self._goto(page)
        page.fill("#key-input", "ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        page.click("#analyze-btn")
        page.wait_for_selector("#nav-tabs:not(.hidden)", timeout=20000)
        tabs = page.locator("#nav-tabs button[data-tab]")
        assert tabs.count() == 4

    def test_insight_screen_appears(self, page, live_server):
        self._goto(page)
        page.fill("#key-input", "ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        page.click("#analyze-btn")
        page.wait_for_selector("#insight-screen", timeout=20000)

    def test_coach_tab(self, page, live_server):
        self._goto(page)
        page.fill("#key-input", "ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        page.click("#analyze-btn")
        page.wait_for_selector("#results:not(.hidden)", timeout=20000)
        page.click('button[data-tab="coach"]')
        assert page.is_visible("#tab-coach")

    def test_timeline_tab(self, page, live_server):
        self._goto(page)
        page.fill("#key-input", "ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        page.click("#analyze-btn")
        page.wait_for_selector("#results:not(.hidden)", timeout=20000)
        page.click('button[data-tab="timeline"]')
        assert page.is_visible("#tab-timeline")

    def test_advanced_tab(self, page, live_server):
        self._goto(page)
        page.fill("#key-input", "ABCDEF01-2345-6789-ABCD-EF0123456789AB")
        page.click("#analyze-btn")
        page.wait_for_selector("#results:not(.hidden)", timeout=20000)
        page.click('button[data-tab="advanced"]')
        assert page.is_visible("#tab-advanced")
