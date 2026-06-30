"""Tests for the Ontology layer — object store, relations, impact analysis, QA gate."""

import datetime
import json
from unittest.mock import AsyncMock, patch

import pytest

from gw2_progression.ontology import config, object_store as store, graph_query as gq
from gw2_progression.ontology.models import OntologyObject, OntologyRelation, SafeSurplusResult, ImpactReport, QAReport
from gw2_progression.ontology.impact_analyzer import analyze_sell_impact, compute_safe_surplus
from gw2_progression.ontology.qa_gate import check_report_publishable, validate_object
from gw2_progression.ontology.account_mapper import sync_account_to_ontology
from gw2_progression.ontology.goal_mapper import map_goal_to_ontology, sync_goal_reservations
from gw2_progression.models import TrackedGoal


def _fresh_ts() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_ontology():
    store.clear()
    yield
    store.clear()


def make_asset(item_id: int, count: int, account: str = "Test.1234", location: str = "material_storage") -> OntologyObject:
    return store.register_object(
        class_name="account_asset",
        account_name=account,
        properties={"item_id": item_id, "count": count, "location": location, "tradable": True},
    )


def make_goal(name: str, account: str = "Test.1234", status: str = "active", template_id: str = "leg_test") -> OntologyObject:
    return store.register_object(
        class_name="legendary_goal",
        account_name=account,
        properties={
            "name": name,
            "template_id": template_id,
            "target_item_id": 0,
            "priority": "normal",
            "status": status,
        },
    )


def make_requirement(goal_id: str, item_id: int, required: int, owned: int = 0) -> OntologyObject:
    return store.register_object(
        class_name="goal_requirement",
        properties={
            "item_id": item_id,
            "required_count": required,
            "owned_count": owned,
            "template_id": "leg_test",
        },
        source_object_id=goal_id,
    )


def make_reservation(item_id: int, count: int, goal_id: str, account: str = "Test.1234") -> OntologyObject:
    return store.register_object(
        class_name="reserved_asset",
        account_name=account,
        properties={"item_id": item_id, "reserved_count": count, "goal_id": goal_id},
    )


# ── Config Tests ──────────────────────────────────────────────────────

class TestConfig:
    def test_class_definitions_exist(self):
        assert len(config.CLASS_DEFINITIONS) >= 10
        assert "account_snapshot" in config.CLASS_DEFINITIONS
        assert "legendary_goal" in config.CLASS_DEFINITIONS
        assert "reserved_asset" in config.CLASS_DEFINITIONS
        assert "safe_surplus" in config.CLASS_DEFINITIONS

    def test_relation_definitions_exist(self):
        assert len(config.RELATION_DEFINITIONS) >= 8
        assert "owns" in config.RELATION_DEFINITIONS
        assert "requires" in config.RELATION_DEFINITIONS
        assert "reserved_for" in config.RELATION_DEFINITIONS

    def test_action_definitions_exist(self):
        assert len(config.ACTION_DEFINITIONS) >= 7
        assert "sync_account_snapshot" in config.ACTION_DEFINITIONS
        assert "generate_do_not_sell" in config.ACTION_DEFINITIONS
        assert "analyze_sell_item" in config.ACTION_DEFINITIONS

    def test_explanation_constraint_ontology_definitions_exist(self):
        assert "explanation_candidate" in config.CLASS_DEFINITIONS
        assert "explanation_constraint_profile" in config.CLASS_DEFINITIONS
        assert "validated_by" in config.RELATION_DEFINITIONS
        assert "validate_explanation_candidate" in config.ACTION_DEFINITIONS


# ── Object Store Tests ────────────────────────────────────────────────

class TestObjectStore:
    def test_register_and_get_object(self):
        obj = store.register_object("test_class", account_name="Player.1", properties={"key": "val"})
        assert obj.object_id.startswith("test_class_")
        assert obj.class_name == "test_class"
        assert obj.account_name == "Player.1"
        assert obj.properties["key"] == "val"
        assert obj.qa_status == "pending"

        fetched = store.get_object(obj.object_id)
        assert fetched is not None
        assert fetched.object_id == obj.object_id

    def test_get_objects_by_class(self):
        store.register_object("class_a", account_name="Player.1")
        store.register_object("class_a", account_name="Player.2")
        store.register_object("class_b", account_name="Player.1")
        assert len(store.get_objects_by_class("class_a")) == 2
        assert len(store.get_objects_by_class("class_b")) == 1

    def test_get_objects_by_account(self):
        store.register_object("test_class", account_name="Player.1")
        store.register_object("test_class", account_name="Player.2")
        store.register_object("test_class", account_name="Player.1")
        assert len(store.get_objects_by_account("test_class", "Player.1")) == 2
        assert len(store.get_objects_by_account("test_class", "Player.2")) == 1

    def test_update_object(self):
        obj = store.register_object("test_class", properties={"count": 1})
        updated = store.update_object(obj.object_id, properties={"count": 2})
        assert updated is not None
        assert updated.properties["count"] == 2
        assert updated.revision == 2

    def test_delete_object(self):
        obj = store.register_object("test_class")
        assert store.get_object(obj.object_id) is not None
        assert store.delete_object(obj.object_id) is True
        assert store.get_object(obj.object_id) is None
        assert store.delete_object("nonexistent") is False

    def test_clear(self):
        store.register_object("class_a")
        store.register_object("class_b")
        store.clear()
        assert len(store.get_objects_by_class("class_a")) == 0
        assert len(store.get_objects_by_class("class_b")) == 0


# ── Relation Store Tests ──────────────────────────────────────────────

class TestRelationStore:
    def test_register_and_get_relation(self):
        obj1 = store.register_object("type_a")
        obj2 = store.register_object("type_b")
        rel = store.register_relation(
            source_id=obj1.object_id,
            target_id=obj2.object_id,
            relation_type="connects",
            confidence=0.9,
        )
        assert rel.relation_id.startswith("rel_")
        assert rel.source_id == obj1.object_id
        assert rel.target_id == obj2.object_id
        assert rel.confidence == 0.9

        fetched = store.get_relation(rel.relation_id)
        assert fetched is not None

    def test_get_relations_by_source(self):
        a = store.register_object("type_a")
        b = store.register_object("type_b")
        c = store.register_object("type_c")
        store.register_relation(a.object_id, b.object_id, "relates")
        store.register_relation(a.object_id, c.object_id, "relates")
        rels = store.get_relations(source_id=a.object_id)
        assert len(rels) == 2

    def test_get_relations_by_type(self):
        a = store.register_object("type_a")
        b = store.register_object("type_b")
        store.register_relation(a.object_id, b.object_id, "type_x")
        store.register_relation(b.object_id, a.object_id, "type_y")
        assert len(store.get_relations(relation_type="type_x")) == 1
        assert len(store.get_relations(relation_type="type_y")) == 1

    def test_delete_relation(self):
        a = store.register_object("type_a")
        b = store.register_object("type_b")
        rel = store.register_relation(a.object_id, b.object_id, "connects")
        assert store.delete_relation(rel.relation_id) is True
        assert store.get_relation(rel.relation_id) is None
        assert store.delete_relation("nonexistent") is False

    def test_delete_object_cascades_relations(self):
        a = store.register_object("type_a")
        b = store.register_object("type_b")
        store.register_relation(a.object_id, b.object_id, "connects")
        assert len(store.get_relations(source_id=a.object_id)) == 1
        store.delete_object(a.object_id)
        assert len(store.get_relations(source_id=a.object_id)) == 0

    def test_relation_has_created_at(self):
        a = store.register_object("type_a")
        b = store.register_object("type_b")
        rel = store.register_relation(a.object_id, b.object_id, "connects")
        assert len(rel.created_at) > 0


