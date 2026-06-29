from __future__ import annotations

from gw2_progression.data_mesh.ingestion import DataIngestion
from gw2_progression.data_mesh.integration import DataMeshBridge
from gw2_progression.data_mesh.pipeline import DataMeshPipeline
from gw2_progression.data_mesh.schema.confidence import ConfidenceRecord, ConfidenceSystem
from gw2_progression.data_mesh.schema.normalizer import SchemaNormalizer
from gw2_progression.data_mesh.sources.registry import (
    BUILTIN_SOURCES,
    AllowedUse,
    CrawlPolicy,
    KBDomain,
    KnowledgeArticle,
    KnowledgeSource,
    SourceRegistry,
    SourceType,
)

# ── KnowledgeSource / SourceRegistry ─────────────────────────────────────

def test_knowledge_source_creation():
    ks = KnowledgeSource(
        source_id="source:test:foo",
        name="Test Source",
        source_type=SourceType.OFFICIAL_WIKI,
        source_url="https://example.com",
        allowed_use=AllowedUse.SUMMARY_AND_REFERENCE,
        crawl_policy=CrawlPolicy.MANUAL_OR_LOW_FREQUENCY,
        default_confidence=0.9,
        license_note="test license",
        recommended_kb_domain=KBDomain.OFFICIAL,
    )
    d = ks.to_dict()
    assert d["source_id"] == "source:test:foo"
    assert d["source_type"] == "official_wiki"
    assert d["default_confidence"] == 0.9


def test_builtin_sources_loaded():
    assert len(BUILTIN_SOURCES) >= 15
    source_ids = [s.source_id for s in BUILTIN_SOURCES]
    assert "source:official:guildwars2_home" in source_ids
    assert "source:gw2wiki:api_v2" in source_ids
    assert "source:gw2api:account" in source_ids
    assert "source:snowcrows:home" in source_ids
    assert "source:community:reddit_guildwars2" in source_ids


def test_builtin_source_types():
    types = {s.source_type for s in BUILTIN_SOURCES}
    assert SourceType.OFFICIAL_API in types
    assert SourceType.OFFICIAL_WIKI in types
    assert SourceType.COMMUNITY in types
    assert SourceType.PUBLIC_BUILD_SITE in types


def test_source_registry_register_and_get():
    reg = SourceRegistry()
    ks = KnowledgeSource(
        source_id="source:test:reg",
        name="Reg Test",
        source_type=SourceType.COMPETITOR_TOOL,
        source_url="https://test.com",
        allowed_use=AllowedUse.METADATA_ONLY,
        crawl_policy=CrawlPolicy.MANUAL_ONLY,
        default_confidence=0.7,
        license_note="test",
        recommended_kb_domain=KBDomain.MARKET,
    )
    reg.register(ks)
    assert reg.get("source:test:reg") is ks
    assert reg.get("nonexistent") is None


def test_source_registry_filter():
    reg = SourceRegistry()
    for s in BUILTIN_SOURCES:
        reg.register(s)
    api_sources = reg.list_sources(source_type=SourceType.OFFICIAL_API)
    assert len(api_sources) >= 5
    for s in api_sources:
        assert s.source_type == SourceType.OFFICIAL_API
    community_sources = reg.list_sources(source_type=SourceType.COMMUNITY)
    assert len(community_sources) >= 1


def test_knowledge_article():
    article = KnowledgeArticle(
        kb_id="kb:test:article_1",
        title="Test Article",
        domain="official",
        content_type="source_note",
        summary="A test article",
        linked_entities=["entity:test:gw2_v2"],
        linked_actions=["INGEST_SOURCE"],
        linked_sources=["source:test:foo"],
        confidence=0.95,
        review_status="reviewed",
    )
    d = article.to_dict()
    assert d["kb_id"] == "kb:test:article_1"
    assert d["confidence"] == 0.95
    assert len(d["linked_sources"]) == 1


def test_source_registry_article_crud():
    reg = SourceRegistry()
    a = KnowledgeArticle(kb_id="kb:crud:1", title="CRUD", domain="test", content_type="note", summary="x")
    reg.add_article(a)
    assert reg.get_article("kb:crud:1") is a
    assert reg.get_article("nonexistent") is None
    assert len(reg.list_articles()) == 1
    assert len(reg.list_articles(domain="other")) == 0


