"""Tests for the Ontology layer — object store, relations, impact analysis, QA gate."""

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
            "snapshot_time": "2026-06-26T12:00:00",
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
            "api_key": "ABCDEF1234567890",
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
            "snapshot_time": "2026-06-26T12:00:00",
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
                "snapshot_time": "2026-06-26T12:00:00",
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
            {"report_id": 1, "access_level": "private", "snapshot_time": "2026-06-26T12:00:00"},
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
            "snapshot_time": "2026-06-26T12:00:00",
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
            "snapshot_time": "2026-06-26T12:00:00",
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

        map_signal_to_ontology(TradingPostSignal(item_id=19976, signal_type="sell_candidate", price_timestamp="2026-06-26T12:00:00"), "Player.1")
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
