"""Tests for static data ingest and recipe lookup."""

from unittest.mock import AsyncMock, patch

import pytest

from gw2_progression.services.static_data_service import find_recipes_by_output


@pytest.mark.asyncio
class TestRecipeLookup:
    async def test_recipe_lookup_by_output(self):
        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(
            return_value=[
                {"id": 1, "output_item_id": 19976, "output_item_count": 1, "disciplines": '["Artificer"]', "min_rating": 400, "flags": "[]", "type": "Component"},
            ]
        )
        mock_ing_cursor = AsyncMock()
        mock_ing_cursor.fetchall = AsyncMock(
            return_value=[
                {"item_id": 19720, "count": 3},
                {"item_id": 19684, "count": 1},
            ]
        )

        async def execute_side_effect(sql, params=None):
            if "FROM static_recipes" in sql:
                return mock_cursor
            return mock_ing_cursor

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock()

        with patch("gw2_progression.services.static_data_service.get_db", return_value=mock_db):
            recipes = await find_recipes_by_output(19976)

        assert len(recipes) == 1
        assert recipes[0]["id"] == 1
        assert recipes[0]["output_item_id"] == 19976
        assert len(recipes[0]["ingredients"]) == 2
        assert recipes[0]["ingredients"][0]["item_id"] == 19720

    async def test_recipe_lookup_no_results(self):
        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock()

        with patch("gw2_progression.services.static_data_service.get_db", return_value=mock_db):
            recipes = await find_recipes_by_output(999999)

        assert recipes == []