def test_source_registry_serialize():
    reg = SourceRegistry()
    ks = KnowledgeSource(
        source_id="source:serialize:1", name="S", source_type=SourceType.OFFICIAL_API,
        source_url="https://s.com", allowed_use=AllowedUse.API_JSON,
        crawl_policy=CrawlPolicy.GATEWAY_MANAGED, default_confidence=1.0,
        license_note="n", recommended_kb_domain=KBDomain.GAME_SYSTEM,
    )
    reg.register(ks)
    d = reg.to_dict()
    assert "sources" in d
    assert "source:serialize:1" in d["sources"]
    assert d["sources"]["source:serialize:1"]["source_type"] == "official_api"


def test_source_registry_count():
    reg = SourceRegistry()
    for s in BUILTIN_SOURCES[:5]:
        reg.register(s)
    c = reg.count()
    assert c["sources"] == 5


# ── SchemaNormalizer ────────────────────────────────────────────────────

def test_normalize_empty():
    ds = SchemaNormalizer.normalize({})
    assert ds.account == "unknown"
    assert ds.wallet == []
    assert ds.items == []
    assert ds.characters == []
    assert ds.relations == []


def test_normalize_account():
    ds = SchemaNormalizer.normalize({"account": "TestUser.1234"})
    assert ds.account == "TestUser.1234"


def test_normalize_account_name_fallback():
    ds = SchemaNormalizer.normalize({"account_name": "Fallback.5678"})
    assert ds.account == "Fallback.5678"


def test_normalize_wallet():
    ds = SchemaNormalizer.normalize({"wallet": [{"id": 1, "value": 100}, {"id": 2, "value": 200}]})
    assert len(ds.wallet) == 2
    assert ds.wallet[0]["id"] == 1
    assert ds.wallet[0]["value"] == 100


def test_normalize_currencies_alias():
    ds = SchemaNormalizer.normalize({"currencies": [{"id": 1, "value": 50}]})
    assert len(ds.wallet) == 1


def test_normalize_items():
    ds = SchemaNormalizer.normalize({"items": [{"id": 12345, "count": 5, "name": "Test Item"}]})
    assert len(ds.items) == 1
    assert ds.items[0]["id"] == 12345
    assert ds.items[0]["count"] == 5


def test_normalize_relations():
    ds = SchemaNormalizer.normalize({"relations": [
        {"source": "a", "relation_type": "requires", "target": "b", "confidence": 0.9},
    ]})
    assert len(ds.relations) == 1
    assert ds.relations[0]["source"] == "a"
    assert ds.relations[0]["relation_type"] == "requires"
    assert ds.relations[0]["target"] == "b"


def test_normalize_inventory_alias():
    ds = SchemaNormalizer.normalize({"inventory": [{"id": 999, "count": 2}]})
    assert len(ds.items) == 1


def test_normalize_assets_alias():
    ds = SchemaNormalizer.normalize({"assets": [{"id": 111, "count": 1}]})
    assert len(ds.items) == 1


def test_normalize_source_type_metadata():
    ds = SchemaNormalizer.normalize({"account": "U"}, source_type="gw2_api")
    assert ds.metadata["source"] == "gw2_api"


def test_normalize_achievements():
    ds = SchemaNormalizer.normalize({"achievements": [{"id": 1, "current": 100, "max": 200}]})
    assert len(ds.achievements) == 1


def test_normalize_recipes():
    ds = SchemaNormalizer.normalize({"recipes": [{"id": 1, "output_item_id": 123}]})
    assert len(ds.recipes) == 1


def test_normalize_non_dict_items():
    ds = SchemaNormalizer.normalize({"items": ["abc", "def"]})
    assert len(ds.items) == 2


def test_normalize_merge():
    s1 = SchemaNormalizer.normalize({"wallet": [{"id": 1, "value": 100}]}, "src_a")
    s2 = SchemaNormalizer.normalize({"wallet": [{"id": 2, "value": 200}]}, "src_b")
    merged = SchemaNormalizer.merge([s1, s2])
    assert len(merged.wallet) == 2
    assert merged.metadata["merged_from"] == 2
    assert "src_a" in merged.metadata["sources"]
    assert "src_b" in merged.metadata["sources"]


