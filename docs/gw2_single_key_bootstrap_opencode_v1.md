
# GW2 Single-Key Data Bootstrapping Strategy — OpenCode Spec v1.0

> Purpose: Build GW2 Expert AI training system from ONLY ONE real API key  
> Output: scalable synthetic + real hybrid dataset pipeline for gw2-progression

---

# 0. CORE PRINCIPLE

A single GW2 API key is NOT a limitation.

It is:

> 🌱 A "World Seed Node" for infinite synthetic expansion

---

# 1. SYSTEM OBJECTIVE

Transform:

```
1 GW2 API Key
→ 1 Account Snapshot
→ Full World Graph Seed
→ Infinite Synthetic Training Data
```

---

# 2. DATA STRATEGY OVERVIEW

4-layer expansion model:

```
L1: Real Seed Data (1 API key)
L2: DGSK Graph Expansion
L3: OOSK Simulation Expansion
L4: BORS + LLM Reasoning Expansion
```

---

# 3. L1 — REAL SEED DATA

## Source
- single GW2 API key

## Extract
- account
- characters
- inventory
- wallet
- achievements
- trading post snapshot

## Output
```
SeedGraph_v0
```

---

# 4. L2 — DGSK GRAPH BUILDING

## Convert API → Graph

Nodes:
- Item
- Character
- Currency
- Build
- Achievement

Edges:
- owns
- uses
- depends_on
- crafts
- consumes

## Output
```
WorldGraph_v0
```

---

# 5. L3 — OOSK SIMULATION ENGINE

## Purpose
Turn static graph into dynamic world

## Rule

```
state(t+1) = f(state(t), agent_actions)
```

## Output
- inventory evolution
- economy evolution
- build changes
- crafting chains

---

# 6. L4 — SYNTHETIC PLAYER SYSTEM

## Agents

- Trader
- Crafter
- Flipper
- Raider
- Collector

## Model

```
agent = (state + goal + policy)
```

## Actions

- trade
- craft
- farm
- speculate

---

# 7. L5 — ECONOMY SIMULATION

## Model

```
price = f(supply, demand, velocity)
```

## Dynamics

- crafting consumes supply
- trading shifts liquidity
- agents generate demand shocks

## Output
```
economic_time_series
```

---

# 8. L6 — BORS LABELING ENGINE

## Rule system

IF demand ↑ AND supply ↓:
    HOLD

IF profit > threshold:
    SELL

IF dependency missing:
    UPGRADE

## Output labels
- SELL
- HOLD
- BUY
- CRAFT

---

# 9. L7 — REASONING GRAPH GENERATION

Format:

```
Item → System → Meta → Decision
```

Example:

```
Mystic Coin
→ used in Legendary crafting
→ affected by meta shift
→ demand increases
→ HOLD
```

---

# 10. DATASET FACTORY OUTPUT

```json
{
  "graph": "DGSK",
  "trajectory": "OOSK simulation",
  "agents": "synthetic players",
  "economy": "price evolution",
  "labels": "BORS decisions",
  "reasoning": "LLM chains"
}
```

---

# 11. BOOTSTRAP FLOW

```
STEP 1: fetch API (1 key)
STEP 2: build DGSK graph
STEP 3: initialize OOSK world
STEP 4: spawn synthetic agents
STEP 5: simulate interactions
STEP 6: generate economy dynamics
STEP 7: apply BORS labeling
STEP 8: build reasoning graphs
STEP 9: store dataset versions
STEP 10: repeat loop
```

---

# 12. SELF-EXPANSION LOOP

```
real data → simulation → synthetic data → improved model → better simulation
```

---

# 13. SCALING STRATEGY

| Stage | Source | Scale |
|------|-------|------|
| Real | 1 API key | 1 world |
| Graph | DGSK | 10³ nodes |
| Simulation | OOSK | 10⁴ states |
| Agents | synthetic | 10⁵ actions |
| Reasoning | LLM | 10⁶ samples |

---

# 14. KEY INSIGHT

The system does NOT scale via data collection.

It scales via:

> world simulation depth

---

# 15. FINAL ARCHITECTURE

```
GW2 API (1 key)
   ↓
DGSK Graph Builder
   ↓
OOSK Simulation Engine
   ↓
Synthetic Agent System
   ↓
Economy Engine
   ↓
BORS Label Engine
   ↓
Reasoning Generator
   ↓
Dataset Factory
   ↓
Training Loop
```

---

# END
