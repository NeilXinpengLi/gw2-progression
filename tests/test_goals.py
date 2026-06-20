"""Tests for the goal tracker service."""

from unittest.mock import AsyncMock, patch

import pytest

from gw2_progression.models import TrackedGoal


class TestGoalModel:
    def test_goal_defaults(self):
        goal = TrackedGoal(goal_id="abc123", account_name="Player.1234", target_item_id=19976)
        assert goal.status == "active"
        assert goal.priority == "normal"
        assert goal.completion_percent == 0.0

    def test_goal_with_progress(self):
        goal = TrackedGoal(
            goal_id="abc",
            account_name="Player.1234",
            target_item_id=19976,
            target_count=250,
            completion_percent=40.0,
            owned_material_value=200000,
            missing_material_value=300000,
            estimated_remaining_cost=300000,
        )
        assert goal.completion_percent == 40.0
        assert goal.owned_material_value == 200000


@pytest.mark.asyncio
class TestGoalService:
    async def test_create_goal(self):
        from gw2_progression.services.goal_service import create_goal

        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.lastrowid = 1
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock()

        with (
            patch("gw2_progression.analyzer.fetch_all", AsyncMock()) as mock_fetch,
            patch("gw2_progression.services.goal_service.get_db", return_value=mock_db),
        ):
            mock_fetch.return_value.account_name = "Player.1234"
            goal = await create_goal("fake-key", 19976, 10, "high")

        assert goal.target_item_id == 19976
        assert goal.target_count == 10
        assert goal.priority == "high"
        assert goal.status == "active"
        assert len(goal.goal_id) > 0

    async def test_refresh_goal_updates_progress(self):
        from gw2_progression.services.goal_service import refresh_goal

        # Use a callable that returns a dict-like row for each query
        class FakeRow:
            def __init__(self, data):
                self._data = data

            def __getitem__(self, key):
                return self._data[key]

            def keys(self):
                return self._data.keys()

            def __iter__(self):
                return iter(self._data.keys())

        mock_goal_data = {
            "goal_id": "test123",
            "account_name": "Player.1234",
            "target_item_id": 19976,
            "target_count": 10,
            "status": "active",
            "priority": "normal",
            "completion_percent": 0.0,
            "owned_material_value": 0,
            "missing_material_value": 0,
            "missing_item_count": 0,
            "estimated_remaining_cost": 0,
            "created_at": "",
            "updated_at": "",
        }

        mock_db = AsyncMock()

        async def execute_side_effect(sql, params=None):
            mock_c = AsyncMock()
            mock_c.fetchone = AsyncMock(return_value=FakeRow(mock_goal_data))
            return mock_c

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock()

        with (
            patch("gw2_progression.services.goal_service.get_db", return_value=mock_db),
            patch("gw2_progression.services.goal_service.create_plan", AsyncMock()) as mock_plan,
        ):
            mock_plan.return_value.missing_material_cost = 300000
            mock_plan.return_value.owned_material_value_used = 200000
            mock_plan.return_value.lines = [
                type("Line", (), {"missing_count": 2})(),
                type("Line", (), {"missing_count": 0})(),
            ]

            goal = await refresh_goal("fake-key", "test123")

        assert goal.owned_material_value == 200000
        assert goal.missing_material_value == 300000
        assert goal.estimated_remaining_cost == 300000
        assert goal.missing_item_count == 1
        assert goal.completion_percent == 40.0
