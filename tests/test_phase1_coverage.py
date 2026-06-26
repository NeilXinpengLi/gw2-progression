"""Phase 1.1: Coverage for build_service, recipe_service, static_data_service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Build Service Tests ──


class TestBuildService:
    def test_get_all_builds_returns_list(self):
        from gw2_progression.services.build_service import get_all_builds

        builds = get_all_builds()
        assert len(builds) >= 15
        assert all(hasattr(b, "build_id") for b in builds)
        assert all(hasattr(b, "profession") for b in builds)

    def test_get_build_found(self):
        from gw2_progression.services.build_service import get_all_builds, get_build

        builds = get_all_builds()
        if builds:
            tid = builds[0].build_id
            build = get_build(tid)
            assert build is not None
            assert build.build_id == tid

    def test_get_build_not_found(self):
        from gw2_progression.services.build_service import get_build

        assert get_build("nonexistent") is None

    def test_get_account_professions(self):
        from gw2_progression.services.build_service import _get_account_professions

        class MockContents:
            characters = [
                {"name": "War", "profession": "Warrior", "level": 80},
                {"name": "Ele", "profession": "Elementalist", "level": 80},
            ]

        profs = _get_account_professions(MockContents())
        assert "Warrior" in profs
        assert "Elementalist" in profs

    def test_get_account_professions_empty(self):
        from gw2_progression.services.build_service import _get_account_professions

        class MockContents:
            characters = []

        assert _get_account_professions(MockContents()) == set()

    @pytest.mark.asyncio
    async def test_calculate_readiness_no_characters(self):
        from gw2_progression.services.build_service import calculate_readiness, get_all_builds

        builds = get_all_builds()
        if not builds:
            return
        bid = builds[0].build_id
        with patch("gw2_progression.analyzer.fetch_all", AsyncMock()) as mock_fetch:
            mock_fetch.return_value = MagicMock(
                account_name="Test.Player",
                characters=[],
                wallet=[],
                bank=[],
                materials=[],
                shared_inventory=[],
                unlocked_skins=[],
                unlocked_skins_count=0,
                errors={},
            )
            readiness = await calculate_readiness("test-key", bid)
        assert readiness.readiness_score == 0.0


# ── Recipe Pure Function Tests ──


class TestRecipePureFunctions:
    def test_extract_disciplines(self):
        from gw2_progression.services.recipe_service import _extract_disciplines

        chars = [
            {"crafting": [{"discipline": "Weaponsmith", "rating": 500}]},
            {"crafting": [{"discipline": "Armorsmith", "rating": 400}]},
        ]
        disc = _extract_disciplines(chars)
        assert disc["Weaponsmith"] == 500
        assert disc["Armorsmith"] == 400

    def test_extract_disciplines_empty(self):
        from gw2_progression.services.recipe_service import _extract_disciplines

        assert _extract_disciplines(None) == {}
        assert _extract_disciplines([]) == {}

    def test_filter_recipes_by_discipline(self):
        from gw2_progression.services.recipe_service import _filter_recipes_by_discipline

        recipes = [
            {"disciplines": ["Weaponsmith"], "min_rating": 450},
            {"disciplines": ["Armorsmith"], "min_rating": 300},
        ]
        disc = {"Weaponsmith": 400, "Armorsmith": 350}

        filtered = _filter_recipes_by_discipline(recipes, disc)
        assert len(filtered) == 1  # Only Armorsmith (350 >= 300)
        assert filtered[0]["disciplines"] == ["Armorsmith"]

    def test_filter_recipes_no_disc(self):
        from gw2_progression.services.recipe_service import _filter_recipes_by_discipline

        recipes = [{"disciplines": ["Weaponsmith"], "min_rating": 400}]
        filtered = _filter_recipes_by_discipline(recipes, {})
        assert filtered == recipes

    def test_build_owned_map(self):
        from gw2_progression.services.recipe_service import _build_owned_map

        materials = [{"id": 19720, "count": 100}]
        bank = [{"id": 19721, "count": 50}]

        owned = _build_owned_map(materials, bank, None, None)
        assert owned[19720] == 100
        assert owned[19721] == 50

    def test_build_owned_map_from_characters(self):
        from gw2_progression.services.recipe_service import _build_owned_map

        chars = [
            {"bags": [{"inventory": [{"id": 19720, "count": 5}]}]},
            {"bags": [{"inventory": [{"id": 19720, "count": 3}]}]},
        ]
        owned = _build_owned_map([], [], chars, [])
        assert owned[19720] == 8

    def test_build_owned_map_shared_inventory(self):
        from gw2_progression.services.recipe_service import _build_owned_map

        shared = [{"id": 19976, "count": 25}]
        owned = _build_owned_map([], [], [], shared)
        assert owned[19976] == 25


# ── Static Data Tests ──


class TestStaticDataService:
    @pytest.mark.asyncio
    async def test_find_recipes_by_output_empty(self):
        from gw2_progression.services.static_data_service import find_recipes_by_output

        with patch("gw2_progression.services.static_data_service.get_db") as mock_get_db:
            mock_conn = AsyncMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall = AsyncMock(return_value=[])
            mock_conn.execute.return_value = mock_cursor
            mock_get_db.return_value = mock_conn

            recipes = await find_recipes_by_output(999999)
        assert recipes == []

    def test_get_ingest_progress_not_found(self):
        from gw2_progression.services.static_data_service import get_ingest_progress

        assert get_ingest_progress("nonexistent") is None

    def test_get_ingest_progress(self):
        from gw2_progression.services.static_data_service import (
            _update_progress,
            get_ingest_progress,
        )

        _update_progress("test-task", status="running", progress=50)
        result = get_ingest_progress("test-task")
        assert result["status"] == "running"
        assert result["progress"] == 50


# ── Combined Flow Tests ──


@pytest.mark.asyncio
async def test_expand_ingredient_no_price():
    from gw2_progression.services.recipe_service import _expand_ingredient

    with (
        patch("gw2_progression.services.recipe_service.fetch_prices", AsyncMock(return_value={})),
        patch("gw2_progression.services.recipe_service._fetch_item_name", AsyncMock(return_value="Test")),
        patch("gw2_progression.services.recipe_service._fetch_recipes_for_output", AsyncMock(return_value=[])),
    ):
        result = await _expand_ingredient(
            item_id=19720,
            needed_count=10,
            owned_map={},
            prices={},
        )
    assert result.item_id == 19720
