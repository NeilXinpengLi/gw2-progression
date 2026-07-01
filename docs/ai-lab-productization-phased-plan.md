# AI Lab Productization Phased Plan

Updated: 2026-07-01

## Strategy

AI Lab systems should not become parallel production decision engines. The product-safe pattern is:

```text
AI Lab candidate/evidence -> Product adapter -> Ontology validation/evidence -> Core Product response
```

Role boundaries:

| Layer | Production role |
| --- | --- |
| Goal-Driven OS | User-facing product planning layer |
| Ontology Runtime | Evidence, constraints, lineage, replay, audit |
| AI Lab / Cognitive OS / Rule v2 / Lifecycle / Expert AI | Candidate generation, validation, simulation, training, evaluation |
| Data Mesh | Data quality, freshness, confidence, source governance |

## Phase 1 Completed: Internal AI Lab Adapter

Implemented:

- `src/gw2_progression/services/ai_lab_adapter.py`
- `enhance_plan_with_ai_lab(plan, parsed, account_state)`
- Integration into `generate_plan_from_goal()`
- Tests in `tests/test_ai_lab_adapter.py` and `tests/test_goal_driven.py`

Behavior:

- Does not expose new production routes.
- Does not reorder or replace Goal-Driven actions.
- Adds evidence source `ai_lab_adapter:v1`.
- Adds deterministic plan validation and 7-day cost/time simulation.
- Annotates action `risk_reason`, `data_sources`, and plan `insight`.
- Fails open so Core Product remains available if adapter logic fails.

## Phase 2 Completed: Rule And Lifecycle Adapters

Goal: replace heuristic warnings with real internal adapters.

Implemented:

1. Added `RuleValidationAdapter` that maps `PlanAction` into bounded Rule Engine v2 simulation rules.
2. Added `LifecycleSimulationAdapter` that maps plans into Lifecycle validation state and action trajectory checks.
3. Returned structured warning codes:
   - `budget:*`
   - `time:*`
   - `dependency:*`
   - `market:*`
   - `blocked:*`
   - `rule:*`
   - `lifecycle:*`
4. Kept adapters internal and non-blocking.

Promotion gate:

```powershell
pytest -q tests/test_ai_lab_adapter.py tests/test_goal_driven.py
pytest -q tests/test_rule_engine_v2.py::TestRuleEngineV2::test_simulate_rules tests/test_lifecycle.py::TestLifecycleEngine::test_simulate_forward tests/test_lifecycle.py::TestLifecycleEngine::test_validate_state
```

Note: the full Rule Engine v2 + Lifecycle experimental test suite currently exceeds the 124 second local command limit when run together, so the Phase 2 gate uses focused smoke coverage for the directly invoked engine methods.

## Phase 3 Completed: Ontology Evidence Binding

Goal: make AI-enhanced plans replayable and auditable.

Implemented:

1. `OntologyEvidenceAdapter` persists plan assessment as an Ontology Runtime `evidence` entity.
2. Evidence content is hash-chained with `create_chain_link()`.
3. Evidence is written through `OntologyKernel.execute_kernel_action()` so validation, lineage, persistence, and replay all use the single kernel path.
4. Adapter tests reload tenant state and verify durable replay remains deterministic.

Promotion gate:

```powershell
pytest -q tests/test_ontology_runtime_persistence.py tests/test_ontology_runtime_api.py tests/test_ai_lab_adapter.py
```

Remaining for L4: persist full compiled plan manifests with schema compatibility metadata and signature policy.

## Phase 4 Completed: Data Mesh Confidence

Goal: attach data freshness and source confidence to product recommendations.

Implemented:

1. Added `DataMeshConfidenceAdapter`.
2. Mapped existing action `data_sources` into Data Mesh source types and registry IDs.
3. Added merged confidence summaries to `AIPlanAssessment.data_confidence`.
4. Added low-confidence and missing-record warnings with `data_mesh:*` codes.
5. Added confidence penalties and risk notes for low-confidence actions.
6. Included Data Mesh confidence in Ontology evidence content.

Promotion gate:

```powershell
pytest -q tests/test_ai_lab_adapter.py tests/test_goal_driven.py tests/test_core_player_smoke.py
pytest -q tests/test_data_mesh_v1.py tests/test_data_mesh_integration.py
```

## Phase 5: Expert AI Offline Training Loop

Goal: use Expert AI to improve future plans without blocking current users.

Tasks:

1. Export anonymized plan/action/outcome events.
2. Train offline candidate rankers.
3. Compare AI-ranked candidates against deterministic baseline in Arena.
4. Promote only if adapter contract tests and replay audits pass.

Production rule:

Expert AI can suggest candidates, but Core Product must keep final response ownership.

## Current Maturity Impact

| Area | Before | After Phase 1 |
| --- | --- | --- |
| AI Lab integration | L2 isolated experiments | L3 internal adapter with Rule/Lifecycle/Ontology/Data Mesh evidence |
| Goal-Driven plan evidence | L3 product rules | L3 product rules + AI Lab/Rule/Lifecycle/Data Mesh evidence annotations and ontology persistence |
| Production exposure risk | Medium | Lower: no new public routes |
| User-facing value | Medium | Higher: plan warnings and simulation insight |

## Next Best Task

Implement Phase 5 Expert AI offline training loop so anonymized plan/action/outcome events can improve future candidate ranking without blocking production users.
