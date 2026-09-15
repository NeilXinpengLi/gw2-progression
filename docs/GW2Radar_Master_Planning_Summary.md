# GW2Radar / GW2 Progression 全部规划与系统设计汇总（统一主文档）

> 版本：v1.0 Unified Master Plan  
> 用途：作为后续独立讨论 / 开发拆分 / Codex执行的总纲  
> 系统范围：GW2Radar + GW2 Progression Engine + SaaS + Credential + Growth + Productization

---

# 1. 项目总目标（统一定义）

GW2Radar 的最终形态不是工具，而是：

> **GW2 Player Progression Intelligence System（玩家成长决策系统）**

核心能力：

```text
输入：GW2账号数据（API Key）
输出：
- 资产价值
- 目标差距
- 最优成长路径
- 7天行动计划
- Build推荐
- 制作路径优化
```

---

# 2. 核心系统演进路径

```text
v1: 数据系统（Data System）
    ↓
v2: 决策系统（Decision System）
    ↓
v3: 规划系统（Planning Agent）
    ↓
v4: 自适应Agent系统（Adaptive Agent）
    ↓
SaaS：商业化平台（Report + Subscription + Team）
```

---

# 3. GW2 Progression Engine v1（决策系统）

## 3.1 核心目标

```text
把 GW2账号状态 → Top-K 最优行动
```

---

## 3.2 系统结构

```text
Account State
    ↓
Feature Extraction
    ↓
Action Generator
    ↓
Scoring Engine
    ↓
Ranking Engine
    ↓
Top-K Actions
```

---

## 3.3 Action模型

```text
SELL_ITEM
BUY_ITEM
FARM_MATERIAL
CRAFT_ITEM
COMPLETE_ACHIEVEMENT
IMPROVE_BUILD
```

---

## 3.4 scoring函数

```text
score =
  gold_gain * 0.4
+ progress_gain * 0.3
+ build_impact * 0.2
- time_cost * 0.3
- risk * 0.2
```

---

## 3.5 v1输出

```json
Top 5 Actions:
- Sell Mystic Coin
- Farm Fractals
- Craft Ascended Gear
- Buy materials
- Improve Build
```

---

# 4. GW2 Progression Engine v2（规划系统）

## 4.1 核心升级

```text
v1 = 推荐（ranking）
v2 = 规划（planning + DAG）
```

---

## 4.2 核心结构

```text
Account State
    ↓
Goal Interpreter
    ↓
Action Generator v2
    ↓
Planning Engine (DAG)
    ↓
Optimization Engine
    ↓
Execution Plan (7-day)
```

---

## 4.3 Action Chain（关键升级）

```text
SELL → BUY → CRAFT → BUILD → COMPLETE GOAL
```

---

## 4.4 DAG规划

```text
Sell items
    ↓
Buy materials
    ↓
Craft components
    ↓
Craft legendary
    ↓
Complete goal
```

---

## 4.5 输出

```text
Day 1 → Sell items
Day 2 → Farm fractals
Day 3 → Buy materials
Day 4 → Craft components
Day 5 → Continue chain
Day 6 → Build optimization
Day 7 → Goal completion
```

---

# 5. GW2 Progression v3（Agent系统）

## 5.1 核心升级

```text
v2 = 计划
v3 = 自动动态调整计划（Agent）
```

---

## 5.2 核心能力

```text
- real-time replanning
- market reaction
- user behavior learning
- adaptive optimization
```

---

## 5.3 Agent输出

```text
Today you should:
1. Sell surplus
2. Farm fractals
3. Craft missing parts

If market changes:
→ replan automatically
```

---

# 6. GW2Radar SaaS架构（可上线）

## 6.1 系统架构

```text
Frontend (Dashboard / Reports)
    ↓
FastAPI Backend
    ↓
GW2 Engine (Value / Crafting / Build)
    ↓
Credential Layer (BYOK)
    ↓
Data Layer (PostgreSQL + Redis)
    ↓
External APIs (GW2 / LLM / Search)
```

---

## 6.2 核心模块

```text
Value Engine
Crafting Engine
Build Engine
Goal Engine
Report Engine
Agent Engine
Credential Center
```

---

# 7. Credential / BYOK系统

## 7.1 模式

```text
Session-only (default)
Encrypted storage
Team workspace
```

---

## 7.2 Provider类型

```text
GW2 API
LLM (OpenAI / Claude / DeepSeek)
Search APIs
Commerce APIs
Map APIs
```

---

## 7.3 安全机制

```text
- no logging keys
- fingerprint only
- encrypted storage
- audit logs
- revoke / rotate
```

---

# 8. 产品化系统（Gumroad式）

## 8.1 产品类型

```text
Account Value Report
Legendary Gap Report
Build Readiness Report
Weekly Progression Plan
Guild Analysis Report
```

---

## 8.2 商业流

```text
Landing Page
    ↓
API Key Input
    ↓
Free Report
    ↓
Paywall
    ↓
Full Report
    ↓
PDF + Dashboard
    ↓
Subscription
```

---

# 9. Growth系统

## 9.1 流量来源

```text
Reddit (r/GW2)
Discord Guilds
Twitch / YouTube
GW2 communities
```

---

## 9.2 Viral Loop

```text
User generates report
    ↓
shares link
    ↓
others view
    ↓
enter API key
    ↓
new users
```

---

## 9.3 留存

```text
Weekly report
Email updates
Goal tracking
Build alerts
```

---

# 10. GW2 Progression核心三层

```text
1. Wealth Layer → 我有什么
2. Gap Layer → 我缺什么
3. Action Layer → 我该做什么
```

---

# 11. GW2 Progression核心公式

```text
Progression Score =

gold_efficiency
+ build_progress
+ goal_completion
- time_cost
- risk
```

---

# 12. MVP上线结构

## API

```text
/analyze
/value
/gap
/decide
/plan
```

---

## 输出

```text
- Value Report
- Build Report
- Crafting Report
- 7-Day Plan
```

---

# 13. 产品定位统一

GW2Radar不是：

```text
GW2工具 ❌
```

而是：

```text
GW2 Decision System ✅
GW2 Progression Intelligence System ✅
```

---

# 14. 最终系统定义

```text
GW2Radar =
A system that converts GW2 account data into optimal player progression decisions.
```

---

# 15. 下一步方向（预留）

```text
- 自动Agent执行系统
- 市场预测模型
- Build推荐学习系统
- 公会级分析系统
- 完整订阅SaaS化
```