# ── Graph Query Tests ─────────────────────────────────────────────────

class TestGraphQuery:
    def test_find_related_objects(self):
        a = store.register_object("type_a")
        b = store.register_object("type_b", properties={"item_id": 19976})
        store.register_relation(a.object_id, b.object_id, "owns")
        related = gq.find_related_objects(a.object_id, relation_type="owns")
        assert len(related) == 1
        assert related[0].object_id == b.object_id

    def test_find_related_by_class(self):
        a = store.register_object("type_a")
        b = store.register_object("type_b", properties={"item_id": 19976})
        c = store.register_object("type_c")
        store.register_relation(a.object_id, b.object_id, "owns")
        store.register_relation(a.object_id, c.object_id, "owns")
        related = gq.find_related_objects(a.object_id, relation_type="owns", target_class="type_b")
        assert len(related) == 1
        assert related[0].class_name == "type_b"

    def test_find_source_objects(self):
        a = store.register_object("type_a")
        b = store.register_object("type_b")
        store.register_relation(a.object_id, b.object_id, "owned_by")
        sources = gq.find_source_objects(b.object_id, relation_type="owned_by")
        assert len(sources) == 1
        assert sources[0].object_id == a.object_id

    def test_get_reserved_quantities(self):
        goal = make_goal("Test Goal", account="Player.1")
        r1 = make_reservation(19976, 77, goal.object_id, account="Player.1")
        r2 = make_reservation(19976, 50, goal.object_id, account="Player.2")
        store.register_relation(r1.object_id, goal.object_id, "reserved_for")
        store.register_relation(r2.object_id, goal.object_id, "reserved_for")
        quant = gq.get_reserved_quantities("Player.1")
        assert quant.get(19976) == 77
        quant2 = gq.get_reserved_quantities("Player.2")
        assert quant2.get(19976) == 50

    def test_find_goals_for_item(self):
        goal = make_goal("Aurora", account="Player.1")
        req = make_requirement(goal.object_id, 19976, 77)
        store.register_relation(goal.object_id, req.object_id, "requires")
        goals = gq.find_goals_for_item(19976, "Player.1")
        assert len(goals) >= 1
        assert goals[0]["goal_name"] == "Aurora"
        assert goals[0]["required_count"] == 77

    def test_compute_asset_safe_surplus(self):
        make_asset(19976, 120, account="Player.1")
        goal = make_goal("Aurora", account="Player.1")
        req = make_requirement(goal.object_id, 19976, 77)
        store.register_relation(goal.object_id, req.object_id, "requires")
        result = gq.compute_asset_safe_surplus(19976, "Player.1")
        assert result["total_owned"] == 120
        assert result["safe_surplus"] == 43
        assert len(result["goals"]) >= 1


# ── Impact Analyzer Tests ─────────────────────────────────────────────

class TestImpactAnalyzer:
    @pytest.mark.asyncio
    async def test_analyze_sell_impact_low_risk(self):
        make_asset(19976, 120, account="Player.1")
        goal = make_goal("Aurora", account="Player.1")
        req = make_requirement(goal.object_id, 19976, 77)
        store.register_relation(goal.object_id, req.object_id, "requires")

        report = await analyze_sell_impact(19976, 10, "Player.1", "Mystic Coin")
        assert report.risk_level == "low"
        assert report.safe_surplus == 43
        assert "Safe to sell" in report.recommendation

    @pytest.mark.asyncio
    async def test_analyze_sell_impact_high_risk(self):
        make_asset(19976, 50, account="Player.1")
        goal = make_goal("Aurora", account="Player.1")
        req = make_requirement(goal.object_id, 19976, 77)
        store.register_relation(goal.object_id, req.object_id, "requires")

        report = await analyze_sell_impact(19976, 30, "Player.1", "Mystic Coin")
        assert report.risk_level == "high"
        assert len(report.blocked_goals) > 0
        assert "Do not sell" in report.recommendation

    @pytest.mark.asyncio
    async def test_analyze_sell_impact_item_not_found(self):
        report = await analyze_sell_impact(99999, 1, "Player.1", "Unknown Item")
        assert len(report.warnings) > 0
        assert "not found" in report.warnings[0].lower()

    @pytest.mark.asyncio
    async def test_analyze_sell_impact_multiple_goals(self):
        make_asset(19976, 200, account="Player.1")
        g1 = make_goal("Aurora", account="Player.1")
        g2 = make_goal("Vision", account="Player.1")
        make_requirement(g1.object_id, 19976, 77)
        make_requirement(g2.object_id, 19976, 77)
        store.register_relation(g1.object_id, g1.object_id, "requires")
        store.register_relation(g2.object_id, g2.object_id, "requires")

        report = await analyze_sell_impact(19976, 100, "Player.1", "Mystic Coin")
        assert report.risk_level == "low"  # 200 > 77+77=154, selling 100 leaves 100
        assert report.safe_surplus >= 0

    @pytest.mark.asyncio
    async def test_compute_safe_surplus(self):
        with patch("gw2_progression.ontology.impact_analyzer.using_db") as mock_db_ctx:
            mock_db = AsyncMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock()

            with patch("gw2_progression.ontology.impact_analyzer.load_latest_holdings", AsyncMock(return_value=[])):
                make_asset(19976, 120, account="Player.1")
                result = await compute_safe_surplus(19976, "Player.1")
                assert result.total_owned >= 0
                assert isinstance(result, SafeSurplusResult)


# ── QA Gate Tests ─────────────────────────────────────────────────────

class TestQAGate:
    def test_validate_object_unknown_class(self):
        obj = OntologyObject(object_id="o1", class_name="nonexistent")
        qa = validate_object(obj)
        assert qa.status == "fail"
        assert len(qa.blocking_errors) > 0

    def test_validate_object_missing_required_property(self):
        obj = OntologyObject(
            object_id="o2",
            class_name="account_asset",
            properties={"item_id": 19976},
        )
        qa = validate_object(obj)
        assert qa.status == "fail"
        assert any("count" in e for e in qa.blocking_errors)

    def test_validate_object_valid(self):
        obj = OntologyObject(
            object_id="o3",
            class_name="account_asset",
            properties={"item_id": 19976, "count": 50, "location": "material_storage"},
        )
        qa = validate_object(obj)
        assert qa.status == "pass"

    def test_validate_explanation_candidate_object_valid(self):
        obj = OntologyObject(
            object_id="exp1",
            class_name="explanation_candidate",
            properties={
                "output_item_id": "19865",
                "note": "Carrion Silk Insignia is suitable for a small first craft.",
                "source": "provider",
                "report_language": "en",
            },
        )
        qa = validate_object(obj)
        assert qa.status == "pass"

    def test_validate_explanation_candidate_language_invalid(self):
        obj = OntologyObject(
            object_id="exp2",
            class_name="explanation_candidate",
            properties={
                "output_item_id": "19865",
                "note": "Carrion Silk Insignia is suitable.",
                "source": "provider",
                "report_language": "fr",
            },
        )
        qa = validate_object(obj)
        assert qa.status == "fail"


