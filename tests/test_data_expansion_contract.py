from __future__ import annotations

import json
import uuid
from pathlib import Path


def _test_dir() -> Path:
    path = Path("data/test_runs") / f"data_expansion_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_data_expansion_record_contract_and_store():
    from gw2_progression.data_acquisition.contract import DataExpansionRecord
    from gw2_progression.data_acquisition.persistence import DataExpansionStore

    record = DataExpansionRecord.from_entity(
        {"id": "item:1", "type": "item", "properties": {"name": "Test"}, "source": "fixture"},
        source_id="fixture",
        source_type="api",
        collected_at=10.0,
        observed_at=9.0,
        confidence=0.9,
        privacy_scope="public",
    )
    assert record.raw_payload_hash
    assert record.lineage == ["fixture"]

    workdir = _test_dir()
    store = DataExpansionStore(workdir / "expansion.sqlite3")
    result = store.write_records([record, record])
    assert result["written"] == 1
    assert store.count() == 1
    loaded = store.list_records()[0]
    assert loaded.entity_id == "item:1"
    assert loaded.normalized_payload["properties"]["name"] == "Test"


def test_ingestion_persists_records_and_reports_coverage():
    from gw2_progression.data_acquisition.ingestion.orchestrator import IngestionOrchestrator
    from gw2_progression.data_acquisition.persistence import DataExpansionStore
    from gw2_progression.data_acquisition.registry.source_registry import SourcePriority, SourceRegistry, SourceType

    registry = SourceRegistry(sources=[])
    source = registry.register({
        "id": "fixture_items",
        "type": "api",
        "priority": SourcePriority.CRITICAL,
        "frequency": "realtime",
        "freshness_sla_seconds": 60,
        "confidence_default": 0.95,
    })

    class FixtureFetcher:
        def fetch(self, _source):
            return {
                "source_id": source.id,
                "type": SourceType.API.value,
                "timestamp": 100.0,
                "data": [{"id": 42, "name": "Mithril Ore", "type": "item", "count": 250}],
            }

    workdir = _test_dir()
    store = DataExpansionStore(workdir / "expansion.sqlite3")
    orch = IngestionOrchestrator(registry=registry, fetcher=FixtureFetcher(), store=store)
    result = orch.ingest_source(source)

    assert result.success
    assert result.records_written == 1
    assert result.coverage["total_records"] == 1
    assert result.coverage["entity_types"]["item"] == 1
    assert store.list_records()[0].privacy_scope == "public"


def test_coverage_analyzer_and_active_refresh_planner():
    from gw2_progression.data_acquisition.contract import DataExpansionRecord
    from gw2_progression.data_acquisition.coverage import ActiveRefreshPlanner, CoverageAnalyzer
    from gw2_progression.data_acquisition.registry.source_registry import SourceRegistry

    registry = SourceRegistry(sources=[
        {"id": "market", "type": "market", "priority": 1, "frequency": "hourly", "freshness_sla_seconds": 10},
        {"id": "wiki", "type": "wiki", "priority": 1, "frequency": "daily", "freshness_sla_seconds": 10},
    ])
    records = [
        DataExpansionRecord.from_entity(
            {"id": "market:mystic_coin", "type": "market_item", "source": "market"},
            source_id="market",
            source_type="market",
            collected_at=0.0,
            observed_at=0.0,
            confidence=0.7,
            privacy_scope="public",
        )
    ]
    report = CoverageAnalyzer(registry, required_entity_types={"market_item", "recipe"}).analyze(records, now=100.0)
    assert "wiki" in report.stale_sources
    assert "recipe" in report.missing_entity_types

    requests = ActiveRefreshPlanner(registry).plan(report)
    reasons = {r.reason for r in requests}
    assert "stale_source" in reasons
    assert "missing_entity_type" in reasons


