from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from gw2_progression.analyzer import AccountContents
from gw2_progression.api.main import app
from gw2_progression.models import (
    AccountReport,
    CraftingResponse,
    ItemHolding,
    ParsedGoal,
    PlanAction,
    ProgressionPlan,
    ValueAnalyzeResponse,
    ValueBreakdown,
    ValueSummary,
)

client = TestClient(app)


def test_core_player_smoke_flow(monkeypatch):
    api_key = "ABCDEF01-1234"
    account_name = "Player.1234"

    monkeypatch.setattr(
        "gw2_progression.analyzer.fetch_all",
        AsyncMock(
            return_value=AccountContents(
                account_name=account_name,
                wallet=[{"id": 1, "value": 1000000}],
                materials=[{"id": 19720, "count": 10, "category": 5}],
                bank=[],
                characters=[],
                shared_inventory=[],
            )
        ),
    )
    monkeypatch.setattr("gw2_progression.api.main.create_session", AsyncMock(return_value="session-token"))
    monkeypatch.setattr(
        "gw2_progression.api.routes.valuation.run_full_analysis",
        AsyncMock(
            return_value=ValueAnalyzeResponse(
                summary=ValueSummary(total_value_buy=1000000, wallet_value=1000000),
                breakdown=ValueBreakdown(),
                top_items=[],
                warnings=[],
                history=[],
            )
        ),
    )
    monkeypatch.setattr(
        "gw2_progression.api.routes.valuation.search_items_by_name",
        AsyncMock(
            return_value=[
                ItemHolding(item_id=19720, count=10, location_type="material_storage", value_buy=1000, valuation_status="priced"),
            ]
        ),
    )
    monkeypatch.setattr(
        "gw2_progression.api.routes.crafting.calculate_cheapest",
        AsyncMock(
            return_value=CraftingResponse(
                target_item_id=19720,
                target_count=1,
                total_buy_cost=1000,
                shopping_list=[{"item_id": 19720, "count": 1}],
            )
        ),
    )

    action = PlanAction(
        action_id="a1",
        plan_id="p1",
        action_type="BUY_ITEM",
        title="Buy one material",
        reason="Fastest path",
        cost_gold=1,
        priority=1,
        day_index=0,
    )
    plan = ProgressionPlan(
        plan_id="p1",
        account_name=account_name,
        strategy="balanced",
        estimated_days=1,
        actions=[action],
        insight="Buy the missing material.",
    )
    monkeypatch.setattr(
        "gw2_progression.api.routes.goal_driven.interpret_goal",
        AsyncMock(
            return_value=ParsedGoal(
                raw_text="Craft item",
                goal_type="CRAFT_ITEM",
                target_item_id=19720,
                target_item_name="Mystic Coin",
                confidence=0.9,
            )
        ),
    )
    monkeypatch.setattr("gw2_progression.api.routes.goal_driven.generate_plan_from_goal", AsyncMock(return_value=plan))
    monkeypatch.setattr("gw2_progression.api.routes.goal_driven._save_plan", AsyncMock())
    monkeypatch.setattr(
        "gw2_progression.api.routes.reports.generate_report",
        AsyncMock(
            return_value=AccountReport(
                report_id=99,
                account_name=account_name,
                report_type="full",
                title="Smoke Report",
                summary="Ready.",
            )
        ),
    )

    auth = client.post("/auth/session", json={"api_key": api_key})
    assert auth.status_code == 200
    assert auth.json()["token"] == "session-token"

    value = client.post("/value/analyze", json={"api_key": api_key})
    assert value.status_code == 200
    assert value.json()["summary"]["wallet_value"] == 1000000

    search = client.get("/value/items/search", params={"account_name": account_name, "q": "19720"})
    assert search.status_code == 200
    assert search.json()[0]["item_id"] == 19720

    crafting = client.post("/crafting/calculate/cheapest", json={"api_key": api_key, "target_item_id": 19720, "quantity": 1})
    assert crafting.status_code == 200
    assert crafting.json()["shopping_list"][0]["item_id"] == 19720

    generated = client.post("/goal-driven/generate", json={"api_key": api_key, "goal_text": "Craft Mystic Coin"})
    assert generated.status_code == 200
    assert generated.json()["plan"]["plan_id"] == "p1"
    assert generated.json()["top_actions"][0]["title"] == "Buy one material"

    report = client.post(
        "/reports/generate",
        params={"account_name": account_name, "report_type": "full", "title": "Smoke Report", "summary": "Ready."},
    )
    assert report.status_code == 200
    assert report.json()["report_id"] == 99
