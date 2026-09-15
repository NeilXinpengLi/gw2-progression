
# GW2 Synthetic World Simulation Engine — Codex Integration Specification (v1.0)

> Unified production-grade specification for GW2 Multi-Agent Simulation System
> Designed to be integrated into **gw2-progression (NOT standalone)**

---

# 0. ARCHITECTURE DECISION (CRITICAL)

## ❗ Should this system be independent?

### Answer: NO

This simulation system MUST be:

> # 🔗 A CORE SUBSYSTEM of `gw2-progression`

---

## Why?

### 1. Shared Ontology Requirement
- DGSK (Domain Graph) is shared between:
  - Account system
  - Insight system
  - Plan system
  - Simulation system

### 2. Single Source of Truth
- Simulation uses same graph model as real account data
- Prevents divergence between:
  - “real player state”
  - “synthetic world state”

### 3. AI Feedback Loop Dependency
- Insight/Plan modules require:
  - simulated futures
  - counterfactual reasoning

### 4. Data Flywheel Integration
- Simulation generates:
  - training data
  - reasoning graphs
  - BORS labels

➡ This feeds GW2 Progression AI directly

---

# 1. SYSTEM OVERVIEW

GW2 Synthetic World Simulation Engine is:

> A multi-agent economic + progression simulation layer embedded inside gw2-progression

It provides:

- Synthetic player behavior
- Economy simulation
- Time progression engine
- Automated labeling (BORS)
- Reasoning graph generation
- Training dataset factory
- Self-learning loop

---

# 2. INTEGRATION WITH GW2-PROGRESSION

## Modules mapping:

| gw2-progression module | simulation role |
|------------------------|-----------------|
| DGSK | shared world graph |
| OOSK | runtime engine |
| BORS | labeling system |
| Insight | consumes simulation output |
| Plan | uses simulated futures |
| Training | consumes generated dataset |

---

# 3. CORE ARCHITECTURE

```
GW2 API (seed)
   ↓
DGSK (shared graph layer)
   ↓
OOSK Simulation Engine
   ↓
Multi-Agent Interaction Engine
   ↓
Economy Simulator
   ↓
BORS Labeling Engine
   ↓
Reasoning Graph Generator
   ↓
Dataset Factory
   ↓
Training Loop
   ↓
Memory Feedback → DGSK/OOSK update
```

---

# 4. SYNTHETIC PLAYER SYSTEM

## Purpose
Generate infinite GW2-like agents.

## Player Types

- Trader Agent
- Crafter Agent
- Raider Agent
- Collector Agent
- Flipper Agent

## Schema

```python
class SyntheticPlayer:
    id: str
    goal: str
    style: str
    gold: float
    inventory: dict
```

## Behavior Policy

- trade()
- craft()
- flip()
- farm()

---

# 5. MULTI-AGENT INTERACTION ENGINE

## Purpose
Simulate economic interactions between players.

## Core Logic

```python
for agent in agents:
    action = agent.act(world)
    result = world.apply(action)
    log_interaction(agent, action, result)
```

## Interaction Types

- trade
- competition
- crafting demand
- market manipulation

---

# 6. SHARED WORLD GRAPH (DGSK EXTENSION)

## Node Types

- Item
- Currency
- Character
- Build
- MarketOrder

## Edge Types

- uses
- produces
- consumes
- depends_on
- affects_price

---

# 7. OOSK TIME ENGINE

## Purpose
Advance simulation time deterministically.

```python
for tick in range(T):
    world.time += 1
    update_agents()
    update_economy()
```

## Features

- deterministic replay
- time branching support (future simulation)
- snapshot rollback

---

# 8. ECONOMY SIMULATION ENGINE

## Price Model

```
price = f(supply, demand, velocity)
```

## Updates

- supply changes via crafting
- demand changes via meta shifts
- liquidity decay over time

---

# 9. BORS LABELING ENGINE

## Purpose
Auto-generate expert decision labels.

## Rules

```python
if demand_high and supply_low:
    label = HOLD

if profit > threshold:
    label = SELL

if crafting_required:
    label = CRAFT
```

## Outputs

- decision label
- score
- risk level

---

# 10. REASONING GRAPH GENERATOR

## Purpose
Convert simulation into causal reasoning chains.

## Format

```
Item → System → Meta → Decision
```

## Example

```
Mystic Coin
  ↓ used in
Legendary crafting
  ↓ affected by
Patch economy shift
  ↓ leads to
Demand increase
  ↓ decision
HOLD
```

---

# 11. DATASET FACTORY

## Output Dataset Schema

```json
{
  "state": {},
  "graph": {},
  "trajectory": [],
  "labels": {},
  "reasoning": []
}
```

## Versioning

- v1, v2, v3 datasets
- reproducible simulation seeds
- deterministic replay

---

# 12. SELF-TRAINING LOOP

## Cycle

1. simulate world
2. generate dataset
3. train model
4. evaluate performance
5. update policies
6. feed back into simulation

## Result

- continuous improvement loop
- synthetic data scaling
- self-evolving AI system

---

# 13. FASTAPI INTEGRATION

## Endpoints

```
/simulation/run
/simulation/reset
/world/snapshot
/agents/spawn
/economy/update
/labels/generate
/reasoning/build
/dataset/export
```

---

# 14. DOCKER ARCHITECTURE

```
services:
  gw2-progression-api
  simulation-engine
  worker-agents
  redis
  postgres
```

---

# 15. CRITICAL DESIGN PRINCIPLE

## ❗ Simulation is NOT separate system

It MUST:

- share DGSK graph
- feed BORS
- feed Insight engine
- feed training pipeline

---

# 16. SYSTEM ROLE IN GW2-PROGRESSION

| Component | Role |
|----------|------|
| Account | real data |
| Insight | interpretation |
| Plan | decision |
| Simulation | counterfactual world generation |
| Training | self-improving AI loop |

---

# 17. FINAL ARCHITECTURE

```
                 GW2-PROGRESSION CORE
                         │
        ┌────────────────┼────────────────┐
        │                                │
     REAL DATA                     SIMULATION LAYER
   (GW2 API)                     (Synthetic World)
        │                                │
        └──────────────┬───────────────┘
                       DGSK
                         ↓
                       OOSK
                         ↓
                       BORS
                         ↓
                     LLM Layer
                         ↓
                SELF-IMPROVING LOOP
```

---

# END
