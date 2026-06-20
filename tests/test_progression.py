"""Tests for the progression goal template system."""

from unittest.mock import AsyncMock, patch

import pytest

from gw2_progression.services.progression_service import CURATED_REQUIREMENTS, CURATED_TEMPLATES, get_requirements, get_templates


class TestGoalTemplate:
    def test_curated_templates_count(self):
        assert len(CURATED_TEMPLATES) >= 5

    def test_curated_templates_types(self):
        types = set(t.goal_type for t in CURATED_TEMPLATES)
        assert "legendary_weapon" in types
        assert "legendary_trinket" in types

    def test_curated_requirements_for_bolt(self):
        bolt_reqs = [r for r in CURATED_REQUIREMENTS if r.template_id == "leg_greatsword_bolt"]
        assert len(bolt_reqs) >= 5
        assert any("mystic_coin" in r.requirement_id for r in bolt_reqs)

    def test_template_has_target_item(self):
        for t in CURATED_TEMPLATES:
            if t.goal_type in ("legendary_weapon", "legendary_trinket"):
                assert t.target_item_id > 0

    @pytest.mark.asyncio
    async def test_get_templates_fallback(self):
        """When DB is unavailable, should fall back to curated templates."""
        with patch("gw2_progression.services.progression_service.get_db", side_effect=Exception("DB unavailable")):
            templates = await get_templates()
        assert len(templates) >= 5

    @pytest.mark.asyncio
    async def test_get_requirements_fallback(self):
        with patch("gw2_progression.services.progression_service.get_db", side_effect=Exception("DB unavailable")):
            reqs = await get_requirements("leg_greatsword_bolt")
        assert len(reqs) >= 5


@pytest.mark.asyncio
class TestGenerateGoalPlan:
    async def test_generate_plan(self):
        from gw2_progression.services.progression_service import generate_goal_plan

        with (
            patch("gw2_progression.analyzer.fetch_all", AsyncMock()) as mock_fetch,
            patch("gw2_progression.services.progression_service.get_requirements", AsyncMock()) as mock_reqs,
            patch("gw2_progression.services.progression_service.fetch_prices", AsyncMock(return_value={})),
        ):
            mock_fetch.return_value.account_name = "Player.1234"
            mock_fetch.return_value.materials = [{"id": 19976, "count": 50, "category": 5}]
            mock_fetch.return_value.bank = []
            mock_fetch.return_value.wallet = [{"id": 1, "value": 100000}]
            mock_fetch.return_value.characters = []
            mock_fetch.return_value.shared_inventory = []
            mock_fetch.return_value.errors = {}
            from gw2_progression.models import GoalRequirement

            mock_reqs.return_value = [
                GoalRequirement(requirement_id="test1", template_id="leg_greatsword_bolt", requirement_type="item", ref_id=19976, ref_name="Mystic Coin", required_count=100),
                GoalRequirement(requirement_id="test2", template_id="leg_greatsword_bolt", requirement_type="currency", ref_id=1, ref_name="Gold", required_count=500),
            ]
            plan = await generate_goal_plan("fake-key-12345678", "leg_greatsword_bolt")

        assert plan.template_id == "leg_greatsword_bolt"
        assert plan.account_name == "Player.1234"
        assert len(plan.requirements) >= 2
        assert plan.total_completion_percent >= 0
