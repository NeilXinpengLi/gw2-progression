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

## Phase 2: Rule And Lifecycle Adapters

Goal: replace heuristic warnings with real internal adapters.

Tasks:

1. Add `RuleValidationAdapter` that maps `PlanAction` into Rule Engine v2 validation facts.
2. Add `LifecycleSimulationAdapter` that maps plans into 7/14/30 day trajectory checks.
3. Return structured warning codes:
   - `budget:*`
   - `time:*`
   - `dependency:*`
   - `market:*`
   - `blocked:*`
4. Keep adapters internal and non-blocking.

Promotion gate:

```powershell
pytest -q tests/test_ai_lab_adapter.py tests/test_goal_driven.py tests/test_lifecycle.py tests/test_rule_engine_v2.py
```

## Phase 3: Ontology Evidence Binding

Goal: make AI-enhanced plans replayable and auditable.

Tasks:

1. Persist plan assessment as Ontology Runtime evidence.
2. Store compiled plan manifests with hash/signature.
3. Add durable replay checks for plan assessment lineage.
4. Add compatibility metadata for future replay versions.

Promotion gate:

```powershell
pytest -q tests/test_ontology_runtime_persistence.py tests/test_ontology_runtime_api.py tests/test_ai_lab_adapter.py
```

## Phase 4: Data Mesh Confidence

Goal: attach data freshness and source confidence to product recommendations.

Tasks:

1. Feed Data Mesh source freshness into action `data_sources`.
2. Add confidence penalties for stale market/account data.
3. Expose confidence summary in reports.
4. Add fallback reasons when source quality is low.

Promotion gate:

```powershell
pytest -q tests/test_data_mesh_v1.py tests/test_data_mesh_integration.py tests/test_core_player_smoke.py
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
| AI Lab integration | L2 isolated experiments | L2-L3 internal adapter |
| Goal-Driven plan evidence | L3 product rules | L3 product rules + AI Lab evidence annotations |
| Production exposure risk | Medium | Lower: no new public routes |
| User-facing value | Medium | Higher: plan warnings and simulation insight |

## Next Best Task

Implement Phase 2 adapters for Rule Engine v2 and Lifecycle so the current deterministic warnings become evidence-backed validation and simulation results.