class TestExplanationConstraints:
    def test_provider_explanation_passes_ontology_constraints(self):
        from gw2_progression.ontology.explanation_constraints import build_explanation_facts, validate_explanation_candidate

        risk = {"level": "low"}
        facts = build_explanation_facts(
            {
                "output_item_name": "Carrion Silk Insignia",
                "output_item_id": "19865",
                "craftable_now": 273,
                "missing_total_count": 0,
                "net_profit": 187,
                "craft_cost": 237,
                "roi": 0.789,
            },
            risk,
            language="en",
        )
        result = validate_explanation_candidate(
            "Carrion Silk Insignia is suitable for a small first craft: you can craft it 273 time(s), sample net profit is 1s 87c with ROI 0.789, and market risk is low. Re-check prices before scaling.",
            facts,
            risk,
            category="do_now",
        )

        assert result.passed is True
        assert result.checks["profit_preserved"] is True
        assert "entity_layer" in result.constraint_layers

    def test_provider_explanation_blocks_coin_scale_error(self):
        from gw2_progression.ontology.explanation_constraints import build_explanation_facts, validate_explanation_candidate

        risk = {"level": "low"}
        facts = build_explanation_facts(
            {
                "output_item_name": "Carrion Silk Insignia",
                "output_item_id": "19865",
                "craftable_now": 273,
                "missing_total_count": 0,
                "net_profit": 187,
                "craft_cost": 237,
                "roi": 0.789,
            },
            risk,
            language="en",
        )
        result = validate_explanation_candidate(
            "Carrion Silk Insignia can earn 1 gold 87 copper with low risk, so mass craft it now.",
            facts,
            risk,
            category="do_now",
        )

        assert result.passed is False
        assert "no_profit_currency_scale_error" in result.violations
        assert "no_overconfident_scale_up" in result.violations

    def test_validate_object_safe_surplus_valid(self):
        obj = OntologyObject(
            object_id="o4",
            class_name="safe_surplus",
            properties={"item_id": 19976, "total_owned": 120, "total_reserved": 77, "safe_surplus": 43},
        )
        qa = validate_object(obj)
        assert qa.status == "pass"

    def test_validate_object_safe_surplus_negative(self):
        obj = OntologyObject(
            object_id="o5",
            class_name="safe_surplus",
            properties={"item_id": 19976, "total_owned": 50, "total_reserved": 77, "safe_surplus": -27},
        )
        qa = validate_object(obj)
        assert qa.status == "fail"

    def test_validate_object_build_unreviewed(self):
        obj = OntologyObject(
            object_id="o6",
            class_name="build",
            properties={
                "build_id": "test_build",
                "source": "unreviewed",
                "profession": "Guardian",
                "patch_version": "2025.01",
            },
        )
        qa = validate_object(obj)
        assert qa.status == "fail"

    @pytest.mark.asyncio
    async def test_check_report_publishable_fresh(self):
        qa = await check_report_publishable({
            "report_id": 1,
            "snapshot_time": _fresh_ts(),
            "access_level": "private",
            "recommendations": ["Do X", "Do Y"],
        })
        assert qa.status == "pass"
        assert qa.passed >= 1

    @pytest.mark.asyncio
    async def test_check_report_publishable_no_snapshot(self):
        qa = await check_report_publishable({
            "report_id": 2,
            "snapshot_time": "",
            "access_level": "private",
        })
        assert qa.status == "fail"
        assert any("snapshot" in e.lower() for e in qa.blocking_errors)

    @pytest.mark.asyncio
    async def test_check_report_publishable_api_key_leak(self):
        qa = await check_report_publishable({
            "report_id": 3,
            "snapshot_time": "2026-06-26T12:00:00",
            "access_level": "public",
            "api_key": "ABCDEF01-2345-6789-ABCD-EF0123456789AB",
        })
        assert qa.status == "fail"
        assert any("API key" in e for e in qa.blocking_errors)


# ── Account Mapper Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestAccountMapper:
    async def test_sync_account_to_ontology(self):
        mock_holdings = [
            type("H", (), {"item_id": 19976, "count": 120, "location_type": "material_storage", "location_ref": "", "tradable": True, "value_buy": 50000, "value_sell": 48000, "binding_status": "", "confidence": 0.9})(),
            type("H", (), {"item_id": 46765, "count": 1, "location_type": "bank", "location_ref": "", "tradable": False, "value_buy": 0, "value_sell": 0, "binding_status": "AccountBound", "confidence": 1.0})(),
        ]

        from gw2_progression.ontology.account_mapper import sync_account_to_ontology

        with patch("gw2_progression.ontology.account_mapper.using_db") as mock_db_ctx, \
             patch("gw2_progression.ontology.account_mapper.load_latest_holdings", AsyncMock(return_value=mock_holdings)):
            mock_db = AsyncMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock()

            objs = await sync_account_to_ontology("fake-key-12345678", "Player.1")

        snapshots = [o for o in objs if o.class_name == "account_snapshot"]
        assets = [o for o in objs if o.class_name == "account_asset"]
        assert len(snapshots) == 1
        assert len(assets) == 2
        assert snapshots[0].account_name == "Player.1"

        owns_rels = store.get_relations(source_id=snapshots[0].object_id, relation_type="owns")
        assert len(owns_rels) == 2

    async def test_sync_empty_account(self):
        with patch("gw2_progression.ontology.account_mapper.using_db") as mock_db_ctx, \
             patch("gw2_progression.ontology.account_mapper.load_latest_holdings", AsyncMock(return_value=[])):
            mock_db = AsyncMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock()

            objs = await sync_account_to_ontology("fake-key-12345678", "Player.Empty")
        assert len(objs) == 1  # snapshot with no assets
        assert objs[0].class_name == "account_snapshot"


# ── Goal Mapper Tests ─────────────────────────────────────────────────

