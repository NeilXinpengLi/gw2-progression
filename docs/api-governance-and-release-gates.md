# API Governance and Release Gates

This document defines the production exposure model for GW2 Progression APIs.

## Categories

| Category | Purpose | Production posture |
|---|---|---|
| Core Product | Player-facing account value, search, crafting, goals, reports, builds, and planning | On by default |
| Commerce | Products, orders, licenses, payment, subscriptions, affiliates, delivery | On by default, guarded by idempotency tests |
| Infrastructure | Credentials, audit, workspaces, data mesh, ontology evidence/governance | On by default, reviewed as platform surface |
| AI Lab | V4/V5 experiments, Expert AI, Arena, Cognitive OS, rule evolution, lifecycle simulation | Off by default in production |

## Stability Levels

| Level | Meaning | Release gate |
|---|---|---|
| GA | Mature product path with contract tests and smoke coverage | Must pass core smoke or endpoint contract tests |
| Beta | Product or platform surface that is usable but still evolving | Must pass contract tests and owner review |
| Experimental | Research or AI Lab surface | Disabled in production unless explicitly enabled |
| Internal | Operational surface for platform use | Security/platform review required |

## Deployment Switches

The route registry lives in `src/gw2_progression/api/governance.py`. Runtime exposure is controlled by environment variables:

| Variable | Development default | Production default | Effect |
|---|---:|---:|---|
| `ENABLE_COMMERCE_ROUTES` | `true` | `true` | Enables Commerce APIs |
| `ENABLE_INFRASTRUCTURE_ROUTES` | `true` | `true` | Enables Infrastructure APIs |
| `ENABLE_AI_LAB_ROUTES` | `true` | `false` | Enables AI Lab APIs |
| `ENABLE_EXPERIMENTAL_ROUTES` | `true` | `false` | Allows routes marked Experimental |

Production compose sets `ENV=production`, `ENABLE_AI_LAB_ROUTES=false`, and `ENABLE_EXPERIMENTAL_ROUTES=false` by default.

## Role Boundaries

| Layer | Role | Must not |
|---|---|---|
| Goal-Driven OS | Product planning layer: interpret player goals and generate actionable plans | Become an experimental training runtime |
| Ontology Runtime | Governance/evidence layer: constraints, lineage, replay, evidence binding | Directly choose user actions without product-layer approval |
| Expert AI | Experimental training and simulation layer | Block core player flows or expose production decisions by default |
| Rule/Cognitive AI Lab | Research layer for rule evolution, agents, and simulation | Ship as stable user-facing APIs without promotion |

## Promotion Rules

To promote an API from AI Lab or Beta to Core Product GA:

1. Add or update route metadata in `API_ROUTE_GOVERNANCE`.
2. Add endpoint contract tests for request/response behavior.
3. Add the route to the core smoke suite if it is on the player critical path.
4. For Commerce, prove idempotency for order creation, webhook replay, license generation, and delivery retry.
5. Update this document and deployment defaults if production exposure changes.
6. Run GitNexus impact/detect-changes before committing.

## Current Critical Smoke Path

The minimum player smoke test is:

```text
auth -> value/analyze -> item search -> crafting -> goal-driven/generate -> report
```

Implemented in `tests/test_core_player_smoke.py`.

## Current Commerce Idempotency Path

Commerce release gates cover:

```text
order creation -> payment webhook replay -> license generation -> delivery retry
```

Implemented across `tests/test_commerce.py` and `tests/test_delivery.py`.
