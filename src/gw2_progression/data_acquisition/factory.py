"""GW2 Data Factory — top-level orchestrator for the autonomous data pipeline.

Architecture:
  Collector Layer  →  DGSK Graph Builder  →  OOSK Simulation  →  Behavior Inference  →  Data Flywheel

This is the entry point for the GW2 Single Machine Data Factory.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from gw2_progression.data_acquisition.dgsk.graph_builder import DGSKGraphBuilder, GraphBuildResult
from gw2_progression.data_acquisition.flywheel.data_loop import DataFlywheel, FlywheelIteration
from gw2_progression.data_acquisition.flywheel.dataset_builder import DatasetBuilder
from gw2_progression.data_acquisition.ingestion.orchestrator import IngestionOrchestrator, IngestionResult
from gw2_progression.data_acquisition.persistence import DataExpansionStore
from gw2_progression.data_acquisition.registry.source_registry import SourceRegistry
from gw2_progression.data_acquisition.scheduler.task_scheduler import TaskScheduler
from gw2_progression.data_acquisition.streaming.stream_engine import StreamEngine


@dataclass
class FactoryStatus:
    running: bool = False
    uptime_seconds: float = 0.0
    total_ingestions: int = 0
    total_flywheel_iterations: int = 0
    total_datasets_generated: int = 0
    start_time: float = 0.0


class DataFactory:
    """GW2 Data Factory v1 — autonomous world model factory on single machine.

    Ties together:
      - Source Registry (config-driven data sources)
      - Ingestion Orchestrator (fetch + normalize + expand + graph)
      - DGSK Graph Builder (automatic world model)
      - Stream Engine (real-time updates)
      - Task Scheduler (periodic ingestion)
      - Data Flywheel (self-improving loop)
      - Dataset Builder (training data generation)

    This is the top-level entry point for the autonomous pipeline.
    """

    def __init__(
        self,
        source_registry: SourceRegistry | None = None,
        ingestion_orchestrator: IngestionOrchestrator | None = None,
        graph_builder: DGSKGraphBuilder | None = None,
        stream_engine: StreamEngine | None = None,
        task_scheduler: TaskScheduler | None = None,
        flywheel: DataFlywheel | None = None,
        dataset_builder: DatasetBuilder | None = None,
        data_store: DataExpansionStore | None = None,
    ) -> None:
        self.source_registry = source_registry or SourceRegistry()
        self.ingestion = ingestion_orchestrator or IngestionOrchestrator(registry=self.source_registry, store=data_store or DataExpansionStore())
        self.data_store = data_store or self.ingestion.store
        self.graph_builder = graph_builder or DGSKGraphBuilder()
        self.stream_engine = stream_engine or StreamEngine()
        self.task_scheduler = task_scheduler or TaskScheduler(registry=self.source_registry)
        self.dataset_builder = dataset_builder or DatasetBuilder()
        self.flywheel = flywheel or DataFlywheel()

        self.status = FactoryStatus()

        # External hook references (set by engine)
        self._simulate_fn: Callable[[], Any] | None = None
        self._infer_fn: Callable[[], Any] | None = None
        self._graph_to_dgsk_fn: Callable[[], dict[str, Any]] | None = None

        self.ingestion.register_graph_hook(self.graph_builder.build)
        self._wire_scheduler_handlers()
        self._wire_flywheel()

    def _wire_scheduler_handlers(self) -> None:
        for source in self.source_registry.get_enabled():
            self.task_scheduler.register_handler(source.id, self.ingestion.ingest_source)

    def _wire_flywheel(self) -> None:
        """Wire the flywheel hooks to factory components."""
        def ingest_all():
            return self.ingestion.ingest_all()

        def graph_build():
            self.ingestion.ingest_all()
            gdata = self.graph_builder.to_dict()
            if self._graph_to_dgsk_fn:
                self._graph_to_dgsk_fn()
            return gdata

        def simulate():
            if self._simulate_fn:
                return self._simulate_fn()
            return {}

        def infer():
            if self._infer_fn:
                result = self._infer_fn()
                return result
            return {}

        def dataset(iteration):
            records = self.data_store.list_records()
            if records:
                self.dataset_builder.build_expansion_dataset(records, iteration)
            return self.dataset_builder.total_samples()

        def checkpoint(iteration):
            self.dataset_builder.save_all()

        self.flywheel.set_hooks(
            ingest_all=ingest_all,
            graph_build=graph_build,
            simulate=simulate,
            infer=infer,
            dataset=dataset,
            checkpoint=checkpoint,
        )

    # ─── Collector Layer ────────────────────────────────────────────

    def collect_all(self) -> list[IngestionResult]:
        """Collect data from all enabled sources."""
        results = self.ingestion.ingest_all()
        self._enqueue_refresh_requests(results)
        self.status.total_ingestions += len(results)
        return results

    def collect_source(self, source_id: str) -> IngestionResult | None:
        """Collect data from a specific source."""
        source = self.source_registry.get(source_id)
        if not source:
            return None
        result = self.ingestion.ingest_source(source)
        if result:
            self._enqueue_refresh_requests([result])
            self.status.total_ingestions += 1
        return result

    # ─── DGSK Graph Layer ───────────────────────────────────────────

    def build_graph(self) -> GraphBuildResult:
        """Build the DGSK graph from currently ingested data."""
        return self.graph_builder.build({"entities": [], "relations": []})

    # ─── Stream Layer ───────────────────────────────────────────────

    def push_event(self, source_id: str, data_type: str, data: dict[str, Any]) -> None:
        self.stream_engine.push_data(source_id, data_type, data)

    def flush_stream(self) -> int:
        events = self.stream_engine.flush()
        return len(events)

    # ─── Scheduler Layer ────────────────────────────────────────────

    def run_scheduler(self) -> list[dict[str, Any]]:
        scheduled = self.task_scheduler.run_pending(time.time())
        refresh = self.task_scheduler.run_refresh_queue()
        return scheduled + refresh

    # ─── Flywheel Layer ─────────────────────────────────────────────

    def run_flywheel(self, iterations: int = 1) -> list[FlywheelIteration]:
        """Run the data flywheel for N iterations."""
        results = self.flywheel.run(iterations=iterations)
        self.status.total_flywheel_iterations += len(results)
        self.status.total_datasets_generated = self.dataset_builder.total_samples()
        return results

    def stop_flywheel(self) -> None:
        self.flywheel.stop()

    # ─── Lifecycle ──────────────────────────────────────────────────

    def start(self) -> None:
        """Start the data factory."""
        self.status.start_time = time.time()
        self.status.running = True

    def stop(self) -> None:
        """Stop the data factory."""
        self.stop_flywheel()
        self.status.running = False
        self.status.uptime_seconds = time.time() - self.status.start_time

    def status_report(self) -> dict[str, Any]:
        if self.status.running:
            self.status.uptime_seconds = time.time() - self.status.start_time
        return {
            "running": self.status.running,
            "uptime_seconds": round(self.status.uptime_seconds, 1),
            "total_ingestions": self.status.total_ingestions,
            "total_flywheel_iterations": self.status.total_flywheel_iterations,
            "total_datasets_generated": self.status.total_datasets_generated,
            "source_registry": self.source_registry.to_dict(),
            "graph_builder": self.graph_builder.to_dict(),
            "stream": self.stream_engine.to_dict(),
            "scheduler": self.task_scheduler.to_dict(),
            "flywheel": self.flywheel.to_dict(),
            "dataset_builder": self.dataset_builder.to_dict(),
            "data_expansion": self.ingestion.to_dict(),
        }

    def _enqueue_refresh_requests(self, results: list[IngestionResult]) -> int:
        requests: list[dict[str, Any]] = []
        for result in results:
            requests.extend(result.refresh_requests)
        return self.task_scheduler.enqueue_refresh_requests(requests, current_time=time.time())