class TestGoalMapper:
    def test_map_goal_to_ontology(self):
        goal = TrackedGoal(
            goal_id="test_goal_1",
            account_name="Player.1",
            target_item_id=19976,
            target_count=77,
            status="active",
            priority="high",
        )
        objs = map_goal_to_ontology(goal)
        goals = [o for o in objs if o.class_name == "legendary_goal"]
        reqs = [o for o in objs if o.class_name == "goal_requirement"]
        assert len(goals) == 1
        assert goals[0].account_name == "Player.1"
        assert goals[0].properties["priority"] == "high"

    def test_map_multiple_goals(self):
        g1 = TrackedGoal(goal_id="g1", account_name="Player.1", target_item_id=46765, status="active")
        g2 = TrackedGoal(goal_id="g2", account_name="Player.1", target_item_id=84767, status="active")
        map_goal_to_ontology(g1)
        map_goal_to_ontology(g2)
        assert len(store.get_objects_by_class("legendary_goal")) == 2
        assert len(store.get_objects_by_class("goal_requirement")) >= 2

    @pytest.mark.asyncio
    async def test_sync_goal_reservations(self):
        g1_obj = make_goal("Goal A", account="Player.1", status="active")
        r1 = make_requirement(g1_obj.object_id, 19976, 77)
        store.register_relation(g1_obj.object_id, r1.object_id, "requires")

        store.clear()
        g1_obj = make_goal("Goal A", account="Player.1", status="active")
        r1 = make_requirement(g1_obj.object_id, 19976, 77)
        store.register_relation(g1_obj.object_id, r1.object_id, "requires")

        count = await sync_goal_reservations("Player.1")
        assert count >= 1
        reservations = store.get_objects_by_class("reserved_asset")
        assert len(reservations) >= 1
        assert reservations[0].properties["item_id"] == 19976
        assert reservations[0].properties["reserved_count"] == 77

    @pytest.mark.asyncio
    async def test_sync_goal_reservations_skips_inactive(self):
        g1 = make_goal("Goal A", account="Player.1", status="completed")
        r1 = make_requirement(g1.object_id, 19976, 77)
        store.register_relation(g1.object_id, r1.object_id, "requires")

        count = await sync_goal_reservations("Player.1")
        assert count == 0


# ── Action Registry Tests ─────────────────────────────────────────────

class TestActionRegistry:
    @pytest.mark.asyncio
    async def test_execute_unknown_action_fails(self):
        from gw2_progression.ontology.action_registry import execute_action
        with pytest.raises(ValueError, match="Unknown action"):
            await execute_action("nonexistent_action")

    @pytest.mark.asyncio
    async def test_execute_action_preconditions_blocked(self):
        from gw2_progression.ontology.action_registry import execute_action
        with patch("gw2_progression.ontology.action_registry.persist_action", AsyncMock()):
            action = await execute_action(
                "create_legendary_goal",
                account_name="Player.1",
                params={"goal_id": "test", "template_id": "leg_test"},
            )
        assert action.preconditions_met is False
        assert "Preconditions not met" in action.error


# ── End-to-End Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
class TestEndToEnd:
    async def test_legendary_do_not_sell_flow(self):
        make_asset(19976, 120, account="Player.E2E")
        goal_obj = make_goal("Aurora", account="Player.E2E", status="active")
        req_obj = make_requirement(goal_obj.object_id, 19976, 77)
        store.register_relation(goal_obj.object_id, req_obj.object_id, "requires")
        await sync_goal_reservations("Player.E2E")

        result = gq.compute_asset_safe_surplus(19976, "Player.E2E")
        assert result["safe_surplus"] == 43

        report = await analyze_sell_impact(19976, 10, "Player.E2E", "Mystic Coin")
        assert report.risk_level == "low"
        assert report.safe_surplus == 43

    async def test_report_qa_gate_flow(self):
        qa = await check_report_publishable({
            "report_id": 42,
            "snapshot_time": _fresh_ts(),
            "access_level": "public",
            "recommendations": ["Sell excess Mystic Coins"],
        })
        assert qa.status == "pass"

        qa_blocked = await check_report_publishable({
            "report_id": 43,
            "snapshot_time": "",
            "access_level": "public",
            "recommendations": [],
        })
        assert qa_blocked.status == "fail"


# ── Phase B: Build Fit Trust Tests ────────────────────────────────────

class TestBuildTrust:
    def test_evaluate_fresh_build(self):
        from gw2_progression.ontology.build_trust import evaluate_build_source_freshness
        from gw2_progression.models import BuildTemplate

        build = BuildTemplate(
            build_id="sc_dh",
            source="snowcrows",
            name="Dragonhunter",
            profession="Guardian",
            patch_version="2026.06",
            review_status="reviewed",
        )
        result = evaluate_build_source_freshness(build)
        assert result["trust_level"] == "high"
        assert result["recommendation_strength"] == "strong"
        assert result["is_stale"] is False
        assert result["is_weak"] is False

    def test_evaluate_weak_build(self):
        from gw2_progression.ontology.build_trust import evaluate_build_source_freshness, WEAK_PATCH_DAYS, STALE_PATCH_DAYS
        from gw2_progression.models import BuildTemplate

        build = BuildTemplate(
            build_id="old_build",
            source="metabattle",
            name="Old Build",
            profession="Guardian",
            patch_version="2025.01",
            review_status="reviewed",
        )
        result = evaluate_build_source_freshness(build)
        assert result["days_old"] is not None
        if result["days_old"] > STALE_PATCH_DAYS:
            assert result["recommendation_strength"] == "none"
        elif result["days_old"] > WEAK_PATCH_DAYS:
            assert result["recommendation_strength"] == "weak"

    def test_unreviewed_build_no_recommendation(self):
        from gw2_progression.ontology.build_trust import evaluate_build_source_freshness
        from gw2_progression.models import BuildTemplate

        build = BuildTemplate(
            build_id="unreviewed",
            source="user",
            name="Custom Build",
            profession="Guardian",
            patch_version="2026.06",
            review_status="unreviewed",
        )
        result = evaluate_build_source_freshness(build)
        assert result["recommendation_strength"] == "none"
        assert result["trust_level"] == "low"

    def test_filter_recommendations_by_freshness(self):
        from gw2_progression.ontology.build_trust import filter_recommendations_by_freshness
        from gw2_progression.models import BuildTemplate

        builds = [
            BuildTemplate(build_id="b1", source="sc", name="Fresh", profession="Guardian", patch_version="2026.06", review_status="reviewed"),
            BuildTemplate(build_id="b2", source="mb", name="Unreviewed", profession="Guardian", patch_version="2026.06", review_status="unreviewed"),
        ]
        result = filter_recommendations_by_freshness(builds, max_results=2)
        assert len(result) == 2
        assert result[0]["build_id"] == "b1"
        assert result[0]["recommendation_strength"] == "strong"
        assert result[1]["recommendation_strength"] == "none"

    def test_get_build_confidence(self):
        from gw2_progression.ontology.build_trust import get_build_recommendation_confidence
        from gw2_progression.models import BuildTemplate

        fresh = BuildTemplate(build_id="b1", source="sc", name="Fresh", profession="Guardian", patch_version="2026.06", review_status="reviewed")
        assert get_build_recommendation_confidence(fresh) == 0.85

        weak = BuildTemplate(build_id="b2", source="mb", name="Weak", profession="Guardian", patch_version="2025.01", review_status="reviewed")
        conf = get_build_recommendation_confidence(weak)
        assert conf <= 0.85

        unreviewed = BuildTemplate(build_id="b3", source="user", name="Custom", profession="Guardian", patch_version="2026.06", review_status="unreviewed")
        assert get_build_recommendation_confidence(unreviewed) == 0.0