def test_horizontal_expander_builds_merged_asset_views():
    from gw2_progression.data_acquisition.expansion.horizontal import HorizontalExpander
    from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType

    expander = HorizontalExpander()
    source = SourceConfig(id="items", type=SourceType.API, priority=SourcePriority.HIGH, frequency="daily")
    item_result = expander.expand({
        "source": "items",
        "entities": [{
            "id": "items:19721",
            "type": "item",
            "name": "Glob of Ectoplasm",
            "properties": {"native_id": 19721, "rarity": "Rare"},
            "confidence": 0.95,
        }],
        "relations": [],
    }, source)
    assert item_result["_horizontal_expanded"]

    market_source = SourceConfig(id="prices", type=SourceType.API, priority=SourcePriority.HIGH, frequency="hourly")
    merged = expander.expand({
        "source": "prices",
        "entities": [{
            "id": "prices:19721",
            "type": "market_item",
            "name": "19721",
            "properties": {"native_id": 19721, "buys": {"unit_price": 10}, "sells": {"unit_price": 12}},
            "confidence": 0.95,
        }],
        "relations": [],
    }, market_source)
    asset = next(entity for entity in merged["entities"] if entity["type"] == "merged_asset")
    assert asset["id"] == "asset:19721"
    assert asset["properties"]["market"]["sells"]["unit_price"] == 12
    assert any(relation["relation"] == "priced_by" for relation in merged["relations"])


def test_recipe_output_connects_to_merged_asset_and_ingredients():
    from gw2_progression.data_acquisition.expansion.horizontal import HorizontalExpander
    from gw2_progression.data_acquisition.expansion.vertical import VerticalExpander
    from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType

    source = SourceConfig(id="fixture", type=SourceType.API, priority=SourcePriority.HIGH, frequency="daily")
    recipe = {
        "id": "recipe:10",
        "type": "recipe",
        "name": "Crafted Output",
        "properties": {
            "native_id": 10,
            "output_item_id": 19721,
            "output_item_count": 2,
            "ingredients": [{"item_id": 123, "count": 4}],
        },
        "confidence": 0.95,
    }
    vertical = VerticalExpander().expand({"source": "recipes", "entities": [recipe], "relations": []}, source)
    assert any(entity["type"] == "ingredient_dependency" for entity in vertical["entities"])
    assert any(relation["relation"] == "produces_item" for relation in vertical["relations"])
    assert any(relation["relation"] == "requires_ingredient" for relation in vertical["relations"])

    horizontal = HorizontalExpander()
    horizontal.expand({
        "source": "items",
        "entities": [{
            "id": "items:19721",
            "type": "item",
            "name": "Glob of Ectoplasm",
            "properties": {"native_id": 19721},
            "confidence": 0.95,
        }],
        "relations": [],
    }, source)
    horizontal.expand({
        "source": "prices",
        "entities": [{
            "id": "prices:19721",
            "type": "market_item",
            "properties": {"native_id": 19721, "sells": {"unit_price": 12}, "buys": {"unit_price": 10}},
            "confidence": 0.95,
        }],
        "relations": [],
    }, source)
    horizontal.expand({
        "source": "prices",
        "entities": [{
            "id": "prices:123",
            "type": "market_item",
            "properties": {"native_id": 123, "sells": {"unit_price": 3}, "buys": {"unit_price": 2}},
            "confidence": 0.95,
        }],
        "relations": [],
    }, source)
    merged = horizontal.expand({"source": "recipes", "entities": [recipe], "relations": []}, source)
    asset = next(entity for entity in merged["entities"] if entity["id"] == "asset:19721")
    assert asset["properties"]["has_recipe"] is True
    assert asset["properties"]["craft_revenue_sell"] == 24
    assert asset["properties"]["tp_fee_adjusted_revenue"] == 20
    assert asset["properties"]["craft_cost"] == 12
    assert asset["properties"]["net_profit"] == 8
    assert asset["properties"]["profit_per_output"] == 4
    assert asset["properties"]["craft_cost_complete"] is True
    assert asset["properties"]["craft_input_item_count"] == 1
    opportunity = next(entity for entity in merged["entities"] if entity["type"] == "craft_profit_opportunity")
    assert opportunity["id"] == "profit:19721"
    assert opportunity["properties"]["asset_id"] == "asset:19721"
    assert opportunity["properties"]["roi"] == 0.6667
    assert opportunity["properties"]["profitable"] is True
    assert opportunity["properties"]["ingredient_item_ids"] == ["123"]
    assert any(relation["relation"] == "crafted_by" for relation in merged["relations"])
    assert any(relation["relation"] == "has_profit_opportunity" for relation in merged["relations"])
    assert any(relation["relation"] == "consumes_asset" and relation["target"] == "asset:123" for relation in merged["relations"])