def test_normalize_merge_dedup():
    s1 = SchemaNormalizer.normalize({"wallet": [{"id": 1, "value": 100}, {"id": 1, "value": 200}]}, "a")
    s2 = SchemaNormalizer.normalize({"wallet": [{"id": 1, "value": 300}]}, "b")
    merged = SchemaNormalizer.merge([s1, s2])
    assert len(merged.wallet) == 1


def test_normalize_relation_predicate_aliases():
    ds = SchemaNormalizer.normalize({"relations": [
        {"from": "a", "label": "contains", "to": "b"},
    ]})
    assert ds.relations[0]["source"] == "a"
    assert ds.relations[0]["relation_type"] == "contains"
    assert ds.relations[0]["target"] == "b"


# ── ConfidenceSystem ────────────────────────────────────────────────────

def test_confidence_base_types():
    cs = ConfidenceSystem()
    assert cs.SOURCE_TYPE_BASE["official_api"] == 1.0
    assert cs.SOURCE_TYPE_BASE["community"] == 0.4
    assert cs.SOURCE_TYPE_BASE["public_build_site"] == 0.8


def test_confidence_official_api():
    cs = ConfidenceSystem()
    r = cs.evaluate(source_type="official_api", records_count=5)
    assert r.base_confidence == 1.0
    assert r.adjusted_confidence == 1.0


def test_confidence_community():
    cs = ConfidenceSystem()
    r = cs.evaluate(source_type="community", records_count=1)
    assert r.base_confidence == 0.4
    assert r.adjusted_confidence < 0.4


def test_confidence_single_record_penalty():
    cs = ConfidenceSystem()
    r = cs.evaluate(source_type="official_wiki", records_count=1)
    assert r.adjusted_confidence < r.base_confidence


def test_confidence_zero_records():
    cs = ConfidenceSystem()
    r = cs.evaluate(source_type="official_api", records_count=0)
    assert r.adjusted_confidence < 0.6


def test_confidence_staleness():
    cs = ConfidenceSystem()
    r = cs.evaluate(source_type="official_wiki", records_count=5, staleness_days=100)
    assert r.adjusted_confidence < r.base_confidence
    assert "staleness" in r.adjustments[0]


def test_confidence_cross_validation():
    cs = ConfidenceSystem()
    r = cs.evaluate(source_type="official_wiki", records_count=5, cross_validation_count=3)
    assert r.adjusted_confidence > r.base_confidence
    assert r.cross_validated is True


def test_confidence_bounded():
    cs = ConfidenceSystem()
    r = cs.evaluate(source_type="official_api", records_count=5, cross_validation_count=10)
    assert r.adjusted_confidence <= 1.0


def test_confidence_adjust_for_merge():
    cs = ConfidenceSystem()
    r1 = ConfidenceRecord("a", "official_api", 1.0, 1.0, records_count=10)
    r2 = ConfidenceRecord("b", "community", 0.4, 0.3, records_count=2)
    merged = cs.adjust_for_merge([r1, r2])
    assert merged > 0.3
    assert merged <= 1.0


# ── DataIngestion ───────────────────────────────────────────────────────

def test_ingestion_unsupported():
    ing = DataIngestion()
    r = ing.ingest("unknown_source")
    assert r.status == "unsupported"
    assert r.error is not None


def test_ingestion_static():
    ing = DataIngestion()
    r = ing.ingest("static", items=[{"id": 1, "name": "test"}], wallet=[{"id": 1, "value": 100}])
    assert r.status == "ok"
    assert r.record_count == 2
    assert len(r.raw_data.get("items", [])) == 1


def test_ingestion_local_json():
    ing = DataIngestion()
    r = ing.ingest("local_json", data={"items": [{"id": 1}], "wallet": [{"id": 2}]})
    assert r.status == "ok"
    assert r.record_count >= 2


def test_ingestion_local_json_list():
    ing = DataIngestion()
    r = ing.ingest("local_json", data=[{"id": 1}, {"id": 2}])
    assert r.status == "ok"