# ── Phase C: Report Mapper Tests ──────────────────────────────────────

@pytest.mark.asyncio
class TestReportMapper:
    async def test_map_report_to_evidence(self):
        from gw2_progression.ontology.report_mapper import map_report_to_evidence

        qa = QAReport(
            target_object_id="report_1",
            target_class="report",
            checks=[{"check": "snapshot_exists", "passed": True}],
            passed=1,
            failed=0,
            status="pass",
            checked_at="2026-06-26T12:00:00",
        )
        objs = await map_report_to_evidence(
            report_data={
                "report_id": 1,
                "report_type": "full",
                "access_level": "private",
                "snapshot_time": _fresh_ts(),
                "recommendations": ["Do X", "Do Y", "Do Z"],
            },
            account_name="Player.1",
            qa_report=qa,
        )
        report_objs = [o for o in objs if o.class_name == "report"]
        evidence_objs = [o for o in objs if o.class_name == "evidence"]
        assert len(report_objs) == 1
        assert len(evidence_objs) == 4  # 3 recommendations + 1 QA report

    async def test_publication_requirements_pass(self):
        from gw2_progression.ontology.report_mapper import check_publication_requirements

        qa = QAReport(target_object_id="r1", target_class="report", passed=1, failed=0, status="pass", checked_at="now")
        result = check_publication_requirements(
            {"report_id": 1, "access_level": "private", "snapshot_time": _fresh_ts()},
            qa,
        )
        assert result["publishable"] is True

    async def test_publication_requirements_blocked(self):
        from gw2_progression.ontology.report_mapper import check_publication_requirements
        result = check_publication_requirements({"report_id": 1}, None)
        assert result["publishable"] is False
        assert "qa_report" in result["missing_requirements"]


# ── Phase B + C E2E Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
class TestBuildAndReportE2E:
    async def test_build_trust_in_report_gate(self):
        from gw2_progression.ontology.qa_gate import check_report_publishable

        qa = await check_report_publishable({
            "report_id": 100,
            "snapshot_time": _fresh_ts(),
            "access_level": "public",
            "recommendations": ["Try Dragonhunter build"],
            "build_details": [
                {
                    "build_id": "sc_dh",
                    "name": "Dragonhunter",
                    "source": "snowcrows",
                    "profession": "Guardian",
                    "patch_version": "2026.06",
                    "review_status": "reviewed",
                },
            ],
            "report_type": "free",
        })
        assert qa.status == "pass"

    async def test_build_trust_blocks_unreviewed(self):
        from gw2_progression.ontology.qa_gate import check_report_publishable

        qa = await check_report_publishable({
            "report_id": 101,
            "snapshot_time": "2026-06-26T12:00:00",
            "access_level": "public",
            "recommendations": ["Try custom build"],
            "build_details": [
                {
                    "build_id": "custom_1",
                    "name": "My Build",
                    "source": "user",
                    "profession": "Guardian",
                    "patch_version": "2026.06",
                    "review_status": "unreviewed",
                },
            ],
            "report_type": "free",
        })
        assert qa.status == "fail"
        assert any("unreviewed" in e.lower() for e in qa.blocking_errors)

    async def test_report_mapper_and_qa_e2e(self):
        from gw2_progression.ontology.qa_gate import check_report_publishable
        from gw2_progression.ontology.report_mapper import check_publication_requirements, map_report_to_evidence

        report_data = {
            "report_id": 200,
            "report_type": "commercial",
            "access_level": "public",
            "snapshot_time": _fresh_ts(),
            "recommendations": ["Sell excess materials"],
        }
        qa = await check_report_publishable(report_data)
        assert qa.status == "pass"

        objs = await map_report_to_evidence(report_data, "Player.E2E", qa)
        assert len(objs) >= 2

        pub = check_publication_requirements(report_data, qa)
        assert pub["publishable"] is True


# ── Phase D: Market Domain Tests ──────────────────────────────────────

class TestMarketMapper:
    def test_map_sell_candidate(self):
        from gw2_progression.ontology.market_mapper import map_signal_to_ontology
        from gw2_progression.models import TradingPostSignal

        signal = TradingPostSignal(
            item_id=19976,
            signal_type="sell_candidate",
            severity="info",
            reason="Mystic Coin surplus available",
            current_buy_price=20000,
            current_sell_price=21000,
            spread_ratio=0.05,
            quantity_owned=120,
            value_owned=2400000,
            confidence=0.78,
            data_sources=["gw2_commerce_prices"],
            price_timestamp="2026-06-26T12:00:00",
        )
        obj = map_signal_to_ontology(signal, "Player.1")
        assert obj.class_name == "sell_candidate"
        assert obj.properties["item_id"] == 19976
        assert obj.properties["signal_type"] == "sell_candidate"

    def test_map_sell_candidate_stale_price(self):
        from gw2_progression.ontology.market_mapper import map_signal_to_ontology
        from gw2_progression.models import TradingPostSignal

        old_signal = TradingPostSignal(
            item_id=19976,
            signal_type="sell_candidate",
            price_timestamp="2020-01-01T00:00:00",
        )
        obj = map_signal_to_ontology(old_signal, "Player.1")
        assert obj.properties.get("price_stale") is True

    def test_get_active_sell_candidates(self):
        from gw2_progression.ontology.market_mapper import get_active_sell_candidates, map_signal_to_ontology
        from gw2_progression.models import TradingPostSignal

        for i in range(3):
            map_signal_to_ontology(TradingPostSignal(item_id=i, signal_type="sell_candidate"), "Player.1")
        candidates = get_active_sell_candidates("Player.1")
        assert len(candidates) == 3

    def test_get_protected_market_assets(self):
        from gw2_progression.ontology.market_mapper import map_signal_to_ontology, get_protected_market_assets
        from gw2_progression.models import TradingPostSignal

        map_signal_to_ontology(TradingPostSignal(item_id=19976, signal_type="protected_asset"), "Player.1")
        protected = get_protected_market_assets("Player.1")
        assert len(protected) == 1
        assert protected[0].class_name == "protected_market_asset"

    def test_check_price_freshness(self):
        from gw2_progression.ontology.market_mapper import check_price_freshness, map_signal_to_ontology
        from gw2_progression.models import TradingPostSignal

        map_signal_to_ontology(TradingPostSignal(item_id=19976, signal_type="sell_candidate", price_timestamp=_fresh_ts()), "Player.1")
        result = check_price_freshness(19976, "Player.1")
        assert result["is_stale"] is False
        assert result["item_id"] == 19976

        result_missing = check_price_freshness(99999, "Player.1")
        assert result_missing["is_stale"] is True


