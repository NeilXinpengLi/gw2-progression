# GW2 Progression — 代码图谱与语义图谱分析

> 基于 GitNexus 知识图谱 + AST/源码扫描自动生成
> 生成日期: 2026-06-28 | 符号数: 7,643 | 执行流: 300 | 文件数: 228

---

## 目录

1. [项目总览](#1-项目总览)
2. [架构分层](#2-架构分层)
3. [代码图谱 — 功能模块 (Communities)](#3-代码图谱--功能模块-communities)
4. [API 路由图谱](#4-api-路由图谱)
5. [语义图谱 — 本体模型 (Ontology)](#5-语义图谱--本体模型-ontology)
6. [三轴业务本体 (DGSK → OOSK → BORS)](#6-三轴业务本体-dgsk--oosk--bors)
7. [状态轴 (State Axis)](#7-状态轴-state-axis)
8. [实体轴 (Entity Axis)](#8-实体轴-entity-axis)
9. [约束轴 (Constraint Axis)](#9-约束轴-constraint-axis)
10. [执行流程分析](#10-执行流程分析)
11. [数据流全景](#11-数据流全景)
12. [治理与安全模型](#12-治理与安全模型)
13. [架构决策记录](#13-架构决策记录)

---

## 1. 项目总览

**gw2-progression** 是一个面向《激战 2》(Guild Wars 2) 玩家的智能决策辅助系统。核心能力：

| 维度 | 说明 |
|------|------|
| **数据源** | GW2 官方 API（角色、物品、配方、交易行、成就、公会） |
| **语义层** | 本体模型（Ontology）将原始 API 数据映射为结构化对象和关系 |
| **生命周期引擎** | 反向推断 → 正向模拟 → 一致性验证 → 路径排序 |
| **AI 决策** | Expert AI Pipeline (Celery + LLM 推理层) |
| **价值衡量** | BORS 三层架构（业务 KPI → 价值图 → 决策引擎） |
| **治理** | QA 门禁 + 策略引擎 + 证据链 + 隐私策略 |
| **商业化** | 订阅 + 支付 + 许可证管理 |

### 技术栈

| 层 | 技术 |
|----|------|
| 框架 | Python 3.12 + FastAPI + Uvicorn |
| 数据库 | PostgreSQL (SQLAlchemy + Alembic) + SQLite (本体持久化) |
| 任务队列 | Celery + Redis |
| AI | LLM (OpenAI API) + LangChain |
| 前端 | 静态 JS (Vanilla JS 管理面板) |
| 图谱 | GitNexus (代码知识图谱分析) |

---

## 2. 架构分层

```
┌────────────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                           │
│  FastAPI REST endpoints  +  Static JS Dashboard  +  Agent API     │
├────────────────────────────────────────────────────────────────────┤
│                     APPLICATION / SERVICE LAYER                    │
│  snapshot_service  goal_driven_engine  progression_service        │
│  build_service     holdings_service    recipe_service             │
│  v4_learning       v5_learning        production_engine           │
├────────────────────────────────────────────────────────────────────┤
│                     EXPERT AI LAYER                                │
│  Celery Workers  →  ExpertRuntime  →  ReasoningEngine             │
│  LLMExpertLayer  →  Memory System  →  Persistence (JSON/PG)      │
├────────────────────────────────────────────────────────────────────┤
│                     LIFECYCLE ENGINE                               │
│  BackwardInference  →  StateEvolver  →  OOSKSimulator            │
│  HypothesisGenerator  →  DependencySolver  →  ConsistencyChecker  │
│  ItemCategorizer  →  RecipeResolver  (GW2 API integration)       │
├────────────────────────────────────────────────────────────────────┤
│                     ONTOLOGY / SEMANTIC LAYER                      │
│  Object Store  →  Graph Queries  →  QA Gate  →  Evidence Chain   │
│  Policy Engine  →  Action Registry  →  Tool Mesh                 │
├────────────────────────────────────────────────────────────────────┤
│                     BORS BUSINESS LAYER                            │
│  Business KPI  →  Value Graph  →  Decision Engine                 │
├────────────────────────────────────────────────────────────────────┤
│                     DATA INFRASTRUCTURE                            │
│  PostgreSQL  ↔  SQLite  ↔  Redis  ↔  GW2 API (external)          │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. 代码图谱 — 功能模块 (Communities)

GitNexus 自动聚类识别出 13 个功能模块 (Leiden 算法)：

| 模块 | 符号数 | 内聚度 | 核心职责 |
|------|--------|--------|----------|
| **Services** | 333 | 72% | 核心业务服务：快照、Build、配方、渐进式分析 |
| **Tests** | 141 | 95% | 全项目测试覆盖 |
| **Static** | 84 | 78% | 前端静态 JS 资源 |
| **Expert_ai** | 77 | 88% | AI 推理管线、LLM 集成、持久化 |
| **Ontology** | 64 | 87% | 本体模型、QA、证据链、策略引擎 |
| **Routes** | 51 | 76% | FastAPI 路由定义 |
| **Gw2_progression** | 48 | 80% | 核心库：Analyzer、GW2 Client、DB |
| **Bors** | 11 | 100% | 业务决策框架 (KPI → 决策) |
| **E2e** | 10 | 100% | 端到端测试 |
| **Object_graph** | 10 | 90% | 账户对象图谱映射 |
| **Domain_graph** | 10 | 100% | YAML 域定义 → OOSK/BORS 编译 |
| **Tool_mesh** | 9 | 94% | Agent 工具注册、治理、依赖 |
| **Memory** | 7 | 100% | Agent 记忆系统 (KV + 序列模式) |

### 模块间调用热力图 (Top 跨社区流)

```
Services ────→ Routes       (API 路由 → 服务实现)
Services ────→ Gw2_progression (服务 → DB/Client)
Routes  ────→ Services      (路由 → 逻辑委托)
Routes  ────→ Gw2_progression (路由直接调用)
Expert_ai ──→ Object_graph  (AI → 图映射)
Ontology ───→ Bors          (本体 → 业务决策)
```

---

## 4. API 路由图谱

### 4.1 路由分组

| 路由前缀 | 文件 | 路由数 | 说明 |
|----------|------|--------|------|
| `/auth/*` | `api/main.py` | 4 | 会话管理 (Session Token) |
| `/account` | `api/routes/account.py` | 1 | 账户总览 (大型端点) |
| `/analyze`, `/items/*`, `/delta`, `/listings/*` | `api/routes/valuation.py` | 11 | 物品估值市场分析 |
| `/generate`, `/plans`, `/templates` | `api/routes/progression.py` | 3 | 进度规划 |
| `/decide`, `/plan`, `/feedback`, `/strategies` | `api/routes/production.py`, `engine.py`, `v4.py` | 8 | 决策引擎 v4/v5 |
| `/experience`, `/model/*`, `/weights/*` | `api/routes/v5.py` | 6 | v5 学习系统 |
| `/crafting/calculate`, `/crafting/plan` | `api/routes/crafting.py` | 2 | 制作计算器 |
| `/signals`, `/sell-candidates`, `/buy-candidates` | `api/routes/tp_strategy.py` | 5 | 交易行信号 |
| `/guild/*` | `api/routes/guild.py` | 7 | 公会管理 |
| `/commercial`, `/checkout` | `api/routes/commercial.py` | 2 | 商业功能 |
| `/webhook`, `/checkout` | `api/routes/payment.py` | 2 | 支付集成 |
| `/workspace/*` | `api/routes/workspaces.py` | 3 | 工作区 |
| `/reports/*` | `api/routes/reports.py` | 4 | 报告 |
| `/lifecycle/*` | `lifecycle/api/lifecycle_api.py` | 9 | 生命周期引擎 |
| `/mesh/*` | 隐含在 data_mesh 集成 | — | 数据网格 |
| `/expert-ai/*` | `api/routes/expert_ai.py` | 14 | Expert AI API |
| `/subscription/*` | `api/routes/subscriptions.py` | 2 | 订阅管理 |
| `/quests/*` | `api/routes/quests.py` | 2 | 任务/成就 |
| `/insight` | `api/routes/insight.py` | 1 | 洞察数据 |
| `/credentials/*` | `api/routes/credentials.py` | 3 | 凭据管理 |

### 4.2 核心消费者的 API 形状匹配

当前仅 `/auth/session` 有前端消费者 (`session-manager.js`)，消费 `token` 字段。其余路由在前端消费映射方面存在缺口。

### 4.3 中间件链

所有路由通过两种中间件链：

```
1. Session Token 解析 → API Key 注入 (auth/session 路由)
2. DB 连接池 (_create_connection → Release_db 对)
```

---

## 5. 语义图谱 — 本体模型 (Ontology)

### 5.1 本体类定义 (10 个类)

来源: `ontology/config.py` 中的 `CLASS_DEFINITIONS`

| 类名 | 类型 | 必需属性 | 隐私范围 |
|------|------|----------|----------|
| `account_snapshot` | **entity** | account_name, snapshot_time, gold, currencies, materials | private |
| `account_asset` | **entity** | item_id, item_name, quantity, location, value | private |
| `legendary_goal` | **entity** | goal_name, target_item, materials_needed | private |
| `goal_requirement` | **entity** | requirement_name, item_id, quantity, satisfied | private |
| `reserved_asset` | **entity** | item_id, quantity, reserved_for | private |
| `guild_workspace` | **entity** | guild_id, guild_name | shared |
| `guild_member` | **entity** | account_name, role, joined_at | shared |
| `guild_goal` | **entity** | goal_name, target_item, contributors, progress | shared |
| `quest_progress` | **entity** | quest_name, quest_type, current, required, week | private |
| `market_signal` | **entity** | item_id, signal_type, confidence, price, volume | private |

### 5.2 关系类型 (8 种)

| 关系 | 来源 → 目标 | 含义 |
|------|-------------|------|
| `belongs_to` | asset/snapshot → account | 所属关系 |
| `requires` | goal → requirement/asset | 依赖关系 |
| `reserves` | goal → asset | 预留关系 |
| `contributes_to` | member → guild_goal | 贡献关系 |
| `generates` | snapshot → signal | 生成关系 |
| `tracks` | quest → account | 追踪关系 |
| `references` | report → snapshot/evidence | 引用关系 |
| `evidences` | evidence → object | 证明关系 |

### 5.3 动作类型 (7 种)

| 动作 | 前提条件 | 后置效果 |
|------|----------|----------|
| `snapshot_account` | — | 创建 account_snapshot + account_asset |
| `reserve_asset` | asset available | 创建 reserved_asset |
| `release_reservation` | reservation exists | 删除 reserved_asset |
| `sync_goal` | goal defines | 更新 goal_requirement, reserved_asset |
| `sync_guild` | guild membership | 更新 guild 对象 |
| `record_evidence` | object exists | 创建证据链 |
| `publish_report` | QA 通过 | 构建并发布报告 |

### 5.4 QA 检查类型 (22 种)

| 检查类型 | 验证逻辑 | 等级 |
|----------|----------|------|
| `exists` | 对象存在 | INFO |
| `freshness` | 时间戳未过 max_age | ERROR |
| `positive_int` | 值 > 0 | ERROR |
| `non_negative` | 值 >= 0 | ERROR |
| `enum` | 值在允许集合 | ERROR |
| `range_0_1` | [0, 1] | WARNING |
| `api_key_leak` | 不含 API Key 格式字符串 | BLOCKING |
| `non_empty` | 字符串非空 | WARNING |

---

## 6. 三轴业务本体 (DGSK → OOSK → BORS)

```
YAML Domain Definitions (DGSK)
    │  compile_to_oosk()
    ▼
OOSK Layer (运行时类型注册 + 对象存储)
    │  populate + validate
    ▼
BORS Layer (业务决策: KPI → 价值图 → 决策)
```

### 6.1 DGSK — 域定义图谱

来源: `domain_graph/domain_engine.py`

- **NodeDef**: type, properties, constraints, qa_checks, privacy_scope
- **EdgeDef**: type, cardinality, source/target type constraints
- **DomainEvent**: name, source, triggers, produces
- **DomainRule**: name, rule expression, severity
- **DomainGraphEngine**: 编译到 OOSK/BORS 格式，合并图，查找公共结构

### 6.2 OOSK — 对象图谱存储

来源: `object_graph/models.py` + `ontology/object_store.py`

```
Object Store
├── 内存: dict 索引 (O(1) 查找)
│   ├── _objects_by_id
│   ├── _objects_by_class
│   ├── _objects_by_account
│   ├── _relations_by_source
│   ├── _relations_by_target
│   └── _relations_by_type
└── 磁盘: SQLite 异步持久化 (fire-and-forget)
    ├── objects 表
    ├── relations 表
    └── actions 表
```

**关键查询**: `trace(entity_id, depth)` — 递归关系遍历，返回树结构

### 6.3 BORS — 业务决策框架

来源: `bors/business_*.py`

```
Entity State
    │  calculate_all()
    ▼
Business KPI (6 种, 0..1 归一化)
    ├── QUALITY      — QA 通过率
    ├── FRESHNESS    — 数据新鲜度
    ├── COVERAGE     — 数据源完整性
    ├── CONFIDENCE   — 置信度
    ├── RELIABILITY  — 历史准确率
    └── LIQUIDITY    — 市场流动性
    │  analyze_impact()
    ▼
ValueGraph (有向图传播)
    │  decide_from_kpis()
    ▼
DecisionEngine
    └── 5 种决策结果: APPROVE / REJECT / REVIEW / CERTIFY / DEFER
```

---

## 7. 状态轴 (State Axis)

### 7.1 角色状态结构

来源: `scripts/lifecycle_character_training.py` + `lifecycle/core/`

```python
{
    "inventory": {item_id: count},       # 物品库存
    "market": {item_id: price_data},     # 交易行行情
    "gold": float,                       # 金币
    "achievements": [achievement_id],    # 已完成成就
    "equipment": {slot: item_id},        # 装备
    "wallet": {currency_id: count},      # 钱包货币
    "_action_validations": [validation]  # 动作验证历史
}
```

### 7.2 动作类型 (8 种)

| 动作 | 状态效应 | 来源 |
|------|----------|------|
| `farm` | inventory[item] += qty, market[item] supply += qty | `state_evolver.py` |
| `gather` | 同 farm (语义不同) | `state_evolver.py` |
| `collect` | inventory[item] += qty | `state_evolver.py` |
| `trade` | inventory[item] += qty, market demand += qty | `state_evolver.py` |
| `craft` | 消耗 ingredients, 产生 output (支持 recipe_sourced) | `state_evolver.py` |
| `achievement` | achievements 列表追加 | `state_evolver.py` |
| `flip` | 同 trade (TP flip 语义) | `hypothesis_generator.py` |
| `sell` | inventory[item] -= qty, market 更新 | (预留) |

---

## 8. 实体轴 (Entity Axis)

### 8.1 核心数据类汇总

| 模块 | 类/数据类 | 字段数 | 用途 |
|------|-----------|--------|------|
| `object_graph/models.py` | `AccountObjectGraph` | 11 | 全量账户对象图 |
| `object_graph/models.py` | `CharacterNode` | 12 | 角色完整状态 |
| `object_graph/models.py` | `ItemNode` | 8 | 物品节点 |
| `object_graph/models.py` | `MarketGraph` | 4 | 交易行数据 |
| `ontology/models.py` | `OntologyObject` | 10 | 本体对象基类 |
| `ontology/models.py` | `OntologyRelation` | 7 | 本体关系 |
| `ontology/models.py` | `OntologyAction` | 15 | 本体动作 |
| `bors/business_decision.py` | `DecisionRecord` | 7 | 决策记录 |
| `bors/business_kpi.py` | `BusinessKPI` | 7 | KPI 度量 |
| `bors/business_value_graph.py` | `ValueNode` | 5 | 价值图节点 |
| `lifecycle/core/backward/dependency_solver.py` | `Dependency` | 6 | 依赖图节点 |
| `lifecycle/core/backward/hypothesis_generator.py` | `Hypothesis` | 4 | 假设路径 |
| `lifecycle/core/backward/inference_engine.py` | `InferredPath` | 9 | 推断路径 |
| `lifecycle/core/utils/item_categorizer.py` | `ItemInfo` | 8 | GW2 物品元数据 |
| `lifecycle/core/utils/recipe_resolver.py` | `RecipeInfo` | 6 | GW2 配方元数据 |
| `lifecycle/core/rules/crafting_rules.py` | `CraftingRecipe` | 7 | 制作配方 |
| `expert_ai/core.py` | `GraphNode` | 4 | AI 图谱节点 |
| `expert_ai/core.py` | `ExpertRuntime` | 6 | AI 运行时 |
| `expert_ai/core.py` | `ReasoningEngine` | 4 | 推理引擎 |
| `expert_ai/persistence.py` | `ExpertAIServiceConfig` | 9 | AI 持久化配置 |
| `expert_ai/persistence.py` | `LocalJsonStateStore` | 4 | JSON 状态存储 |
| `expert_ai/expert_layer.py` | `LLMExpertLayer` | 5 | LLM 推理层 |
| `ontology/tool_mesh/tool_registry.py` | `ToolDef` | 7 | Agent 工具定义 |
| `domain_graph/domain_engine.py` | `DomainGraph` | 7 | 域定义图谱 |

### 8.2 实体关系 ER 简图

```
Account (GW2 API)
  ├── Character [1..9]
  │   ├── Equipment [14 slots]
  │   ├── Inventory (bags) [0..250 items]
  │   └── Build [2 tabs]
  ├── Bank [250 slots]
  ├── Materials [1000+ items]
  ├── Wallet [53 currencies]
  ├── Achievements [3004 entries]
  ├── Guild [0..5]
  └── Trading Post Orders

Ontology Layer
  ├── account_snapshot → has → account_asset[*]
  ├── legendary_goal → requires → goal_requirement[*]
  ├── legendary_goal → reserves → reserved_asset[*]
  ├── guild_workspace → has → guild_member[*]
  ├── guild_workspace → has → guild_goal[*]
  └── account_snapshot → generates → market_signal[*]

Lifecycle Engine
  ├── State (inventory + market + achievements)
  ├── Step (action + item_id + quantity)
  ├── Dependency (entity DAG)
  └── Recipe (input ingredients → output item)

BORS
  ├── KPI (quality/freshness/coverage/confidence/reliability/liquidity)
  ├── ValueNode (entity → KPI → risk → decision)
  └── DecisionRecord (5 outcomes)
```

---

## 9. 约束轴 (Constraint Axis)

### 9.1 运行时约束 (DGSKConstraints)

来源: `lifecycle/core/rules/dgsk_constraints.py`

| 约束 | 规则 | 违反等级 |
|------|------|----------|
| `check_crafting` | 所有 inventory quantity >= 0 | ERROR |
| `check_economy` | 无负数价格/供需 | ERROR |
| `check_consistency` | 供需非负 | WARNING |
| `check_build` | 装备有 weapon/armor/accessory | WARNING |
| `is_terminal` | 所有 goal_items 在 inventory > 0 | (状态) |

### 9.2 动作验证 (StateEvolver)

| 条件 | 验证结果 |
|------|----------|
| craft 且 recipe_sourced=True 且 ingredients 充足 | `valid=True`, exact消耗 |
| craft 且 recipe_sourced=True 但 ingredients 不足 | `valid=False`, reason=具体缺少的原料 |
| craft 且 recipe_sourced=False | `valid=True`, 无数量校验 |
| farm/gather/collect/trade | `valid=True`, 标准加成 |
| achievement 重复 | `valid=False`, "already in list" |

### 9.3 一致性检查 (ConsistencyChecker)

| 维度 | 匹配阈值 |
|------|----------|
| `_dicts_match` (inventory, market, gold) | Jaccard ≥ 80% |
| `_lists_match` (achievements, equipment) | Jaccard ≥ 70% |
| `match_ratio` 总阈值 | ≥ 85% (tolerance=0.15) |

### 9.4 本体 QA 约束

| 检查 | 规则 |
|------|------|
| `freshness` | snapshot_time < max_age_hours 或 max_age_days |
| `api_key_leak` | properties 中无 UUID 格式 API Key |
| `private_fields` | 无 api_key / password 等敏感键名 |
| `build_source_freshness` | build 来源未过时 (build_trust.py) |

### 9.5 策略引擎 (PolicyEngine)

| 等级 | 时机 | 作用域 |
|------|------|--------|
| L1_STATIC | 编译时 | 类型定义约束 |
| L2_RUNTIME | 执行前 | 操作前提条件 |
| L3_GOVERNANCE | 执行后 | 全量治理合规 |

---

## 10. 执行流程分析

### 10.1 顶级流程 (Top 10 by 优先级)

| 流程名 | 步数 | 类型 | 出入口 |
|--------|------|------|--------|
| Api_feedback → _with_retry | 8 | cross_community | /feedback → DB |
| Post_plan → _get_client | 7 | cross_community | /plan → GW2 API |
| V4_optimize → _get_client | 7 | cross_community | /optimize → GW2 API |
| Post_experience → _with_retry | 7 | cross_community | /experience → DB |
| Post_recommendations → _get_client | 7 | cross_community | /recommendations → GW2 API |
| Post_generate → _safe | 6 | cross_community | /generate → DB |
| Post_decide → _safe | 6 | cross_community | /decide → DB |
| V4_decide → _safe | 6 | cross_community | /decide v4 → DB |
| Generate_plan_from_goal → _get_client | 6 | cross_community | 规划 → GW2 API |
| Post_value_analyze → _get_client | 6 | cross_community | /analyze → GW2 API |

### 10.2 标准化中间件模式

几乎所有流程遵循统一的中间件链：

```
Request
  → Session Token 解析 (auth middleware)
  → API Key 验证注入
  → DB 连接池 (with _create_connection / with Release_db)
  → 主处理逻辑
  → HTTP Response
```

### 10.3 GW2 API 集成流

```
post_analyze / post_decide / post_plan / post_progressive
  │
  ├──→ _get_client (创建 GW2Client)
  │      ├──→ fetch_account()
  │      ├──→ fetch_characters()
  │      ├──→ fetch_wallet()
  │      └──→ fetch_achievements()
  │
  ├──→ analyze (处理原始数据)
  │      ├──→ holdings_service.extract_*()
  │      └──→ build_service.calculate_readiness()
  │
  ├──→ decision/plan 引擎调用
  └──→ Response
```

### 10.4 生命周期重建流程

```
current_state (账户快照)
  │
  ├── ItemCategorizer.fetch_batch() — 分类所有物品
  ├── RecipeResolver.preheat_all() — 预热配方缓存
  ├── DependencySolver.register_account_dependencies() — 注册 DAG
  │
  ├── HypothesisGenerator.generate()
  │     ├── 按分类 + 加权选择物品
  │     ├── 对 equipment/upgrade 查真实配方
  │     └── 生成动作步骤
  │
  ├── BackwardInferenceEngine.infer_history()
  │     ├── 包裹为 InferredPath
  │     └── DGSKConstraints 验证
  │
  ├── OOSKSimulator.simulate_with_actions()
  │     ├── StateEvolver.evolve() × N steps
  │     └── 收集 _action_validations
  │
  ├── ConsistencyChecker.validate()
  │     ├── match_ratio ≥ 0.85 → 接受
  │     ├── match_ratio > 0.5 → 部分接受
  │     └── else → 拒绝
  │
  ├── PathRanker.rank()
  └── ranked trajectories output
```

---

## 11. 数据流全景

```
┌───────────────────────────────────────────────────────────┐
│                      GW2 API (External)                    │
│  /v2/account  /v2/characters  /v2/wallet                   │
│  /v2/items  /v2/recipes  /v2/commerce/prices              │
│  /v2/achievements  /v2/guild                              │
└─────────────────────────┬─────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────┐
│                gw2_client.py + analyzer.py                  │
│  fetches raw JSON → AccountContents dataclass              │
└─────────────────────────┬──────────────────────────────────┘
                          │
              ┌───────────┼────────────┐
              ▼           ▼            ▼
┌────────────────────┐ ┌──────────┐ ┌──────────────────────┐
│   Database (PG)    │ │ Memory   │ │  object_graph/       │
│  snapshot_service  │ │ Cache    │ │  mapper.py           │
│  reports/plans     │ │ (dict)   │ │  → AccountObjectGraph│
│  guilds/quests     │ │          │ └──────────┬───────────┘
└────────┬───────────┘ └──────────┘            │
         │                                     ▼
         │                     ┌──────────────────────────────┐
         │                     │      Ontology Layer          │
         │                     │  account_mapper.py           │
         ├─────────────────────┤  goal_mapper.py              │
         │                     │  guild_mapper.py             │
         │                     │  quest_mapper.py             │
         │                     │  market_mapper.py            │
         │                     │  object_store (SQLite)       │
         │                     └──────────┬───────────────────┘
         │                                │
         │                                ▼
         │                     ┌──────────────────────────────┐
         │                     │   QA Gate + Evidence Chain   │
         │                     │   Policy Engine              │
         │                     ├──────────┬───────────────────┘
         │                     │          │
         ▼                     ▼          ▼
┌────────────────────────────────────────────────────────────┐
│                     BORS Decision                           │
│  BusinessKPI  →  ValueGraph  →  DecisionEngine              │
│  → DecisionRecord (APPROVE/REJECT/REVIEW/CERTIFY/DEFER)    │
└────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────┐
│                    Static JS Dashboard                      │
│  account.html  +  session-manager.js  +  app-account.js     │
└────────────────────────────────────────────────────────────┘
```

---

## 12. 治理与安全模型

### 12.1 三层治理

| 层 | 机制 | 失效行为 |
|----|------|----------|
| **数据层** | QA Gate 验证对象模式 + 新鲜度 + 隐私 | BLOCKING errors 阻止发布 |
| **逻辑层** | 策略引擎 (L1/L2/L3) 评估 | ERROR 级别阻断流程 |
| **证据层** | SHA-256 哈希链证明数据来源 | 链断裂 = 不可信报告 |

### 12.2 隐私策略

- 每个 `OntologyObject` 带 `privacy_scope` ("private" / "shared")
- `account_snapshot` 等敏感数据默认 private
- `guild_*` 类为 shared (跨账户共享)
- QA Gate 的 `check_private_fields` 扫描泄露
- 发布报告时强制检查 privacy 合规

### 12.3 Agent 工具安全

- `FORBIDDEN_OPERATIONS` (4个禁止操作)
- `ALLOWED_WITH_OVERRIDE` (2个需覆写)
- Tool Registry 执行前输入 schema 校验
- Tool Graph 分析连锁影响
- Agent Tool Layer 编织: Forbidden → Policy → Execute → Memory

### 12.4 API Key 安全

- 40 字符阈值触发查找（非实时解密）
- Session Token 映射到 API Key
- QA Gate 正则扫描 UUID 格式 Key 泄露
- `delete_credential_endpoint` 凭据管理

---

## 13. 架构决策记录

| 决策 | 选择 | 替代方案 | 理由 |
|------|------|----------|------|
| 本体存储 | 内存 dict + SQLite 异步持久 | 纯 RDBMS / Redis | 读性能优先，写保底 |
| Schema 定义 | Python dicts (非 RDF/OWL) | RDF/OWL/SHACL | MVP 先行，零额外依赖 |
| 业务框架 | 3 层 BORS (KPI→Value→Decision) | 硬编码规则 | 可插拔、可解释、可审计 |
| AI 集成 | Celery + LLM (OpenAI) | 纯规则引擎 | 复杂推理需求 |
| 前端 | 静态 JS (无框架) | React/Vue | 零构建步骤，最小化依赖 |
| 图谱分析 | GitNexus (代码知识图谱) | 纯 AST 扫描 | 执行流、社区聚类、变更影响 |
| 生命周期 | 反向推断 + 正向模拟 + 验证 | 纯前向 / 纯反向 | 双向一致性保证 |
| 配方系统 | 预热所有 ~13K 配方 | 按需延迟加载 | 训练速度优先 |

---

> 本文档由 GitNexus 代码知识图谱自动分析生成，结合 AST 扫描和源码阅读。
> 符号数: 7,643 | 执行流: 300 | 功能模块: 13 | API 路由: 60+ | 本体类: 10 | 关系类型: 8
