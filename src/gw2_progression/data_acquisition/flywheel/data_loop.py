"""Data Flywheel — the self-improving autonomous loop.

The flywheel implements:
  collect → graph → simulate → infer → dataset → repeat

Each iteration enriches the world model and generates training data
for the RL, behavior, and probabilistic layers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from gw2_progression.data_acquisition.ingestion.orchestrator import IngestionResult


@dataclass
class FlywheelIteration:
    """One iteration of the data flywheel."""
    iteration: int
    duration_ms: float
    sources_ingested: int
    total_entities: int
    total_relations: int
    graph_nodes: int
    graph_edges: int
    behavior_profiles: int
    dataset_samples: int
    status: str = "completed"
    error: str | None = None


@dataclass
class FlywheelConfig:
    iterations: int = 0  # 0 = infinite
    interval_seconds: float = 60.0
    ingest_all_on_start: bool = True
    run_simulation: bool = True
    run_inference: bool = True
    generate_dataset: bool = True
    save_checkpoints: bool = True
    checkpoint_dir: str = "data/checkpoints"
    dataset_dir: str = "data/datasets"


class DataFlywheel:
    """The core self-improving data flywheel.

    Each iteration:
      1. Ingest all sources (API, Wiki, Market)
      2. Build DGSK graph from ingested data
      3. Run OOSK simulation step
      4. Run behavior inference
      5. Generate training dataset
      6. Repeat

    This is the heart of the autonomous data factory.
    """

    def __init__(
        self,
        config: FlywheelConfig | None = None,
    ) -> None:
        self.config = config or FlywheelConfig()
        self.iteration_count = 0
        self.history: list[FlywheelIteration] = []
        self._running = False

        # Hooks set by the engine
        self._ingest_all_fn: Callable[[], list[IngestionResult]] | None = None
        self._graph_build_fn: Callable[[], dict[str, Any]] | None = None
        self._simulate_fn: Callable[[], Any] | None = None
        self._infer_fn: Callable[[], Any] | None = None
        self._dataset_fn: Callable[[int], int] | None = None
        self._checkpoint_fn: Callable[[int], None] | None = None

    def set_hooks(
        self,
        ingest_all: Callable[[], list[IngestionResult]],
        graph_build: Callable[[], dict[str, Any]],
        simulate: Callable[[], Any] | None = None,
        infer: Callable[[], Any] | None = None,
        dataset: Callable[[int], int] | None = None,
        checkpoint: Callable[[int], None] | None = None,
    ) -> None:
        self._ingest_all_fn = ingest_all
        self._graph_build_fn = graph_build
        self._simulate_fn = simulate
        self._infer_fn = infer
        self._dataset_fn = dataset
        self._checkpoint_fn = checkpoint

    def run_one_iteration(self) -> FlywheelIteration:
        """Execute one full flywheel iteration."""
        start = time.time()
        self.iteration_count += 1
        it = self.iteration_count

        try:
            # 1. Ingest all sources
            sources_ingested = 0
            total_entities = 0
            total_relations = 0
            if self._ingest_all_fn:
                results = self._ingest_all_fn()
                sources_ingested = len(results)
                for r in results:
                    total_entities += r.total_entities
                    total_relations += r.total_relations

            # 2. Build DGSK graph
            graph_nodes = 0
            graph_edges = 0
            if self._graph_build_fn:
                gdata = self._graph_build_fn()
                graph_nodes = gdata.get("total_nodes", 0) if isinstance(gdata, dict) else 0
                graph_edges = gdata.get("total_edges", 0) if isinstance(gdata, dict) else 0

            # 3. Run simulation
            if self._simulate_fn and self.config.run_simulation:
                self._simulate_fn()

            # 4. Run behavior inference
            behavior_profiles = 0
            if self._infer_fn and self.config.run_inference:
                inferred = self._infer_fn()
                if isinstance(inferred, dict):
                    behavior_profiles = len(inferred.get("profiles", {}) if isinstance(inferred.get("profiles"), dict) else inferred.get("profiles", []))

            # 5. Generate dataset
            dataset_samples = 0
            if self._dataset_fn and self.config.generate_dataset:
                dataset_samples = self._dataset_fn(it)

            # 6. Save checkpoint
            if self._checkpoint_fn and self.config.save_checkpoints:
                self._checkpoint_fn(it)

            duration = (time.time() - start) * 1000
            iteration = FlywheelIteration(
                iteration=it,
                duration_ms=round(duration, 2),
                sources_ingested=sources_ingested,
                total_entities=total_entities,
                total_relations=total_relations,
                graph_nodes=graph_nodes,
                graph_edges=graph_edges,
                behavior_profiles=behavior_profiles,
                dataset_samples=dataset_samples,
            )
            self.history.append(iteration)
            return iteration

        except Exception as e:
            duration = (time.time() - start) * 1000
            iteration = FlywheelIteration(
                iteration=it,
                duration_ms=round(duration, 2),
                sources_ingested=0,
                total_entities=0,
                total_relations=0,
                graph_nodes=0,
                graph_edges=0,
                behavior_profiles=0,
                dataset_samples=0,
                status="failed",
                error=str(e),
            )
            self.history.append(iteration)
            return iteration

    def run(self, iterations: int | None = None) -> list[FlywheelIteration]:
        """Run the flywheel for N iterations (or indefinitely)."""
        max_iters = iterations if iterations is not None else self.config.iterations
        self._running = True
        results: list[FlywheelIteration] = []

        while self._running:
            result = self.run_one_iteration()
            results.append(result)

            if max_iters > 0 and self.iteration_count >= max_iters:
                break

            if self.config.interval_seconds > 0 and self._running:
                time.sleep(self.config.interval_seconds)

        self._running = False
        return results

    def stop(self) -> None:
        self._running = False

    @property
    def average_duration_ms(self) -> float:
        if not self.history:
            return 0.0
        return sum(h.duration_ms for h in self.history) / len(self.history)

    @property
    def total_entities_collected(self) -> int:
        return sum(h.total_entities for h in self.history)

    @property
    def total_datasets_generated(self) -> int:
        return sum(h.dataset_samples for h in self.history)

    @property
    def last_iteration(self) -> FlywheelIteration | None:
        return self.history[-1] if self.history else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "iteration_count": self.iteration_count,
            "config": {
                "iterations": self.config.iterations,
                "interval_seconds": self.config.interval_seconds,
                "run_simulation": self.config.run_simulation,
                "run_inference": self.config.run_inference,
                "generate_dataset": self.config.generate_dataset,
            },
            "average_duration_ms": round(self.average_duration_ms, 2),
            "total_entities_collected": self.total_entities_collected,
            "total_datasets_generated": self.total_datasets_generated,
            "last_iteration": {
                "iteration": self.last_iteration.iteration,
                "duration_ms": self.last_iteration.duration_ms,
                "status": self.last_iteration.status,
                "sources_ingested": self.last_iteration.sources_ingested,
                "dataset_samples": self.last_iteration.dataset_samples,
            } if self.last_iteration else None,
            "history": [
                {
                    "iteration": h.iteration,
                    "duration_ms": h.duration_ms,
                    "status": h.status,
                    "entities": h.total_entities,
                    "samples": h.dataset_samples,
                }
                for h in self.history[-10:]
            ],
        }