# ── Delta Sync Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
class TestDeltaSync:
    async def test_delta_sync_updates_existing(self):
        from gw2_progression.ontology.account_mapper import sync_account_to_ontology

        with patch("gw2_progression.ontology.account_mapper.using_db") as mock_ctx, \
             patch("gw2_progression.ontology.account_mapper.load_latest_holdings") as mock_holdings:
            mock_db = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock()
            mock_holdings.return_value = [
                type("H", (), {"item_id": 19976, "count": 120, "location_type": "material_storage", "location_ref": "", "tradable": True, "value_buy": 50000, "value_sell": 48000, "binding_status": "", "confidence": 0.9})(),
            ]

            objs1 = await sync_account_to_ontology("key", "Delta.Player")
            assert len(objs1) >= 1

            mock_holdings.return_value = [
                type("H", (), {"item_id": 19976, "count": 150, "location_type": "material_storage", "location_ref": "", "tradable": True, "value_buy": 60000, "value_sell": 57000, "binding_status": "", "confidence": 0.9})(),
            ]
            objs2 = await sync_account_to_ontology("key", "Delta.Player")

            assets = store.get_objects_by_account("account_asset", "Delta.Player")
            mystic_coin_assets = [a for a in assets if a.properties.get("item_id") == 19976]
            assert len(mystic_coin_assets) == 1
            assert mystic_coin_assets[0].properties["count"] == 150

    async def test_delta_sync_adds_new_items(self):
        from gw2_progression.ontology.account_mapper import sync_account_to_ontology

        with patch("gw2_progression.ontology.account_mapper.using_db") as mock_ctx, \
             patch("gw2_progression.ontology.account_mapper.load_latest_holdings") as mock_holdings:
            mock_db = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock()

            mock_holdings.return_value = [
                type("H", (), {"item_id": 19976, "count": 120, "location_type": "material_storage", "location_ref": "", "tradable": True, "value_buy": 50000, "value_sell": 48000, "binding_status": "", "confidence": 0.9})(),
                type("H", (), {"item_id": 46765, "count": 1, "location_type": "bank", "location_ref": "", "tradable": False, "value_buy": 0, "value_sell": 0, "binding_status": "AccountBound", "confidence": 1.0})(),
            ]
            objs = await sync_account_to_ontology("key", "Delta.New")
            assets = [o for o in objs if o.class_name == "account_asset"]
            assert len(assets) == 2


# ── Error Handling Tests ──────────────────────────────────────────────

class TestOntologyExceptions:
    def test_exception_hierarchy(self):
        from gw2_progression.ontology.exceptions import (
            OntologyError, ObjectNotFoundError, RelationNotFoundError,
            ValidationError, PreconditionFailedError, PersistenceError,
        )
        assert issubclass(ObjectNotFoundError, OntologyError)
        assert issubclass(RelationNotFoundError, OntologyError)
        assert issubclass(ValidationError, OntologyError)
        assert issubclass(PreconditionFailedError, OntologyError)
        assert issubclass(PersistenceError, OntologyError)

    def test_object_not_found_raised(self):
        from gw2_progression.ontology.exceptions import ObjectNotFoundError
        with pytest.raises(ObjectNotFoundError):
            raise ObjectNotFoundError("Object not found")

    def test_persistence_error_raised(self):
        from gw2_progression.ontology.exceptions import PersistenceError
        with pytest.raises(PersistenceError):
            raise PersistenceError("DB failed")


# ── Object Store Retry Tests ─────────────────────────────────────────

@pytest.mark.asyncio
class TestObjectStoreRetry:
    async def test_with_retry_succeeds(self):
        from gw2_progression.ontology.object_store import _with_retry

        call_count = 0

        async def succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("First attempt fails")
            return "success"

        result = await _with_retry(succeeds)
        assert result == "success"
        assert call_count == 2

    async def test_with_retry_exhausted(self):
        from gw2_progression.ontology.object_store import _with_retry, _MAX_RETRIES
        from gw2_progression.ontology.exceptions import PersistenceError

        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")

        with pytest.raises(PersistenceError):
            await _with_retry(always_fails)
        assert call_count == _MAX_RETRIES


# ── Phase D1: Guild Workspace Tests ───────────────────────────────────

class TestGuildMapper:
    @pytest.mark.asyncio
    async def test_map_guild_to_ontology(self):
        from gw2_progression.ontology.guild_mapper import map_guild_to_ontology

        guild_data = {
            "id": 1,
            "name": "Test Guild",
            "invite_code": "abc123",
            "members": [
                {"account_name": "Player.1", "role": "leader", "joined_at": "2026-01-01"},
                {"account_name": "Player.2", "role": "member", "joined_at": "2026-02-01"},
            ],
        }
        objs = await map_guild_to_ontology(guild_data)
        guilds = [o for o in objs if o.class_name == "guild_workspace"]
        members = [o for o in objs if o.class_name == "guild_member"]
        assert len(guilds) == 1
        assert len(members) == 2
        assert guilds[0].properties["name"] == "Test Guild"

    @pytest.mark.asyncio
    async def test_sync_guild_goals(self):
        from gw2_progression.ontology.guild_mapper import map_guild_to_ontology, sync_guild_goals

        guild_data = {"id": 2, "name": "Shared Guild", "invite_code": "xyz", "members": [
            {"account_name": "Player.A"},
            {"account_name": "Player.B"},
        ]}
        await map_guild_to_ontology(guild_data)

        from gw2_progression.ontology.goal_mapper import map_goal_to_ontology
        map_goal_to_ontology(TrackedGoal(goal_id="g1", account_name="Player.A", target_item_id=46765, status="active"))
        map_goal_to_ontology(TrackedGoal(goal_id="g2", account_name="Player.B", target_item_id=46765, status="active"))

        count = await sync_guild_goals(2, ["Player.A", "Player.B"])
        assert count >= 1

        goals = store.get_objects_by_class("guild_goal")
        assert len(goals) >= 1

    def test_get_guild_member_objects(self):
        from gw2_progression.ontology.guild_mapper import get_guild_member_objects

        store.register_object("guild_member", properties={"guild_id": 1, "role": "member"})
        store.register_object("guild_member", properties={"guild_id": 2, "role": "member"})
        members = get_guild_member_objects(1)
        assert len(members) == 1


# ── Phase D2: Quest Mapper Tests ──────────────────────────────────────

