from fastapi import APIRouter, FastAPI

from gw2_progression.api.governance import API_ROUTE_GOVERNANCE, ApiCategory, StabilityLevel, governance_snapshot, include_governed_routers, route_enabled
from gw2_progression.api.main import ROUTER_BINDINGS


def test_all_main_routers_have_governance_metadata():
    keys = {key for key, _router in ROUTER_BINDINGS}
    assert keys == set(API_ROUTE_GOVERNANCE)


def test_route_categories_are_partitioned():
    categories = {meta.category for meta in API_ROUTE_GOVERNANCE.values()}
    assert categories == {
        ApiCategory.CORE_PRODUCT,
        ApiCategory.COMMERCE,
        ApiCategory.AI_LAB,
        ApiCategory.INFRASTRUCTURE,
    }


def test_app_level_endpoints_are_in_governance_snapshot():
    keys = {entry["key"] for entry in governance_snapshot()}
    assert {"auth_session", "health", "metrics", "static_pages", "websocket"}.issubset(keys)


def test_production_disables_ai_lab_by_default(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ENABLE_AI_LAB_ROUTES", raising=False)
    monkeypatch.delenv("ENABLE_EXPERIMENTAL_ROUTES", raising=False)

    assert route_enabled(API_ROUTE_GOVERNANCE["valuation"]) is True
    assert route_enabled(API_ROUTE_GOVERNANCE["commerce"]) is True
    assert route_enabled(API_ROUTE_GOVERNANCE["expert_ai"]) is False


def test_ai_lab_can_be_enabled_explicitly_in_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ENABLE_AI_LAB_ROUTES", "true")
    monkeypatch.setenv("ENABLE_EXPERIMENTAL_ROUTES", "true")

    assert route_enabled(API_ROUTE_GOVERNANCE["expert_ai"]) is True


def test_include_governed_routers_skips_disabled_routes(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ENABLE_EXPERIMENTAL_ROUTES", "false")
    monkeypatch.delenv("ENABLE_AI_LAB_ROUTES", raising=False)

    app = FastAPI()
    stable = APIRouter(prefix="/stable")
    lab = APIRouter(prefix="/lab")

    @stable.get("")
    async def stable_route():
        return {"ok": True}

    @lab.get("")
    async def lab_route():
        return {"ok": True}

    snapshot = include_governed_routers(app, [("valuation", stable), ("expert_ai", lab)])

    paths = {route.path for route in app.routes}
    assert "/stable" in paths
    assert "/lab" not in paths
    assert snapshot[0]["enabled"] == "true"
    assert snapshot[1]["enabled"] == "false"
    assert API_ROUTE_GOVERNANCE["expert_ai"].stability == StabilityLevel.EXPERIMENTAL