def test_horizontal_expander_accepts_market_snapshots_for_craft_costs():
    from gw2_progression.data_acquisition.expansion.horizontal import HorizontalExpander
    from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType

    source = SourceConfig(id="fixture", type=SourceType.API, priority=SourcePriority.HIGH, frequency="daily")
    horizontal = HorizontalExpander()
    horizontal.expand({
        "source": "items",
        "entities": [{
            "id": "items:19721",
            "type": "item",
            "name": "Output",
            "properties": {"native_id": 19721},
            "confidence": 0.95,
        }],
        "relations": [],
    }, source)
    horizontal.expand({
        "source": "market_snapshots",
        "entities": [
            {
                "id": "snapshot:19721",
                "type": "market_price_snapshot",
                "properties": {"native_id": 19721, "sells": {"unit_price": 100}, "buys": {"unit_price": 80}},
                "confidence": 0.95,
            },
            {
                "id": "snapshot:24272",
                "type": "market_price_snapshot",
                "properties": {"native_id": 24272, "sells": {"unit_price": 20}, "buys": {"unit_price": 18}},
                "confidence": 0.95,
            },
        ],
        "relations": [],
    }, source)
    merged = horizontal.expand({
        "source": "recipes",
        "entities": [{
            "id": "recipe:1",
            "type": "recipe",
            "name": "Snapshot Recipe",
            "properties": {
                "native_id": 1,
                "output_item_id": 19721,
                "output_item_count": 1,
                "ingredients": [{"item_id": 24272, "count": 3}],
            },
            "confidence": 0.95,
        }],
        "relations": [],
    }, source)
    asset = next(entity for entity in merged["entities"] if entity["id"] == "asset:19721")
    assert asset["properties"]["craft_cost"] == 60
    assert asset["properties"]["tp_fee_adjusted_revenue"] == 85
    assert asset["properties"]["net_profit"] == 25
    opportunity = next(entity for entity in merged["entities"] if entity["type"] == "craft_profit_opportunity")
    assert opportunity["properties"]["net_profit"] == 25
    assert opportunity["properties"]["roi"] == 0.4167


def test_coverage_requires_craft_profit_opportunities():
    from gw2_progression.data_acquisition.contract import DataExpansionRecord
    from gw2_progression.data_acquisition.coverage import ActiveRefreshPlanner, CoverageAnalyzer
    from gw2_progression.data_acquisition.registry.source_registry import SourceRegistry

    registry = SourceRegistry(sources=[
        {"id": "gw2_api_recipes", "type": "api", "priority": 0, "frequency": "daily"},
        {"id": "gw2_market_price_snapshots", "type": "api", "priority": 1, "frequency": "hourly"},
    ])
    records = [
        DataExpansionRecord.from_entity(
            {"id": "asset:1", "type": "merged_asset", "source": "fixture"},
            source_id="fixture",
            source_type="api",
            collected_at=1.0,
            observed_at=1.0,
            confidence=0.9,
            privacy_scope="public",
        )
    ]
    report = CoverageAnalyzer(
        registry,
        required_entity_types={"merged_asset", "craft_profit_opportunity"},
    ).analyze(records, now=1.0)
    assert "craft_profit_opportunity" in report.missing_entity_types
    requests = ActiveRefreshPlanner(registry).plan(report)
    assert any(request.entity_type == "craft_profit_opportunity" for request in requests)


