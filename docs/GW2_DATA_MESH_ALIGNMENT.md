# GW2 Data Mesh v1 — OpenCode 研发规范（可执行版）

> 合并目标：gw2-progression（训练管道） × gw2radar（生产基础设施） → 统一认知数据网格

---

## 一、架构总图

```
外部数据源 (GW2 API / gw2radar DB / wiki / reddit / efficiency)
     │
     ▼
┌───────────────────────────────────────────────────────────┐
│               Multi-Source Ingestion Layer                │
│  src/gw2_progression/data_mesh/integration.py             │
│  - gw2_api: fetch_all() + account_contents_to_runtime()   │
│  - gw2radar: GraphRepository.load_graph() bridge          │
│  - wiki/reddit: extensible adapter interface              │
└───────────────────────────────────────────────────────────┘
     │
     ▼
┌───────────────────────────────────────────────────────────┐
│              Schema Normalization Engine                   │
│  DataMeshBridge.normalize() → unified DGSK structure      │
└───────────────────────────────────────────────────────────┘
     │
     ▼
┌───────────────────────────────────────────────────────────┐
│          DGSK Graph Builder (core truth layer)             │
│  ├─ gw2radar DomainGraphEngine (YAML load, validate,      │
│  │   schema_diff, compile_to_oosk, compile_to_bors)       │
│  └─ gw2-progression domain_graph (local fallback)         │
│  三层图: public_game → private_player_state → personal    │
└───────────────────────────────────────────────────────────┘
     │
     ▼
┌───────────────────────────────────────────────────────────┐
│          OOSK Runtime Sync Engine (模拟层)                 │
│  ├─ gw2radar RuntimeStore + RuntimeMapper (production)    │
│  │   MemoryGraph, Planner, ConstraintEngine              │
│  └─ gw2-progression ExpertRuntime (local fallback)        │
│  输出: runtime world state snapshot                       │
└───────────────────────────────────────────────────────────┘
     │
     ▼
┌───────────────────────────────────────────────────────────┐
│          BORS Labeling Engine (决策层)                     │
│  ├─ gw2radar DecisionEngine (APPROVE/REJECT/REVIEW,      │
│  │   DecisionGraph, ValueGraph, WeightCalibrator)         │
│  └─ gw2-progression DecisionEngine (local fallback)       │
│  输出: SELL / HOLD / BUY / CRAFT / OPTIMIZE              │
└───────────────────────────────────────────────────────────┘
     │
     ▼
┌───────────────────────────────────────────────────────────┐
│          Knowledge Base (推理锚点层)                       │
│  ├─ gw2radar KB: 37 SQLite tables, 200+ PDF sources     │
│  │   kb_models, kb_repository, kb_entity_linker          │
│  │   KnowledgeArticle → KnowledgeChunk → KnowledgeRule   │
│  └─ 用途: LLM reasoning grounding, rule engine, schema   │
└───────────────────────────────────────────────────────────┘
     │
     ▼
┌───────────────────────────────────────────────────────────┐
│          Reasoning Dataset Generator (训练工厂)            │
│  ├─ gw2-progression TrainingPipeline (ETL → simulation   │
│  │   → reasoning → labeling → model artifact)            │
│  ├─ gw2-progression ModelTrainer + TrainingScheduler     │
│  ├─ SyntheticSimulationEngine (SyntheticPlayer agents)   │
│  └─ LLMExpertLayer (OpenAI-compatible, counterfactuals)  │
│  输出: {graph, state, label, reasoning, model_artifact}  │
└───────────────────────────────────────────────────────────┘
     │
     ▼
┌───────────────────────────────────────────────────────────┐
│              Self-Learning Data Flywheel                   │
│  1. ingest → 2. normalize → 3. DGSK build →              │
│  4. OOSK sync → 5. BORS label → 6. KB ground →          │
│  7. generate dataset → 8. train model → 9. repeat        │
└───────────────────────────────────────────────────────────┘
```

---

## 二、代码映射表

| Data Mesh 组件 | gw2radar 实现 | gw2-progression 实现 | 桥接模块 |
|---|---|---|---|
| DGSK Engine | `src/gw2radar/domain_graph/domain_engine.py` | `src/gw2_progression/domain_graph/domain_engine.py` | `data_mesh.integration.DataMeshBridge.get_dgsk_engine()` |
| DGSK Schema | `domain_schema.py:DomainGraph,NodeDef,EdgeDef` | `domain_graph.yaml` | 统一通过 YAML 加载 |
| OOSK Runtime | `src/gw2radar/oosk/runtime_store.py:RuntimeStore` | `src/gw2_progression/expert_ai/core.py:ExpertRuntime` | `get_oosk_runtime()` |
| OOSK Mapper | `src/gw2radar/oosk/runtime_mapper.py:RuntimeMapper` | `account_contents_to_runtime_payload()` | `sync_oosk()` |
| BORS Engine | `src/gw2radar/bors/decision_engine.py:DecisionEngine` | `src/gw2_progression/bors/business_decision.py:DecisionEngine` | `get_bors_engine()` |
| BORS Graph | `src/gw2radar/bors/decision_graph.py:DecisionGraph` | — | 通过 radar 使用 |
| Knowledge Base | `src/gw2radar/kb/` (200+ PDF, articles, chunks, rules) | — | `get_kb_status()` |
| Ingestion | `src/gw2radar/ingest/` (API client, gateway, sync) | `src/gw2_progression/gw2_client.py` | `multi_source_ingest()` |
| Security | `src/gw2radar/security/` (Fernet, stores, permissions) | `src/gw2_progression/services/auth_service.py` | 各守各自边界 |
| Training | — | `src/gw2_progression/expert_ai/training.py` | `run_training()` |
| Simulation | — | `src/gw2_progression/expert_ai/simulation.py` | 保留 gw2-progression |
| LLM Expert | — | `src/gw2_progression/expert_ai/expert_layer.py` | 保留 gw2-progression |