class TestQuestMapper:
    def test_map_quest_to_ontology(self):
        from gw2_progression.ontology.quest_mapper import map_quest_to_ontology

        obj = map_quest_to_ontology("goal_progress", "Work on legendary", "Player.1")
        assert obj.class_name == "quest_goal"
        assert obj.properties["quest_key"] == "goal_progress"

    def test_map_achievement_to_ontology(self):
        from gw2_progression.ontology.quest_mapper import map_achievement_to_ontology

        obj = map_achievement_to_ontology(1001, "Mystic Tribune", "Player.1", current=3, max_count=5)
        assert obj.class_name == "achievement"
        assert obj.properties["progress_pct"] == 60.0
        assert obj.properties["done"] is False

    def test_achievement_done(self):
        from gw2_progression.ontology.quest_mapper import map_achievement_to_ontology

        obj = map_achievement_to_ontology(1002, "Complete", "Player.1", current=5, max_count=5, done=True)
        assert obj.properties["done"] is True
        assert obj.properties["progress_pct"] == 100.0

    def test_quest_class_map_completeness(self):
        from gw2_progression.ontology.quest_mapper import COACH_QUEST_CLASS_MAP
        from gw2_progression.services.quest_service import COACH_QUESTS

        keys_in_map = set(COACH_QUEST_CLASS_MAP.keys())
        keys_in_coach = set(q["key"] for q in COACH_QUESTS)
        assert keys_in_coach.issubset(keys_in_map), f"Missing quest keys: {keys_in_coach - keys_in_map}"

    @pytest.mark.asyncio
    async def test_get_quests_by_account(self):
        from gw2_progression.ontology.quest_mapper import get_quests_by_account, map_quest_to_ontology

        map_quest_to_ontology("sell_liquidate", "Sell items", "Player.Q", completed=True)
        map_quest_to_ontology("goal_progress", "Goal work", "Player.Q")
        quests = get_quests_by_account("Player.Q")
        assert len(quests) == 2

    @pytest.mark.asyncio
    async def test_get_completed_quests(self):
        from gw2_progression.ontology.quest_mapper import get_completed_quests, map_quest_to_ontology

        map_quest_to_ontology("fractal_push", "Fractals", "Player.Q", completed=True)
        map_quest_to_ontology("wvw_pvp", "WvW", "Player.Q", completed=False)
        done = get_completed_quests("Player.Q")
        assert len(done) == 1
        assert done[0].properties["quest_key"] == "fractal_push"

    def test_weekly_quest_progress(self):
        from gw2_progression.ontology.quest_mapper import get_weekly_quest_progress, map_quest_to_ontology

        map_quest_to_ontology("sell_liquidate", "Sell", "Player.W", completed=True)
        map_quest_to_ontology("goal_progress", "Goal", "Player.W", completed=True)
        map_quest_to_ontology("build_gear", "Build", "Player.W", completed=False)
        prog = get_weekly_quest_progress("Player.W")
        assert prog["total"] == 3
        assert prog["completed"] == 2
        assert prog["progress_pct"] == 66.7


class TestOntologyRuntimeKernel:
    def test_registry_loads_project_schema_and_rejects_invalid_entity(self):
        from gw2_progression.ontology import OntologyRegistry

        registry = OntologyRegistry.from_project_config()
        errors = registry.validate_action(
            {
                "type": "add_entity",
                "entity": {
                    "id": "asset:1",
                    "type": "account_asset",
                    "properties": {"item_id": 19721, "count": 5},
                },
            },
            None,
        )

        assert "account_asset" in registry.entities
        assert "owns" in registry.relations
        assert "add_entity" in registry.actions
        assert "Missing required property: location" in errors

    def test_kernel_executes_actions_records_lineage_and_queries_graph(self):
        from gw2_progression.ontology import OntologyRuntimeKernel

        kernel = OntologyRuntimeKernel()
        account = {
            "type": "add_entity",
            "entity": {
                "id": "account:Netro.7195",
                "type": "account_snapshot",
                "properties": {"account_name": "Netro.7195", "snapshot_id": "snap-1"},
            },
        }
        asset = {
            "type": "add_entity",
            "entity": {
                "id": "asset:19721",
                "type": "account_asset",
                "properties": {"item_id": 19721, "count": 5, "location": "material_storage", "unit_value": 3},
            },
        }
        relation = {
            "type": "add_relation",
            "relation": {
                "source": "account:Netro.7195",
                "target": "asset:19721",
                "relation_type": "owns",
            },
        }

        first = kernel.execute(account)
        kernel.execute(asset)
        third = kernel.execute(relation)
        trace = kernel.query().traverse("account:Netro.7195")
        impact = kernel.query().economy_impact("asset:19721")

        assert first["delta"]["added_entities"] == ["account:Netro.7195"]
        assert third["delta"]["relation_delta"] == 1
        assert len(kernel.snapshot()["lineage"]) == 3
        assert trace["visited"] == ["account:Netro.7195", "asset:19721"]
        assert impact["estimated_value"] == 15

    def test_kernel_state_transition_is_deterministic_for_same_actions(self):
        from gw2_progression.ontology import OntologyRuntimeKernel

        actions = [
            {
                "type": "add_entity",
                "entity": {
                    "id": "asset:1",
                    "type": "account_asset",
                    "properties": {"item_id": 1, "count": 1, "location": "bank"},
                },
            },
            {"type": "update_entity", "entity_id": "asset:1", "patch": {"count": 2}},
        ]
        left = OntologyRuntimeKernel()
        right = OntologyRuntimeKernel()
        for action in actions:
            left.execute(action)
            right.execute(action)

        assert left.snapshot()["state_hash"] == right.snapshot()["state_hash"]
        assert left.snapshot()["state"] == right.snapshot()["state"]

    def test_llm_constrained_reasoning_rejects_invalid_graph_action(self):
        from gw2_progression.ontology import OntologyRuntimeKernel

        kernel = OntologyRuntimeKernel()
        invalid = kernel.execute_llm_action({
            "type": "add_relation",
            "relation": {
                "source": "missing:source",
                "target": "missing:target",
                "relation_type": "owns",
            },
        })

        assert invalid["status"] == "rejected"
        assert invalid["validation"]["accepted"] is False
        assert any("does not exist" in error for error in invalid["validation"]["errors"])

    def test_replay_reconstructs_final_state_from_lineage(self):
        from gw2_progression.ontology import OntologyRuntimeKernel

        kernel = OntologyRuntimeKernel()
        kernel.execute({
            "type": "add_entity",
            "entity": {
                "id": "asset:2",
                "type": "account_asset",
                "properties": {"item_id": 2, "count": 3, "location": "wallet"},
            },
        })
        kernel.execute({"type": "update_entity", "entity_id": "asset:2", "patch": {"count": 8}})
        snapshot = kernel.snapshot()
        replay = kernel.replay()

        assert replay["deterministic"] is True
        assert replay["mismatches"] == []
        assert replay["state"].to_dict() == snapshot["state"]

    def test_ingestion_pipeline_normalizes_raw_gw2_payload_into_runtime_graph(self):
        from gw2_progression.ontology import GW2APINormalizer, GraphBuilder, OntologyRuntimeKernel

        raw = {
            "account": {"name": "Pipe.1234"},
            "snapshot_id": "snap-pipe",
            "assets": [{"item_id": 19721, "count": 4, "category": "material_storage", "total_value": 12}],
        }
        normalized = GW2APINormalizer().normalize(raw)
        graph = GraphBuilder().build(normalized["entities"], normalized["relations"])
        result = OntologyRuntimeKernel().ingest_normalized(normalized)

        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert result["entity_count"] == 2
        assert result["relation_count"] == 1
        assert result["status"] == "completed"

    def test_execution_graph_runs_actions_in_dependency_order(self):
        from gw2_progression.ontology import OntologyRuntimeKernel

        kernel = OntologyRuntimeKernel()
        result = kernel.execute_graph([
            {
                "node_id": "account",
                "type": "add_entity",
                "entity": {
                    "id": "account:Dag.1234",
                    "type": "account_snapshot",
                    "properties": {"account_name": "Dag.1234", "snapshot_id": "dag-1"},
                },
            },
            {
                "node_id": "asset",
                "depends_on": ["account"],
                "type": "add_entity",
                "entity": {
                    "id": "asset:dag",
                    "type": "account_asset",
                    "properties": {"item_id": 19721, "count": 1, "location": "bank"},
                },
            },
            {
                "node_id": "owns",
                "depends_on": ["asset"],
                "type": "add_relation",
                "relation": {"source": "account:Dag.1234", "target": "asset:dag", "relation_type": "owns"},
            },
        ])

        assert result["status"] == "completed"
        assert [row["node_id"] for row in result["results"]] == ["account", "asset", "owns"]
        assert kernel.query().traverse("account:Dag.1234")["visited"] == ["account:Dag.1234", "asset:dag"]

    def test_execution_graph_rejects_cycles(self):
        from gw2_progression.ontology import ExecutionGraph, OntologyViolation

        graph = ExecutionGraph.from_actions([
            {
                "node_id": "a",
                "depends_on": ["b"],
                "type": "add_entity",
                "entity": {"id": "asset:a", "type": "account_asset", "properties": {"item_id": 1, "count": 1, "location": "bank"}},
            },
            {
                "node_id": "b",
                "depends_on": ["a"],
                "type": "add_entity",
                "entity": {"id": "asset:b", "type": "account_asset", "properties": {"item_id": 2, "count": 1, "location": "bank"}},
            },
        ])

        with pytest.raises(OntologyViolation):
            graph.topological_order()

    def test_oosk_simulation_runs_ticks_through_validated_actions(self):
        from gw2_progression.ontology import OntologyRuntimeKernel

        kernel = OntologyRuntimeKernel()
        kernel.execute({
            "type": "add_entity",
            "entity": {
                "id": "asset:sim",
                "type": "account_asset",
                "properties": {"item_id": 3, "count": 1, "location": "bank"},
            },
        })
        result = kernel.simulate(
            [{"type": "update_entity", "entity_id": "asset:sim", "patch": {"count": 5}}],
            ticks=2,
        )

        assert result["status"] == "completed"
        assert result["time"] == 2
        assert len(result["timeline"]) == 2
        assert kernel.snapshot()["state"]["entities"]["asset:sim"]["properties"]["count"] == 5
        assert len(kernel.snapshot()["lineage"]) == 3

    def test_lineage_store_dgsk_ingestor_gw2_api_and_reasoning_hook(self):
        from gw2_progression.ontology import GW2API, GW2APINormalizer, OntologyRuntimeKernel

        fetched = GW2API(fetcher=lambda url: {"url": url}).fetch("/account")
        assert fetched["url"].endswith("/account")

        kernel = OntologyRuntimeKernel()
        normalized = GW2APINormalizer().normalize({
            "account": {"name": "Hook.1234"},
            "assets": [{"item_id": 19721, "count": 1, "category": "bank"}],
        })
        ingested = kernel.ingest_normalized(normalized)
        valid = kernel.reasoning.execute({
            "type": "update_entity",
            "entity_id": "asset:Hook.1234:bank:19721:0",
            "patch": {"count": 2},
        })
        invalid = kernel.reasoning.execute({
            "type": "update_entity",
            "entity_id": "missing",
            "patch": {"count": 2},
        })

        assert ingested["dgsk"]["edge_count"] == 1
        assert valid["status"] == "accepted"
        assert invalid["status"] == "rejected"
        assert len(kernel.lineage_store.list()) == 4
        assert len(kernel.lineage_store.replayable_actions()) == 4


