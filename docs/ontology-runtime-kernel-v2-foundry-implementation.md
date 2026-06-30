# GW2 Ontology Runtime Kernel v2 Foundry Implementation

Updated: 2026-07-01

## Design Target

`GW2_Ontology_Runtime_Kernel_v2_Foundry.md` defines one core shift:

> Everything is an Ontology-Validated Execution Graph.

The implementation now treats ingestion, simulation, decisioning, RL policy updates, constrained LLM actions, lineage, and replay as paths through the same deterministic ontology runtime.

## Architecture Mapping

| Foundry layer | Runtime implementation | Public API |
| --- | --- | --- |
| Ingestion + normalization gateway | `GW2APINormalizer`, `GraphBuilder`, `DGSKIngestor` | `POST /ontology/runtime/ingest` |
| Ontology registry | `OntologyRegistry.from_project_config()` with project schemas plus runtime decision/policy schemas | Runtime internal, exposed through graph manifest |
| Execution graph compiler | `ExecutionGraphCompiler`, `CompiledRuntimeGraph`, `ExecutionGraph` | `POST /ontology/runtime/compile` |
| Deterministic runtime kernel | `OntologyRuntimeKernel`, `ExecutionEngine`, `StateEngine`, `DAGExecutor` | `POST /ontology/runtime/action`, `POST /ontology/runtime/execute`, `POST /ontology/runtime/compiled/execute` |
| Temporal simulation | `OOSKSimulation` | `POST /ontology/runtime/simulate` |
| Decision layer | `BORSDecisionLayer`, `record_decision` ontology action | `POST /ontology/runtime/decision/decide` |
| RL optimization layer | `RLOptimizationLayer`, `apply_policy_weight` ontology action | `POST /ontology/runtime/rl/optimize` |
| Constrained LLM reasoning | `LLMConstrainedReasoning`, `validate_llm_action()` | `POST /ontology/runtime/llm/action`, `POST /ontology/runtime/reasoning/action` |
| Lineage + replay | `LineageStore`, `LineageTracker`, `ReplayEngine` | `GET /ontology/runtime/lineage`, `POST /ontology/runtime/replay` |

## Implemented Guarantees

| Guarantee | Implementation status | Verification |
| --- | --- | --- |
| Deterministic execution | Implemented. State hashes are generated from stable sorted JSON and replay uses the same execution engine. | `TestOntologyRuntimeKernel.test_kernel_state_transition_is_deterministic_for_same_actions` |
| Full traceability | Implemented. Each executed action records action hash, before/after state hashes, delta, and replayable action payload. | `TestOntologyRuntimeKernel.test_foundry_guarantees_are_replayable_after_decision_and_policy` |
| Ontology enforcement | Implemented. All entity, relation, update, decision, and policy actions pass registry validation before mutation. | `TestOntologyRuntimeKernel.test_foundry_compiler_manifest_and_guarantees_execute_as_dag` |
| Graph compilation | Implemented. Actions compile to a deterministic DAG manifest before compiled execution. | `POST /ontology/runtime/compile`; `tests/test_ontology_runtime_api.py` |
| Constrained AI reasoning | Implemented. LLM candidates are accepted only when they validate as ontology actions against current state. | Existing LLM guard tests and runtime guarantees endpoint |
| Lineage replay | Implemented. Replay reconstructs state from recorded lineage and reports mismatches. | `POST /ontology/runtime/replay`; guarantees endpoint |

## Design Decisions

- BORS does not mutate user state directly. It emits a `record_decision` ontology action, compiles it, and executes it through the kernel.
- RL does not hold a separate production decision authority. It emits `apply_policy_weight` ontology actions and records learned weights as governed ontology entities.
- LLM reasoning remains constrained. Candidate actions are validated by `OntologyRegistry.validate_action()` before execution.
- The graph compiler is the public boundary for Foundry-style execution. Compiled manifests include kernel version, graph id, action types, ontology surface, and guarantees.
- Lineage and replay are first-class runtime checks, not offline-only diagnostics.

## Current API Surface

| Route | Purpose | Stability |
| --- | --- | --- |
| `GET /ontology/runtime/state` | Snapshot current kernel state, lineage, and guarantees. | Experimental |
| `GET /ontology/runtime/guarantees` | Report runtime v2 guarantees and replay status. | Experimental |
| `POST /ontology/runtime/reset` | Reset in-memory kernel instance. | Test/Internal |
| `POST /ontology/runtime/action` | Execute one validated ontology action. | Experimental |
| `POST /ontology/runtime/execute` | Compile and execute an ad hoc action DAG. | Experimental |
| `POST /ontology/runtime/compile` | Compile actions into a Foundry manifest without mutating state. | Experimental |
| `POST /ontology/runtime/compiled/execute` | Compile and execute actions through the compiled graph path. | Experimental |
| `POST /ontology/runtime/simulate` | Run OOSK-style temporal steps through validated actions. | Experimental |
| `POST /ontology/runtime/decision/decide` | Record a BORS decision through the graph compiler. | Experimental |
| `POST /ontology/runtime/rl/optimize` | Record RL policy weights through the graph compiler. | Experimental |
| `POST /ontology/runtime/llm/action` | Validate and execute an ontology-constrained LLM action. | Experimental |
| `POST /ontology/runtime/reasoning/action` | Alias for constrained reasoning execution. | Experimental |
| `GET /ontology/runtime/lineage` | Export lineage records. | Experimental |
| `POST /ontology/runtime/replay` | Replay lineage and compare final state. | Experimental |

## Maturity Assessment

| Area | Maturity | Notes |
| --- | --- | --- |
| Registry and schema enforcement | Medium | Project schemas are loaded and runtime decision/policy schemas are explicit. Deeper semantic constraints are still basic. |
| DAG compilation | Medium | Dependency ordering and cycle detection exist. Manifest signing/version persistence is not yet implemented. |
| Runtime execution | Medium | Deterministic state transitions and lineage work in-process. Persistence and multi-tenant isolation remain future work. |
| OOSK simulation | Low-Medium | Simulation uses validated actions over ticks, but world evolution is still caller-supplied. |
| BORS decision layer | Low-Medium | Deterministic facade is implemented. Domain scoring needs richer production rules. |
| RL optimization | Low | Policy weights are captured as ontology records; training loop integration is not yet production-grade. |
| LLM reasoning | Medium | Guardrails reject invalid actions. Natural-language plan extraction is outside the current kernel. |
| Replay/audit | Medium | Replay is deterministic and tested. Long-term storage and cross-version replay are not yet built. |

## Release Gates

Before promoting the v2 runtime beyond experimental exposure:

1. `pytest -q tests/test_ontology.py::TestOntologyRuntimeKernel tests/test_ontology_runtime_api.py`
2. `ruff check src/gw2_progression/ontology/runtime_kernel.py src/gw2_progression/ontology/__init__.py src/gw2_progression/api/routes/ontology_runtime.py tests/test_ontology_runtime_api.py`
3. `npx gitnexus detect-changes --scope unstaged --repo gw2-progression`
4. Confirm `/ontology/runtime/guarantees` returns `deterministic_execution=true`, `lineage_replay=true`, and an empty `mismatches` list after the smoke flow.