---

## 三、数据流（可执行流水线）

```python
# OpenCode 可执行伪代码 — 对应 scripts/bootstrap_expert_ai.py
from gw2_progression.data_mesh.integration import DataMeshBridge

mesh = DataMeshBridge(use_radar=True)  # 自动检测 gw2radar 是否已安装

# 1. 多源摄入
results = mesh.multi_source_ingest([
    {"type": "gw2_api", "params": {"api_key": api_key}},
    # future: {"type": "gw2radar", "params": {"db_path": "gw2radar.db"}},
])

# 2. Schema 归一化
normalized = mesh.normalize(results[0].get("payload", {}))

# 3. DGSK 编译
compiled = mesh.compile_domain_graph(yaml_path="domain_graph.yaml")

# 4. OOSK 同步
snap = mesh.sync_oosk(normalized["items"], normalized["relations"])

# 5. BORS 决策
decision = mesh.evaluate_decision("progression_health", [
    {"name": "liquid_wealth", "value": 0.7, "weight": 0.6, "impact": "positive"},
    {"name": "asset_risk", "value": 0.3, "weight": 0.4, "impact": "negative"},
])

# 6. KB 锚定
kb_grounded = mesh.ground_reasoning_with_kb(reasoning_chain)

# 7. 训练
models = mesh.run_training(dataset={"examples": [...]}, model_type="expert_reasoner", rounds=5)
```

---

## 四、核心原则（Codex 写入点）

| # | 原则 | 说明 |
|---|------|------|
| 1 | **DGSK = single source of truth** | 所有领域知识只在一个地方定义：`domain_graph.yaml` |
| 2 | **OOSK = runtime only** | OOSK 只做运行时状态快照，不做持久化 truth |
| 3 | **BORS = decision only** | BORS 只做决策，不碰原始数据 |
| 4 | **KB = reasoning grounding only** | 知识库只作为推理锚点，不驱动决策 |
| 5 | **Ingestion = observation only** | 数据摄入只是观察，不修改外部源 |
| 6 | **Layer isolation** | `public_game` / `private_player_state` / `personal_intelligence` 严格分层 |
| 7 | **Security boundary** | API Key 永远不离开 Fernet 加密存储，不被任何 API 端点明文返回 |

---

## 五、Docker 部署拓扑

```yaml
services:
  app:          # FastAPI (gw2-progression + gw2radar routes)
    build: .
    ports: ["8000:8000"]
  worker:       # Celery worker (训练任务队列)
    build: .
    command: celery -A gw2_progression.expert_ai.celery_app worker
  postgres:     # 持久化 (gw2radar 37 tables + gw2-progression)
    image: postgres:16-alpine
  neo4j:        # 图数据库 (可选，用于 DGSK 持久化)
    image: neo4j:5-community
  qdrant:       # 向量数据库 (KB embeddings)
    image: qdrant/qdrant:v1.9.7
  redis:        # 消息队列 + 缓存
    image: redis:7-alpine
```

---

## 六、测试验证点

| 测试 | 验证内容 | 位置 |
|------|----------|------|
| DGSK compile | YAML -> OOSK/BORS 编译无错误 | `tests/test_dgsk_compile.py` |
| Multi-source ingest | gw2_api + gw2radar 双源摄入 | `tests/test_mesh_ingest.py` |
| BORS decision | 加权因子决策正确 | `tests/test_bors_decision.py` |
| Training pipeline | ETL -> simulation -> model | `tests/test_expert_ai_infrastructure.py` |
| KB grounding | 推理链锚定到 KB 文章 | `tests/test_mesh_kb.py` |
| End-to-end mesh | 全流水线: ingest -> train | `tests/test_mesh_e2e.py` |

---

## 七、下一步：GW2 Data Mesh v2

当准备就绪后，可升级到 v2（实时流 + GNN + RL + LLM Agent Swarm）：

| 特性 | v1 | v2 |
|------|----|----|
| 数据流 | 批量 (batch) | 实时流 (streaming) |
| 图推理 | 规则引擎 | GNN 推理引擎 |
| 优化 | 静态 BORS | RL 优化层 |
| Agent | 合成玩家 (SyntheticPlayer) | LLM Agent Swarm |
| 部署 | Docker Compose | Kubernetes (k8s) |
| 分布式 | 单机 | Ray distributed cluster |
