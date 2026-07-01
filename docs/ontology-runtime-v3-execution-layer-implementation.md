# GW2 Ontology Runtime v3 Execution Layer Implementation

Updated: 2026-07-01

## Target

`GW2_Ontology_Runtime_v3_Execution_Layer.md` requires the runtime to move from a Foundry-style design system to a fully executable ontology runtime:

```text
Ontology -> DAG -> Scheduler -> Executor -> State -> Lineage -> Replay
```

The implementation keeps the existing v2 Foundry public surface, but upgrades the execution path so compiled graphs are run by a deterministic scheduler and every action records validation and scheduler evidence.

## Implemented Mapping

| v3 requirement | Implementation |
| --- | --- |
| Execution DAG core | `ExecutionGraph`, `ExecutionGraphNode`, `get_ready_nodes()`, `mark_executed()`, `execution_status()` |
| Runtime scheduler loop | `RuntimeScheduler.run()` repeatedly dispatches dependency-ready nodes in deterministic sorted order |
| Real executor engine | `DAGExecutor.execute_node()` calls `OntologyRuntimeKernel.execute()` with scheduler evidence |
| Strict ontology validation gate | `OntologyValidator.validate()` runs before every state transition |
| Deterministic state transition | `StateEngine.transition()` remains the only mutation path |
| Lineage backbone | `LineageTracker.record()` stores action hash, state hashes, validation evidence, and scheduler evidence |
| Replay engine | `ReplayEngine.replay()` reconstructs state from lineage actions and checks hashes |
| API entry point | `POST /ontology/runtime/scheduler/execute` returns graph, scheduler trace, and execution result |

## Runtime Guarantees

The kernel now reports `kernel_version = v3-execution-layer` and exposes:

- deterministic execution
- full traceability
- ontology enforcement
- graph compilation
- DAG-based scheduling
- constrained AI reasoning
- lineage replay
- evidence-backed lineage
- persistent state and lineage store through the execution-finalization layer

## API Surface

Recommended runtime API:

- `POST /ontology/runtime/kernel/action` for single validated ontology actions.
- `POST /ontology/runtime/scheduler/execute` for action DAG execution.
- `POST /ontology/runtime/persistence/replay` for durable replay checks.

Removed legacy API surface:

- `POST /ontology/runtime/action`
- `POST /ontology/runtime/execute`
- `POST /ontology/runtime/compiled/execute`
- `POST /ontology/runtime/decision/decide`
- `POST /ontology/runtime/rl/optimize`

These routes were replaced by the kernel and scheduler ingress paths to keep the public surface small. Internal kernel methods still exist for adapters and unit tests.

`kernel_version` remains `v3-execution-layer` for execution-model compatibility. The persistent execution-finalization marker is exposed as `finalization_version = vFinal-execution-finalization`.

## Verification

Covered by:

- `tests/test_ontology.py::TestOntologyRuntimeKernel`
- `tests/test_ontology_runtime_api.py`
- `tests/test_ontology_runtime_persistence.py`
- `tests/test_ontology_runtime_smoke.py`
- `tests/test_ontology_runtime_tenant_replay.py`

## Maturity Assessment

Current maturity: L3 Beta.

The v3 execution layer now has a real scheduler loop, strict validation before mutation, deterministic state transitions, lineage evidence, and replay verification. That is enough for controlled runtime use and API-level experimentation.

Remaining gaps before L4 Production Ready:

- compiled graph manifests are not persisted or signed
- replay does not yet validate cross-version graph compatibility
- scheduler does not yet expose retry/rollback policies
- large lineage performance and checkpointing are not covered
- persistent lineage now exists, but it does not yet have checkpointing, pruning, or schema migration policy

Priority after v3:

1. Persist compiled manifests by tenant.
2. Add manifest schema/version compatibility checks during replay.
3. Add replay checkpoints for long-running histories.
4. Add scheduler failure policy support.