def test_dataset_builder_writes_manifest_with_lineage():
    from gw2_progression.data_acquisition.contract import DataExpansionRecord
    from gw2_progression.data_acquisition.flywheel.dataset_builder import DatasetBuilder

    record = DataExpansionRecord.from_entity(
        {"id": "recipe:1", "type": "recipe", "properties": {"disciplines": ["armorsmith"]}, "source": "wiki"},
        source_id="wiki",
        source_type="wiki",
        collected_at=10.0,
        observed_at=10.0,
        confidence=0.86,
        privacy_scope="public",
    )
    workdir = _test_dir()
    builder = DatasetBuilder(output_dir=str(workdir))
    dataset = builder.build_expansion_dataset([record], iteration=1)
    manifest = builder.build_manifest(dataset)
    assert manifest.sample_count == 1
    assert manifest.source_mix["wiki"] == 1
    assert manifest.confidence_distribution["high"] == 1
    assert manifest.lineage_hashes == [record.raw_payload_hash]

    assert builder.save_all() == 1
    manifest_path = workdir / "expansion_training_1.manifest.json"
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved["label_coverage"]["validation_status"] == 1


def test_data_factory_generates_expansion_dataset_from_store():
    from gw2_progression.data_acquisition.factory import DataFactory
    from gw2_progression.data_acquisition.persistence import DataExpansionStore
    from gw2_progression.data_acquisition.registry.source_registry import SourceRegistry

    workdir = _test_dir()
    registry = SourceRegistry(sources=[
        {"id": "wallet", "type": "api", "priority": 0, "frequency": "realtime", "endpoint": "/v2/account/wallet"}
    ])
    factory = DataFactory(source_registry=registry, data_store=DataExpansionStore(workdir / "expansion.sqlite3"))
    factory.dataset_builder.output_dir = workdir / "datasets"
    factory.dataset_builder.output_dir.mkdir(parents=True, exist_ok=True)

    results = factory.collect_all()
    assert results[0].records_written > 0
    iteration = factory.run_flywheel(iterations=1)[0]
    assert iteration.dataset_samples > 0
    assert factory.status_report()["data_expansion"]["stored_records"] > 0


def test_fetcher_real_http_adapter_uses_gw2_api_shape():
    from gw2_progression.data_acquisition.ingestion.fetcher import Fetcher
    from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType

    class Response:
        def __init__(self):
            self.payload = [{"id": 1, "name": "Gold"}]

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class Client:
        def __init__(self):
            self.calls = []

        def get(self, url, headers=None):
            self.calls.append((url, headers or {}))
            return Response()

    client = Client()
    source = SourceConfig(
        id="wallet",
        type=SourceType.API,
        priority=SourcePriority.CRITICAL,
        frequency="realtime",
        endpoint="/v2/account/wallet",
        auth_required=True,
    )
    result = Fetcher(mode="real", api_key="secret", http_client=client).fetch(source)
    assert result["data"][0]["name"] == "Gold"
    assert client.calls[0][0].endswith("/v2/account/wallet")
    assert client.calls[0][1]["Authorization"] == "Bearer secret"


