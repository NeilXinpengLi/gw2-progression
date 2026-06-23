"""Tests for Phase 3 modules: optimizer, TP strategy, builds, agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gw2_progression.models import (
    AccountBuildReadiness,
    BuildTemplate,
    ProtectedAsset,
    RecipeDecision,
    RecipeOptimizationResult,
    TradingPostSignal,
)
from gw2_progression.services.build_service import CURATED_BUILDS, get_all_builds, get_build


class TestRecipeOptimization:
    def test_decision_model(self):
        d = RecipeDecision(item_id=19976, decision="buy", cost_buy=100000)
        assert d.item_id == 19976
        assert d.cost_buy == 100000

    def test_result_model(self):
        r = RecipeOptimizationResult(target_item_id=19976, target_count=10)
        assert r.strategy == "cheapest"
        assert r.craft_vs_buy_delta == 0


class TestTradingPost:
    def test_signal_model(self):
        s = TradingPostSignal(item_id=19976, signal_type="sell_candidate", severity="info", reason="Test")
        assert s.signal_type == "sell_candidate"

    def test_protected_asset_model(self):
        a = ProtectedAsset(account_name="Player.1234", item_id=19976, reason="manual_lock")
        assert a.account_name == "Player.1234"
        assert a.linked_goal_id == ""

    @pytest.mark.asyncio
    async def test_protect_unprotect(self):
        from gw2_progression.services.tp_strategy_service import protect_asset

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=AsyncMock())
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock()

        with patch("gw2_progression.services.tp_strategy_service.get_db", return_value=mock_db):
            asset = await protect_asset("Player.1234", 19976, "manual_lock")
        assert asset.item_id == 19976

    @pytest.mark.asyncio
    async def test_generate_signals_empty(self):
        from gw2_progression.services.tp_strategy_service import generate_signals

        with (
            patch("gw2_progression.services.tp_strategy_service.get_db", AsyncMock()),
        ):
            signals = await generate_signals("Player.1234")
        assert signals == []


class TestBuilds:
    def test_curated_builds_count(self):
        assert len(CURATED_BUILDS) >= 20

    def test_get_all_builds(self):
        builds = get_all_builds()
        assert len(builds) >= 20

    def test_get_build_found(self):
        b = get_build("sc_dh")
        assert b is not None
        assert b.name == "Dragonhunter (Power)"

    def test_get_build_not_found(self):
        assert get_build("nonexistent") is None

    def test_build_template_model(self):
        b = BuildTemplate(build_id="test", source="manual", name="Test Build", profession="Guardian", elite_specialization="Dragonhunter", game_mode="raid", role="dps")
        assert b.build_id == "test"
        assert len(b.gear) == 0

    def test_readiness_model(self):
        r = AccountBuildReadiness(account_name="Player.1234", build_id="sc_dh", build_name="Test")
        assert r.readiness_score == 0.0
        assert r.profession_match is False


class TestAgent:
    def test_advice_model(self):
        from gw2_progression.models import ProgressionAdvice

        a = ProgressionAdvice(summary="Test advice")
        assert a.summary == "Test advice"
        assert a.recommended_actions == []
        assert a.weekly_plan == []

    @pytest.mark.asyncio
    async def test_advice_generation(self):
        from gw2_progression.services.agent_service import generate_advice

        with (
            patch("gw2_progression.analyzer.fetch_all", AsyncMock()) as mock_fetch,
            patch("gw2_progression.services.agent_service.generate_goal_plan", AsyncMock()),
            patch("gw2_progression.services.agent_service.generate_signals", AsyncMock(return_value=[])),
            patch("gw2_progression.services.agent_service.get_recommendations", AsyncMock(return_value=[])),
            patch("gw2_progression.services.agent_service._call_llm", AsyncMock(return_value=None)),
        ):
            mock_fetch.return_value.account_name = "Player.1234"
            mock_fetch.return_value.wallet = [{"id": 1, "value": 50000}]
            mock_fetch.return_value.characters = []
            mock_fetch.return_value.materials = []
            mock_fetch.return_value.bank = []
            mock_fetch.return_value.shared_inventory = []
            mock_fetch.return_value.errors = {}

            advice = await generate_advice("fake-key")

        assert len(advice.recommended_actions) > 0
        assert len(advice.weekly_plan) == 7

    @pytest.mark.asyncio
    async def test_llm_call_success(self):
        from gw2_progression.services.agent_service import _call_llm

        with patch("gw2_progression.services.agent_service.LLM_API_KEY", "sk-test"):
            with patch("gw2_progression.services.agent_service.LLM_PROVIDER", "openai"):
                with patch("httpx.AsyncClient") as mock_client:
                    mock_resp = MagicMock()
                    mock_resp.status_code = 200
                    mock_resp.json.return_value = {"choices": [{"message": {"content": '{"summary": "Test", "recommended_actions": []}'}}]}
                    mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
                    result = await _call_llm("test prompt")
        assert result is not None
        assert result["summary"] == "Test"

    @pytest.mark.asyncio
    async def test_llm_call_no_key(self):
        from gw2_progression.services.agent_service import _call_llm

        with patch("gw2_progression.services.agent_service.LLM_API_KEY", None):
            result = await _call_llm("test prompt")
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_call_api_error(self):
        from gw2_progression.services.agent_service import _call_llm

        with patch("gw2_progression.services.agent_service.LLM_API_KEY", "sk-test"):
            with patch("gw2_progression.services.agent_service.LLM_PROVIDER", "openai"):
                with patch("httpx.AsyncClient") as mock_client:
                    mock_resp = MagicMock()
                    mock_resp.status_code = 500
                    mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
                    result = await _call_llm("test prompt")
        assert result is None

    def test_parse_llm_response_plain_json(self):
        from gw2_progression.services.agent_service import _parse_llm_response

        content = '{"summary": "Hello", "recommended_actions": []}'
        result = _parse_llm_response(content)
        assert result["summary"] == "Hello"

    def test_parse_llm_response_code_fence(self):
        from gw2_progression.services.agent_service import _parse_llm_response

        content = '```json\n{"summary": "Wrapped", "recommended_actions": []}\n```'
        result = _parse_llm_response(content)
        assert result["summary"] == "Wrapped"

    def test_parse_llm_response_code_fence_no_lang(self):
        from gw2_progression.services.agent_service import _parse_llm_response

        content = '```\n{"summary": "No lang", "recommended_actions": []}\n```'
        result = _parse_llm_response(content)
        assert result["summary"] == "No lang"

    def test_parse_llm_response_invalid_json(self):
        from gw2_progression.services.agent_service import _parse_llm_response

        result = _parse_llm_response("not json")
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_call_anthropic(self):
        from gw2_progression.services.agent_service import _call_llm

        with patch("gw2_progression.services.agent_service.LLM_API_KEY", "sk-ant-test"):
            with patch("gw2_progression.services.agent_service.LLM_PROVIDER", "anthropic"):
                with patch("httpx.AsyncClient") as mock_client:
                    mock_resp = MagicMock()
                    mock_resp.status_code = 200
                    mock_resp.json.return_value = {"content": [{"text": '{"summary": "Claude", "recommended_actions": []}'}]}
                    mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
                    result = await _call_llm("test prompt")
        assert result["summary"] == "Claude"

    @pytest.mark.asyncio
    async def test_advice_with_llm_enhancement(self):
        from gw2_progression.services.agent_service import generate_advice

        llm_result = {
            "summary": "LLM powered summary",
            "recommended_actions": [{"action": "test_action", "target": "test", "reason": "LLM reason", "cost": 1000}],
            "weekly_plan": [
                {"day": "Monday", "tasks": ["Task 1"]},
                {"day": "Tuesday", "tasks": ["Task 2"]},
                {"day": "Wednesday", "tasks": []},
                {"day": "Thursday", "tasks": []},
                {"day": "Friday", "tasks": []},
                {"day": "Saturday", "tasks": []},
                {"day": "Sunday", "tasks": []},
            ],
        }

        with (
            patch("gw2_progression.analyzer.fetch_all", AsyncMock()) as mock_fetch,
            patch("gw2_progression.services.agent_service.generate_goal_plan", AsyncMock()),
            patch("gw2_progression.services.agent_service.generate_signals", AsyncMock(return_value=[])),
            patch("gw2_progression.services.agent_service.get_recommendations", AsyncMock(return_value=[])),
            patch("gw2_progression.services.agent_service._call_llm", AsyncMock(return_value=llm_result)),
        ):
            mock_fetch.return_value.account_name = "Player.LLM"
            mock_fetch.return_value.wallet = [{"id": 1, "value": 500000}]
            mock_fetch.return_value.characters = []
            mock_fetch.return_value.materials = []
            mock_fetch.return_value.bank = []
            mock_fetch.return_value.shared_inventory = []
            mock_fetch.return_value.errors = {}

            advice = await generate_advice("fake-key")

        assert advice.summary == "LLM powered summary"
        assert len(advice.recommended_actions) == 1
        assert advice.recommended_actions[0]["action"] == "test_action"
        assert len(advice.weekly_plan) == 7


class TestAuthService:
    @pytest.mark.skip(reason="requires DB init (integration test)")
    @pytest.mark.asyncio
    async def test_create_and_get_session(self):
        from gw2_progression.services.auth_service import create_session, get_session

        token = await create_session("test-api-key", "Player.1234")
        assert len(token) > 20
        session = await get_session(token)
        assert session is not None
        assert session["api_key"] == "test-api-key"
        assert session["account_name"] == "Player.1234"

    @pytest.mark.skip(reason="requires DB init (integration test)")
    @pytest.mark.asyncio
    async def test_get_api_key_from_token(self):
        from gw2_progression.services.auth_service import create_session, get_api_key

        token = await create_session("real-key", "Player.1234")
        resolved = await get_api_key(token)
        assert resolved == "real-key"

    @pytest.mark.asyncio
    async def test_get_api_key_passthrough(self):
        from gw2_progression.services.auth_service import get_api_key

        resolved = await get_api_key("real-key-123")
        assert resolved == "real-key-123"


class TestBuildServiceDetail:
    def test_get_all_builds_count(self):
        from gw2_progression.services.build_service import CURATED_BUILDS

        assert len(CURATED_BUILDS) >= 20

    def test_get_build_detail(self):
        from gw2_progression.services.build_service import get_build

        b = get_build("sc_dh")
        assert b is not None
        assert b.source == "snowcrows"
        assert b.profession == "Guardian"

    def test_build_not_found(self):
        from gw2_progression.services.build_service import get_build

        assert get_build("nonexistent") is None

    @pytest.mark.asyncio
    async def test_readiness_with_no_profession_match(self):
        from gw2_progression.services.build_service import calculate_readiness

        with patch("gw2_progression.analyzer.fetch_all", AsyncMock()) as m:
            m.return_value.account_name = "Player.1234"
            m.return_value.characters = [{"name": "Test", "profession": "Mesmer"}]
            m.return_value.materials = []
            m.return_value.bank = []
            m.return_value.shared_inventory = []
            m.return_value.errors = {}

            readiness = await calculate_readiness("fake-key", "sc_dh")

        assert readiness.profession_match is False
        assert readiness.readiness_score == 0.0


class TestRecipeOptimizerDetail:
    @pytest.mark.asyncio
    async def test_optimizer_direct_buy(self):
        from gw2_progression.services.recipe_optimizer import optimize_item

        with patch("gw2_progression.services.recipe_optimizer._fetch_recipes_for_output", AsyncMock(return_value=[])):
            decision = await optimize_item(19720, 100, {}, {19720: (3000, 3500)}, depth=0)
        assert decision.decision == "buy"
        assert decision.cost_buy == 100 * 3500

    @pytest.mark.asyncio
    async def test_optimizer_use_owned(self):
        from gw2_progression.services.recipe_optimizer import optimize_item

        with patch("gw2_progression.services.recipe_optimizer._fetch_recipes_for_output", AsyncMock(return_value=[])):
            decision = await optimize_item(19720, 100, {19720: 200}, {}, depth=0)
        assert decision.decision == "use_owned"
        assert decision.cost_buy == 0

    @pytest.mark.asyncio
    async def test_optimizer_partial_owned(self):
        from gw2_progression.services.recipe_optimizer import optimize_item

        with patch("gw2_progression.services.recipe_optimizer._fetch_recipes_for_output", AsyncMock(return_value=[])):
            owned = {19720: 30}
            decision = await optimize_item(19720, 100, owned, {19720: (3000, 3500)}, depth=0)
        assert decision.decision == "buy"
        assert decision.owned_count == 30

    @pytest.mark.asyncio
    async def test_optimizer_cycle_guard(self):
        from gw2_progression.services.recipe_optimizer import optimize_item

        with patch(
            "gw2_progression.services.recipe_optimizer._fetch_recipes_for_output",
            AsyncMock(return_value=[{"id": 1, "output_item_id": 1, "output_item_count": 1, "ingredients": [{"item_id": 1, "count": 1}]}]),
        ):
            decision = await optimize_item(1, 5, {}, {})
        # Cycle detected, fallback to buy; craft not selected because
        # ingredient cost (cycle→buy with 0 price) == direct_buy_cost (0)
        assert decision.decision in ("buy", "craft")
