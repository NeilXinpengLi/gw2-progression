# GW2 Expert AI Training Infrastructure

> Status: implemented foundation
> Source spec: `GW2_Expert_AI_Training_Infrastructure_Codex.md`

## Phase Mapping

| Phase | Spec Area | Implementation |
|-------|-----------|----------------|
| P1 | DGSK domain graph | `gw2_progression.expert_ai.core.ExpertAISystem.compile_graph()` |
| P2 | OOSK runtime | `ExpertRuntime`, `GraphStore`, `/runtime/*` |
| P3 | BORS decision layer | `DecisionEngine` facade via `/decision/evaluate` |
| P4 | Reasoning engine | `ReasoningEngine`, `/reasoning/analyze`, `/reasoning/trace` |
| P5 | Economy simulator | `EconomySimulator`, `/economy/simulate` |
| P6 | Meta build engine | `MetaBuildEngine`, `/meta/analyze_build` |
| P7 | Multi-agent planner | `MultiAgentPlanner`, `/plan/generate` |
| P8 | Memory feedback loop | append-only `MemorySystem`, `MemoryFeedbackLoop`, `/memory/*` |
| P9 | Training dataset pipeline | `training.build_dataset()`, `/training/dataset` |
| P10 | GW2 account training adapter | `account_contents_to_runtime_payload()`, `/training/account_snapshot` |
| P11 | Production persistence adapters | `ExpertAIPersistence`, `/persistence/*` |
| P12 | LLM expert layer | read-only `LLMExpertLayer`, `/expert/*` |

## API Surface

```text
POST /graph/compile
GET  /graph/{id}
POST /graph/node
POST /graph/edge

POST /runtime/snapshot
GET  /runtime/state
GET  /runtime/entity/{entity_id}
GET  /runtime/search
GET  /runtime/neighbors/{node_id}
GET  /runtime/trace/{node_id}
POST /runtime/action
POST /runtime/rollback
POST /runtime/simulate
GET  /runtime/history
POST /simulation/run
POST /simulation/reset
GET  /world/snapshot
POST /agents/spawn

POST /reasoning/analyze
POST /reasoning/trace
POST /reasoning/build

POST /economy/simulate
POST /economy/update
POST /data/economy
POST /meta/analyze_build
POST /meta/analyze
POST /data/meta
POST /etl/account_raw
POST /plan/generate
POST /agents/run
POST /decision/evaluate

POST /memory/append
GET  /memory/search
POST /memory/query
POST /memory/update_patterns
POST /memory/feedback
GET  /memory/feedback/status

GET  /persistence/health
GET  /persistence/readiness
POST /persistence/snapshot
POST /persistence/migrate
POST /persistence/graph/export
POST /persistence/graph/write
POST /queue/enqueue
POST /queue/dequeue
GET  /memory/vector/search

POST /expert/explain
GET  /expert/provider
POST /expert/provider/key_file
POST /expert/counterfactuals
POST /expert/think

POST /training/dataset
POST /training/account_snapshot
POST /train/run
POST /train/model
POST /train/schedule
POST /train/scheduler/run_due
GET  /train/jobs

GET  /observability/metrics
GET  /observability/audit
POST /labels/generate
POST /dataset/export
```

## Phase 2 Production Adapters

- `ExpertAIPersistence` adds explicit Neo4j, Qdrant, Postgres, Redis, and local JSON state boundaries.
- Postgres migrations are exposed through `/persistence/migrate`.
- `/persistence/readiness` performs live, non-throwing readiness checks against configured Neo4j, Qdrant, Postgres, and Redis services.
- Runtime snapshots and memory events write to local JSON plus configured Postgres/Qdrant services.
- Graph state can be exported as Cypher or written to Neo4j.
- Redis queue enqueue/dequeue supports worker consumption and successful worker runs acknowledge tasks after processing, with Celery worker wiring in `gw2_progression.expert_ai.celery_app`.
- `LLMExpertLayer` provides read-only explanation, graph interpretation, counterfactual, and expert-thinking APIs.
- `MemoryFeedbackLoop` observes decision outcomes, appends feedback events, updates patterns, and adjusts memory-derived reasoning weights.
- `docker-compose.expert-ai.yml` starts FastAPI with Postgres, Neo4j, Qdrant, Redis, and a worker entrypoint.