def test_fetcher_real_ids_all_fallback_chunks_ids():
    from gw2_progression.data_acquisition.ingestion.fetcher import Fetcher
    from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType

    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self.payload = payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"status {self.status_code}")

        def json(self):
            return self.payload

    class Client:
        def __init__(self):
            self.urls = []

        def get(self, url, headers=None):
            self.urls.append(url)
            if url.endswith("?ids=all"):
                return Response(400, {})
            if url.endswith("/v2/items"):
                return Response(200, [1, 2, 3])
            if "ids=1,2" in url:
                return Response(200, [{"id": 1}, {"id": 2}])
            if "ids=3" in url:
                return Response(200, [{"id": 3}])
            return Response(404, {})

    source = SourceConfig(
        id="items",
        type=SourceType.API,
        priority=SourcePriority.CRITICAL,
        frequency="daily",
        endpoint="/v2/items?ids=all",
        metadata={"chunk_size": 2},
    )
    result = Fetcher(mode="real", http_client=Client()).fetch(source)
    assert [row["id"] for row in result["data"]] == [1, 2, 3]
    assert result["metadata"]["fallback"] == "ids_chunked"


def test_fetcher_mediawiki_adapter_and_normalizer_build_wiki_pages():
    from gw2_progression.data_acquisition.ingestion.fetcher import Fetcher
    from gw2_progression.data_acquisition.ingestion.normalizer import Normalizer
    from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "query": {
                    "pages": {
                        "123": {
                            "pageid": 123,
                            "ns": 0,
                            "title": "Crafting",
                            "revisions": [{
                                "revid": 456,
                                "timestamp": "2026-06-29T00:00:00Z",
                                "slots": {"main": {"*": "Crafting page content"}},
                            }],
                        }
                    }
                }
            }

    class Client:
        def __init__(self):
            self.calls = []

        def get(self, url, headers=None, params=None):
            self.calls.append((url, headers or {}, params or {}))
            return Response()

    client = Client()
    source = SourceConfig(
        id="wiki",
        type=SourceType.WIKI,
        priority=SourcePriority.HIGH,
        frequency="daily",
        endpoint="https://wiki.guildwars2.com/api.php",
        metadata={"adapter": "mediawiki", "titles": ["Crafting"], "entity_type": "wiki_page"},
    )
    raw = Fetcher(mode="real", http_client=client).fetch(source)
    normalized = Normalizer().normalize(raw, source)
    page = normalized["entities"][0]
    assert raw["metadata"]["adapter"] == "mediawiki"
    assert client.calls[0][2]["titles"] == "Crafting"
    assert page["type"] == "wiki_page"
    assert page["properties"]["revision_id"] == 456
    assert page["properties"]["content_excerpt"] == "Crafting page content"


def test_market_timeseries_adapter_builds_snapshot_entities():
    from gw2_progression.data_acquisition.ingestion.fetcher import Fetcher
    from gw2_progression.data_acquisition.ingestion.normalizer import Normalizer
    from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [{"id": 19721, "buys": {"unit_price": 10}, "sells": {"unit_price": 12}}]

    class Client:
        def get(self, url, headers=None, params=None):
            return Response()

    source = SourceConfig(
        id="market_snapshots",
        type=SourceType.API,
        priority=SourcePriority.HIGH,
        frequency="hourly",
        endpoint="/v2/commerce/prices?ids=19721",
        metadata={"adapter": "market_timeseries", "entity_type": "market_price_snapshot"},
    )
    raw = Fetcher(mode="real", http_client=Client()).fetch(source)
    normalized = Normalizer().normalize(raw, source)
    snapshot = normalized["entities"][0]
    assert raw["metadata"]["adapter"] == "market_timeseries"
    assert snapshot["type"] == "market_price_snapshot"
    assert snapshot["id"].startswith("market_snapshots:19721:")
    assert snapshot["properties"]["snapshot_source_id"] == "market_snapshots"


def test_source_registry_exposes_adapter_metadata():
    from gw2_progression.data_acquisition.registry.source_registry import SourceRegistry

    registry = SourceRegistry()
    sources = {source["id"]: source for source in registry.to_dict()["sources"]}
    assert sources["gw2_wiki_crafting"]["metadata"]["adapter"] == "mediawiki"
    assert sources["gw2_api_recipes"]["metadata"]["entity_type"] == "recipe"
    assert sources["gw2_market_price_snapshots"]["metadata"]["adapter"] == "market_timeseries"


