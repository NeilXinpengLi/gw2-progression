"""Unit tests for the Production Decision Engine — decide() and record_feedback()."""

from unittest.mock import AsyncMock, patch

import pytest

from gw2_progression.services.production_engine import decide, record_feedback
from gw2_progression.services.v4_economic_model import STRATEGIES

FETCH_ALL = "gw2_progression.analyzer.fetch_all"
GET_RECS = "gw2_progression.services.build_service.get_recommendations"
GET_WEIGHTS = "gw2_progression.services.production_engine.get_personalized_weights"


def _mock_contents(**overrides) -> AsyncMock:
    c = AsyncMock()
    c.account_name = overrides.get("account_name", "Test.Player")
    c.wallet = overrides.get("wallet", [])
    c.characters = overrides.get("characters", [])
    c.materials = []
    c.bank = []
    c.shared_inventory = []
    c.errors = {}
    return c


def _mock_build(build_id="b1", name="Build", score=0.5, missing=2):
    b = AsyncMock()
    b.build_id = build_id
    b.build_name = name
    b.readiness_score = score
    b.missing_items_count = missing
    return b


@pytest.mark.asyncio
class TestDecide:
    async def test_decide_requires_api_key(self):
        with patch(FETCH_ALL, AsyncMock(side_effect=ValueError("api_key required"))):
            with pytest.raises(ValueError, match="api_key required"):
                await decide("")

    async def test_decide_with_minimal_account(self):
        with (
            patch(FETCH_ALL, AsyncMock(return_value=_mock_contents(wallet=[{"id": 1, "value": 250000}]))),
            patch(GET_RECS, AsyncMock(return_value=[])),
            patch(GET_WEIGHTS, AsyncMock(return_value=STRATEGIES["hybrid"]["weights"])),
        ):
            result = await decide("fake-key")

        assert result["account_name"] == "Test.Player"
        assert result["strategy_name"] == "Balanced"

    async def test_decide_with_builds(self):
        with (
            patch(FETCH_ALL, AsyncMock(return_value=_mock_contents(account_name="Build.Player"))),
            patch(GET_RECS, AsyncMock(return_value=[_mock_build("sc_bs", "Berserker", 0.45, 3)])),
            patch(GET_WEIGHTS, AsyncMock(return_value=STRATEGIES["build"]["weights"])),
        ):
            result = await decide("fake-key", strategy="build")

        assert result["strategy_name"] == "Build Completion"

    async def test_decide_gold_strategy(self):
        with (
            patch(FETCH_ALL, AsyncMock(return_value=_mock_contents(account_name="Gold.Player", wallet=[{"id": 1, "value": 50000}]))),
            patch(GET_RECS, AsyncMock(return_value=[])),
            patch(GET_WEIGHTS, AsyncMock(return_value=STRATEGIES["gold"]["weights"])),
        ):
            result = await decide("fake-key", strategy="gold")

        assert result["strategy_name"] == "Gold Farming"

    async def test_decide_no_wallet(self):
        with (
            patch(FETCH_ALL, AsyncMock(return_value=_mock_contents(account_name="NoWallet.Player", wallet=None))),
            patch(GET_RECS, AsyncMock(return_value=[])),
            patch(GET_WEIGHTS, AsyncMock(return_value=STRATEGIES["hybrid"]["weights"])),
        ):
            result = await decide("fake-key")

        assert result["account_name"] == "NoWallet.Player"

    async def test_decide_fallback_account_name(self):
        with (
            patch(FETCH_ALL, AsyncMock(return_value=_mock_contents(account_name=None))),
            patch(GET_RECS, AsyncMock(return_value=[])),
            patch(GET_WEIGHTS, AsyncMock(return_value=STRATEGIES["hybrid"]["weights"])),
        ):
            result = await decide("fake-key")

        assert result["account_name"] == "unknown"


RECORD_EXP = "gw2_progression.services.production_engine.record_experience"


@pytest.mark.asyncio
class TestRecordFeedback:
    async def test_record_feedback_success(self):
        mock_result = {"experience_id": 42, "reward": 0.5}
        with patch(RECORD_EXP, AsyncMock(return_value=mock_result)) as mock_rec:
            result = await record_feedback(
                account_name="Test.Player",
                action_key="sell_mystic_coin",
                action_label="Sell Mystic Coin",
                gold_impact=320000,
                success=True,
            )
        assert result == mock_result
        mock_rec.assert_called_once_with(
            account_name="Test.Player",
            action_key="sell_mystic_coin",
            action_label="Sell Mystic Coin",
            gold_impact=320000,
            build_impact=0.0,
            legendary_impact=0.0,
            time_spent_minutes=0,
            success=True,
        )

    async def test_record_feedback_minimal(self):
        mock_result = {"experience_id": 1, "reward": 0}
        with patch(RECORD_EXP, AsyncMock(return_value=mock_result)):
            result = await record_feedback(
                account_name="Minimal.Player",
                action_key="do_nothing",
            )
        assert result["experience_id"] == 1