```bash
docker compose -f docker-compose.expert-ai.yml up --build
```

The default test suite uses deterministic local adapters and does not require external services to be running.

## Phase 3 Full Production Pipeline

- OOSK now supports `update_state`, `simulate_step`, and `trace_history`.
- `/runtime/simulate` executes one or more deterministic simulation steps and records state transitions.
- `/runtime/history` exposes replayable transition history.
- `/memory/query` returns in-memory episodic results and can optionally include vector search.
- `/train/run` executes a deterministic ETL -> simulation -> reasoning graph -> BORS labeling -> dataset versioning -> training metrics -> feedback loop.
- Dataset versions are deterministic from dataset type and graph size, for example `full_production-n2-e1`.

## Phase 4 Scheduler, Trainer, Data Sources, Agents

- `EconomyDataSource` and `MetaBuildDataSource` provide injectable real-data facades for market and meta build inputs.
- `AgentOrchestrator` coordinates Economy, Meta, Build, Planner, and Coordinator decisions.
- `ModelTrainer` emits auditable model artifacts and metrics for deterministic training execution.
- `TrainingScheduler` schedules one-shot or recurring training jobs, optionally dispatching through Redis.
- `/train/model`, `/train/schedule`, `/train/scheduler/run_due`, and `/train/jobs` expose trainer/scheduler operations.

## Phase 5 Real Provider, Raw Account ETL, Observability

- `LLMExpertLayer` supports OpenAI-compatible chat/completions providers via env vars or a local key file. Provider status always redacts the API key.
- `raw_account_to_runtime_payload()` imports exported account raw JSON such as `gw2-account-Netro.7195-2026-06-28.json` into runtime graph entities and relations.
- Raw account ETL also derives economy simulator rows and meta build rows.
- `ModelTrainer` writes auditable model artifact JSON files under `data/expert_ai_models`.
- `ObservabilityHub` tracks counters and audit events for train, agent, and ETL flows.
- Celery task dispatch supports `train_run`, `model_train`, `agents_run`, `run_due`, `feedback`, `migrate`, and `health`.

## Phase 6 Synthetic World Simulation Engine

- `SyntheticSimulationEngine` is embedded in `gw2_progression.expert_ai` rather than shipped as a standalone system.
- `SyntheticPlayer` agents cover trader, crafter, raider, collector, and flipper styles.
- The simulation shares OOSK runtime state, writes synthetic players into the runtime graph, and emits replayable simulation steps.
- Economy updates use supply, demand, and velocity to update item prices deterministically.
- BORS-style labels are generated as `HOLD`, `SELL`, `CRAFT`, or `REVIEW`.
- Reasoning output follows the `Item -> System -> Meta -> Decision` chain shape.
- Dataset export emits `{state, graph, trajectory, labels, reasoning}` with deterministic simulation seed versioning.
- Celery task dispatch supports `simulation_run`.

To run the external-service smoke test after the compose stack is healthy:

```bash
RUN_EXPERT_AI_E2E=1 python -m pytest tests/test_expert_ai_compose_e2e.py -q
```

## Guarantees

- Runtime mutations go through OOSK actions or explicit runtime APIs.
- Decisions go through BORS `DecisionEngine`.
- LLM-facing reasoning is read-only and produces structured chains.
- Memory is append-only.
- Runtime snapshots are replayable through rollback.
- Persistence exports are explicit adapters; external services are not mutated by read-only expert endpoints.
- GW2 account snapshots can be converted into runtime graph entities and training examples without allowing LLM state mutation.

## Known Semantic Graph Gap

`domain_graph.yaml` currently defines a `progresses` relation from `quest` to `legendary_goal`, but `quest` is not defined as a node. The compiler reports this instead of silently ignoring it.