# ── Phase D3: Performance Tests ───────────────────────────────────────

class TestPerformance:
    def test_batch_register_objects(self):
        from gw2_progression.ontology.object_store import register_objects, get_objects_by_class

        specs = [
            {"class_name": "test_batch", "account_name": "Player.B", "properties": {"idx": i}}
            for i in range(10)
        ]
        objs = register_objects(specs)
        assert len(objs) == 10
        assert len(get_objects_by_class("test_batch")) == 10

    def test_batch_register_relations(self):
        from gw2_progression.ontology.object_store import register_objects, register_relations, get_relations

        objs = register_objects([
            {"class_name": "batch_a", "account_name": "P"},
            {"class_name": "batch_b", "account_name": "P"},
        ])
        rels = register_relations([
            {"source_id": objs[0].object_id, "target_id": objs[1].object_id, "relation_type": "batch_rel", "confidence": 0.9},
        ])
        assert len(rels) == 1
        assert len(get_relations(relation_type="batch_rel")) == 1

    def test_get_objects_by_property(self):
        from gw2_progression.ontology.object_store import register_object, get_objects_by_property

        register_object("prop_test", properties={"color": "red", "size": 1})
        register_object("prop_test", properties={"color": "blue", "size": 2})
        register_object("prop_test", properties={"color": "red", "size": 3})

        reds = get_objects_by_property("prop_test", "color", "red")
        assert len(reds) == 2
        blues = get_objects_by_property("prop_test", "color", "blue")
        assert len(blues) == 1

    def test_get_objects_by_property_batch(self):
        from gw2_progression.ontology.object_store import register_object, get_objects_by_property_batch

        register_object("batch_filter", properties={"type": "a", "active": True})
        register_object("batch_filter", properties={"type": "b", "active": True})
        register_object("batch_filter", properties={"type": "a", "active": False})

        result = get_objects_by_property_batch("batch_filter", {"type": "a", "active": True})
        assert len(result) == 1

    def test_count_objects(self):
        from gw2_progression.ontology.object_store import register_object, count_objects

        register_object("count_test", account_name="Player.C")
        register_object("count_test", account_name="Player.C")
        register_object("count_test", account_name="Player.D")
        assert count_objects("count_test") == 3
        assert count_objects("count_test", account_name="Player.C") == 2

    def test_count_relations(self):
        from gw2_progression.ontology.object_store import register_object, register_relation, count_relations

        a = register_object("count_rel_a")
        b = register_object("count_rel_b")
        register_relation(a.object_id, b.object_id, "type_x")
        register_relation(b.object_id, a.object_id, "type_y")
        assert count_relations() == 2
        assert count_relations(relation_type="type_x") == 1

    def test_pagination(self):
        from gw2_progression.ontology.object_store import register_object, get_objects_paginated

        for i in range(10):
            register_object("page_test", account_name="Player.P", properties={"i": i})
        page1 = get_objects_paginated("page_test", offset=0, limit=3)
        assert len(page1) <= 3
        page2 = get_objects_paginated("page_test", offset=3, limit=3)
        assert len(page2) <= 3

    def test_property_index_caching(self):
        from gw2_progression.ontology.object_store import register_object, get_objects_by_property, clear_prop_index

        clear_prop_index()
        register_object("cache_test", properties={"key": "val"})
        result1 = get_objects_by_property("cache_test", "key", "val")
        assert len(result1) == 1

        register_object("cache_test", properties={"key": "val"})
        result2 = get_objects_by_property("cache_test", "key", "val")
        assert len(result2) == 1  # cached, still shows 1

        clear_prop_index()
        result3 = get_objects_by_property("cache_test", "key", "val")
        assert len(result3) == 2  # re-queried, shows 2
