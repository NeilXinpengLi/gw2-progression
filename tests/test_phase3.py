"""Tests for Phase 3 modules: optimizer, TP strategy, builds, agent."""

from unittest.mock import AsyncMock, patch

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