def test_ingestion_cache():
    ing = DataIngestion()
    params = {"items": [{"id": 1}], "wallet": []}
    r1 = ing.ingest("static", **params)
    r2 = ing.ingest("static", **params)
    assert r1.status == "ok"
    assert r2.status == "cached"


def test_ingestion_cache_clear():
    ing = DataIngestion()
    ing.ingest("static", items=[{"id": 1}])
    cleared = ing.clear_cache()
    assert cleared == 1
    assert len(ing._cache) == 0


def test_ingestion_multi():
    ing = DataIngestion()
    results = ing.ingest_multi([
        {"type": "static", "params": {"items": [{"id": 1}]}},
        {"type": "static", "params": {"items": [{"id": 2}]}},
        {"type": "unknown_source", "params": {}},
    ])
    assert len(results) == 3
    assert results[0].status == "ok"
    assert results[1].status in ("ok", "cached")
    assert results[2].status == "unsupported"


# ── DataMeshPipeline ────────────────────────────────────────────────────

def test_pipeline_empty():
    pipe = DataMeshPipeline()
    result = pipe.run([])
    assert result.status == "ok"
    assert result.sources_ingested == 0
    assert result.normalized is not None


def test_pipeline_static_sources():
    pipe = DataMeshPipeline()
    result = pipe.run([
        {"type": "static", "params": {"items": [{"id": 1, "name": "Item A"}], "wallet": [{"id": 1, "value": 100}]}},
        {"type": "static", "params": {"items": [{"id": 2, "name": "Item B"}], "relations": [{"source": "a", "relation_type": "connects", "target": "b"}]}},
    ])
    assert result.status in ("ok", "partial")
    assert result.sources_ingested >= 1
    assert result.normalized is not None
    assert result.confidence is not None
    assert len(result.source_results) == 2


def test_pipeline_stages():
    pipe = DataMeshPipeline()
    result = pipe.run([
        {"type": "static", "params": {"items": [{"id": 1}]}},
    ])
    stage_names = [s.name for s in result.stages]
    assert "resolve_sources" in stage_names
    assert "ingest" in stage_names
    assert "normalize" in stage_names
    assert "confidence" in stage_names
    assert "persist" in stage_names


def test_pipeline_to_dict():
    pipe = DataMeshPipeline()
    result = pipe.run([
        {"type": "static", "params": {"items": [{"id": 99}]}},
    ])
    d = result.to_dict()
    assert "id" in d
    assert "status" in d
    assert "stages" in d
    assert "source_results" in d
    assert "normalized" in d
    assert "confidence" in d


def test_pipeline_error_handling():
    pipe = DataMeshPipeline()
    result = pipe.run([
        {"type": "local_file", "params": {"path": "/nonexistent/file.json"}},
    ])
    assert result.status in ("error", "partial")
    assert any(r.status == "error" for r in result.source_results)


# ── DataMeshBridge (integration) ────────────────────────────────────────

def test_bridge_multi_source_ingest_static():
    bridge = DataMeshBridge()
    results = bridge.multi_source_ingest([
        {"type": "static", "params": {"items": [{"id": 7, "name": "bridge test"}], "wallet": []}},
    ])
    assert len(results) == 1
    assert results[0]["status"] in ("ok",)
    assert "normalized" in results[0]


def test_bridge_run_pipeline():
    bridge = DataMeshBridge()
    result = bridge.run_pipeline([
        {"type": "static", "params": {"wallet": [{"id": 1, "value": 999}]}},
    ])
    assert result["status"] in ("ok", "partial")
    assert "normalized" in result
    assert "confidence" in result


def test_bridge_normalize_legacy():
    result = DataMeshBridge.normalize({"account": "Legacy.1234", "wallet": {"gold": 100}})
    assert result["account"] == "Legacy.1234"
    assert len(result["wallet"]) > 0


def test_bridge_normalize_fallback():
    result = DataMeshBridge.normalize({})
    assert result["account"] == "unknown"
    assert result["items"] == []


def test_bridge_health():
    from gw2_progression.data_mesh.integration import check_mesh_health
    health = check_mesh_health()
    assert health["mesh_version"] == "v1"