def test_fetcher_replays_raw_account_snapshot_and_normalizer_keeps_sections():
    from gw2_progression.data_acquisition.ingestion.fetcher import Fetcher
    from gw2_progression.data_acquisition.ingestion.normalizer import Normalizer
    from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType

    workdir = _test_dir()
    replay_path = workdir / "raw.json"
    replay_path.write_text(json.dumps({
        "collected_at": 123.0,
        "account": {"name": "Netro.7195"},
        "wallet": [{"id": 1, "value": 100}],
        "bank": [{"id": 2, "count": 3}],
        "materials": [{"id": 3, "count": 4}],
        "characters": [{"name": "Netro Ignis"}],
    }), encoding="utf-8")
    source = SourceConfig(
        id="raw_account",
        type=SourceType.API,
        priority=SourcePriority.CRITICAL,
        frequency="daily",
        metadata={"replay_path": str(replay_path)},
        privacy_scope="account",
    )
    raw = Fetcher(mode="replay").fetch(source)
    normalized = Normalizer().normalize(raw, source)
    entity_types = {entity["type"] for entity in normalized["entities"]}
    assert "account_snapshot" in entity_types
    assert "account_wallet" in entity_types
    assert "account_materials" in entity_types


def test_data_expansion_mirror_writes_postgres_neo4j_and_qdrant():
    from gw2_progression.data_acquisition.contract import DataExpansionRecord
    from gw2_progression.data_acquisition.persistence import DataExpansionMirror

    record = DataExpansionRecord.from_entity(
        {"id": "item:mirror", "type": "item", "properties": {"name": "Mirror"}},
        source_id="fixture",
        source_type="api",
        collected_at=1.0,
        observed_at=1.0,
        confidence=0.91,
        privacy_scope="public",
    )

    class FakePg:
        def __init__(self):
            self.executed = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, params=None):
            self.executed.append((sql, params))

        def commit(self):
            self.committed = True

    fake_pg = FakePg()

    class FakeSession:
        def __init__(self):
            self.runs = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def run(self, query, **params):
            self.runs.append((query, params))

    class FakeDriver:
        def __init__(self):
            self.session_obj = FakeSession()
            self.closed = False

        def session(self):
            return self.session_obj

        def close(self):
            self.closed = True

    fake_driver = FakeDriver()

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeHttp:
        def __init__(self):
            self.puts = []

        def put(self, url, json=None):
            self.puts.append((url, json))
            return FakeResponse()

    fake_http = FakeHttp()
    mirror = DataExpansionMirror(
        postgres_url="postgresql://example/db",
        neo4j_url="bolt://neo4j:7687",
        qdrant_url="http://qdrant:6333",
        postgres_connection_factory=lambda _url: fake_pg,
        neo4j_driver_factory=lambda *_args, **_kwargs: fake_driver,
        http_client=fake_http,
    )
    result = mirror.write_records([record])
    assert result["postgres"]["written"]
    assert result["neo4j"]["written"]
    assert result["qdrant"]["written"]
    assert fake_pg.executed
    assert fake_driver.session_obj.runs
    assert any("/points" in url for url, _body in fake_http.puts)


def test_active_refresh_queue_runs_registered_handler():
    from gw2_progression.data_acquisition.registry.source_registry import SourceRegistry
    from gw2_progression.data_acquisition.scheduler.task_scheduler import TaskScheduler

    registry = SourceRegistry(sources=[
        {"id": "market", "type": "market", "priority": 1, "frequency": "hourly"}
    ])
    scheduler = TaskScheduler(registry=registry)
    called = []

    def handler(source):
        called.append(source.id)

    scheduler.register_handler("market", handler)
    added = scheduler.enqueue_refresh_requests([{"source_id": "market", "reason": "stale_source", "priority": 1}], current_time=1.0)
    results = scheduler.run_refresh_queue()
    assert added == 1
    assert called == ["market"]
    assert results[0]["status"] == "completed"
