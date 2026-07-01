# GW2 Progression 实现成熟度评估

Updated: 2026-07-01

Implementation progress:

- GitNexus refreshed: 15,826 nodes, 28,934 edges, 548 clusters, 300 execution flows.
- P0 completed: commercial idempotency now uses transaction-level serialization, payment event receipts, and real SQLite replay tests.
- P1 completed: license use is an atomic conditional update, delivery uses an outbox record, and Ontology Runtime API state is tenant-isolated through `X-Ontology-Tenant`.
- P1 completed: Ontology Runtime now persists tenant-scoped state/lineage and can replay from durable history.
- P2 completed: redundant Ontology Runtime public routes were removed; the API surface now centers on kernel action, scheduler execution, and durable replay.
- P2 completed: governance is exposed at `/api/governance/routes`, `production` is gated as AI Lab/Experimental, and CI tests scan Core Product routes for AI Lab decision dependencies.
- P2 completed: AI Lab is now integrated through an internal product-safe adapter for Goal-Driven plans, without exposing new production routes.
- P2 completed: AI Lab Adapter now invokes bounded Rule Engine v2 validation and Lifecycle simulation adapters for plan evidence.

## 1. 评估结论

当前系统已经从“功能原型堆叠”进入“有治理边界的 Beta 系统”阶段。Core Product 主流程已有 smoke suite，Commerce 已具备基础幂等模型，Ontology Runtime vFinal execution finalization 已形成统一执行内核、持久化 state/lineage 和 durable replay，AI Lab 与 Infrastructure 路由也已通过 governance 元数据和部署开关隔离。

完整实现层代码图谱见 `docs/architecture-code-graph-analysis.md`。

但整体尚未达到强生产级。主要短板集中在支付平台沙箱矩阵、交付任务死信/运营补偿、Ontology Runtime manifest 持久化/跨版本 replay 兼容性、以及长期运维可观测性。

## 2. 成熟度等级定义

| 等级 | 含义 |
| --- | --- |
| L0 Concept | 概念或接口存在，但未闭环。 |
| L1 Prototype | 可手动调用，缺少稳定测试和边界治理。 |
| L2 Alpha | 有局部测试，核心路径可跑通，但生产风险未收敛。 |
| L3 Beta | 有治理、测试、错误路径和部署开关，适合受控试运行。 |
| L4 Production Ready | 有并发安全、观测、审计、回滚、迁移和稳定 SLA。 |
| L5 Mature | 有自动化门禁、容量验证、长期兼容和运营闭环。 |

## 3. 模块成熟度总览

| 模块 | 当前等级 | 主要证据 | 主要缺口 |
| --- | --- | --- | --- |
| Core Product 玩家主流程 | L3 Beta | `tests/test_core_player_smoke.py` 覆盖 auth -> value/analyze -> item search -> crafting -> goal-driven/generate -> report。 | smoke 大量依赖 mock，缺少真实 GW2 API fallback、真实 DB fixture、端到端浏览器/API 契约测试。 |
| API Governance | L3 Beta | `src/gw2_progression/api/governance.py` 已按 Core Product、Commerce、AI Lab、Infrastructure 分类，并支持稳定性和开关。 | 还缺少自动 OpenAPI 分类导出、CI 发布门禁、生产环境开关快照审计。 |
| Commerce 订单/许可证 | L3 Beta | `create_order()` 支持 idempotency key 回放；同 key 创建在 `BEGIN IMMEDIATE` 写锁内串行化；真实 SQLite 测试覆盖重复 key。 | 仍缺少外部支付平台沙箱压测和版本化 migration。 |
| Payment Webhook | L3 Beta | `payment_events` 持久化 provider event receipt；重复 event 只 fulfillment 一次。 | 缺少 Stripe 沙箱乱序事件矩阵和人工补偿后台。 |
| Delivery Retry | L3 Beta | `delivery_outbox` 记录邮件副作用；delivery job 对 order 唯一；测试覆盖重复处理只发送一次。 | 缺少独立 outbox worker、死信队列和运营 dashboard。 |
| Ontology Runtime vFinal Execution | L3 Beta | `OntologyKernel.execute()` 是唯一状态变更入口；公开 API 已收敛到 `/kernel/action`、`/scheduler/execute`、`/persistence/replay`；state/lineage 按 tenant 持久化。 | compiled manifest 仍未持久化/签名；跨版本 replay 还没有长期兼容策略；长 lineage 未 checkpoint。 |
| Goal-Driven OS 职责边界 | L3 Beta | governance 中定义为 Core Product 的 product planning layer；Ontology Runtime 定位为 governance/evidence layer；Expert AI 归 AI Lab。 | 代码层还缺少硬性依赖约束，不能自动阻止 AI Lab 直接参与生产决策。 |
| AI Lab 隔离 | L3 Beta | production 默认禁用 experimental/AI Lab 路由；测试覆盖。 | 还缺少部署时路由快照检查、运行时安全告警、实验数据与生产数据隔离策略。 |
| 数据库/迁移 | L2 Alpha | SQLite schema 有基础外键、部分唯一约束、连接池和 WAL。 | schema 直接内嵌在 `CREATE_TABLES`，缺少版本化 migration；幂等和交付约束不完整。 |
| Observability/运维 | L2 Alpha | API 有 request id、基础 metrics、security headers、rate limit。 | 缺少 structured audit for commerce、webhook event log、delivery retry dashboard、SLO/error budget。 |

## 4. 商业化幂等成熟度

### 已实现

- 订单创建支持调用方传入 `idempotency_key`。
- 重复 key 会查询 `order_idempotency_keys` 并返回已有订单/许可证。
- Stripe webhook 使用 `stripe:{event_id}` 作为幂等 key。
- license key 具备数据库唯一约束。
- delivery job 可失败后重试。

### 风险点

1. 订单创建已具备基础并发安全。
   当前流程在存在 idempotency key 时先进入 `BEGIN IMMEDIATE`，再查询/创建订单，真实 SQLite 测试验证同 key 并发只产生一个 order/license/delivery job。

2. webhook receipt 已有单独表。
   `payment_events` 记录 provider event、状态、order_id、错误信息。仍需补 Stripe 沙箱乱序事件和运营补偿界面。

3. delivery 副作用已改为 outbox 模型。
   delivery job 创建 outbox 记录，邮件发送状态记录在 `delivery_outbox`。仍需独立 worker 和死信策略。

4. license 使用计数已改成原子条件更新。
   `use_license()` 使用单条 `UPDATE ... WHERE used_count < max_uses`，真实并发测试验证不会超过 `max_uses`。

### 升级到 L4 的门槛

- 已完成：idempotency 事务锁定、`payment_events`、`licenses.order_id` 唯一索引、`delivery_jobs.order_id` 唯一约束、license 条件更新、真实 SQLite 并发测试。
- 未完成：版本化 migration、支付沙箱矩阵测试、outbox worker/死信队列、运营补偿界面。

## 5. Ontology Runtime vFinal 成熟度

### 已实现

- 所有 action 先通过 `OntologyRegistry.validate_action()`。
- action graph 可编译成 `CompiledRuntimeGraph`，manifest 包含 kernel version、action types、ontology surface 和 guarantees。
- DAG 执行经过 `DAGExecutor`，支持依赖顺序和 cycle detection。
- BORS 决策层只产生 `record_decision` ontology action。
- RL 优化层只产生 `apply_policy_weight` ontology action。
- LLM action 必须通过 constrained reasoning guard。
- lineage/replay 可验证 deterministic state hash。
- state/lineage 已通过 `ontology_kernel_states` 和 `ontology_kernel_lineage` 按 tenant 持久化。
- `/ontology/runtime/persistence/replay` 可从 durable lineage 重建最终 state 并校验 persisted/replayed hash。

### 风险点

1. guarantee 目前是运行时自报为主。
   `guarantees()` 对 replay 做了验证，但 `ontology_enforcement=True`、`graph_compilation=True` 等仍是能力声明，不是每个历史 action 的证明集合。

2. snapshot 调用会触发 replay。
   当前规模小可接受，但随着 lineage 增长会有性能压力。

3. runtime 已具备 durable state/lineage，但缺少长期 checkpoint。
   API 路由通过 `X-Ontology-Tenant` 分配独立 kernel，并可从 SQLite 恢复 tenant state；长历史 replay 性能和 schema 迁移策略仍未实现。

4. manifest 没有持久化或签名。
   编译结果可返回，但还不能作为长期审计证据。

### 升级到 L4 的门槛

- 为 compiled graph manifest 加 `schema_version`、签名/hash、持久化表。
- 已完成：将 state/lineage 持久化，支持按 tenant 分区 replay。
- 将 guarantees 拆成 evidence 列表，例如每条 action 的 validation result、compiler result、replay result。
- 增加 lineage 大小/性能测试和 replay 快照 checkpoint。
- 已完成：API 层加 tenant 边界，禁止共享 `_kernel` 状态污染。

## 6. API Governance 成熟度

### 已实现

- 所有主路由纳入 `API_ROUTE_GOVERNANCE`。
- 分类覆盖 Core Product、Commerce、AI Lab、Infrastructure。
- 稳定性等级覆盖 GA、Beta、Experimental、Internal。
- 生产环境默认禁用 AI Lab/Experimental。
- tests 覆盖路由元数据完整性和生产开关行为。

### 风险点

- governance 目前是 Python 字典，并已通过 `/api/governance/routes` 暴露运行时快照；尚未写入 OpenAPI extension 或部署产物。
- 如果新增 route 但未加入 `ROUTER_BINDINGS`，治理测试无法发现。
- Internal 路由仍依赖 `ENABLE_INFRASTRUCTURE_ROUTES`，没有鉴权层硬隔离。

### 升级到 L4 的门槛

- CI 中固定运行 governance tests。
- 已完成：`/api/governance/routes` 输出 route category/stability/gate。
- production 启动时打印并持久化路由快照。
- Internal/Beta 路由加鉴权或 admin guard，而不只靠 include/exclude。

## 7. 测试成熟度

| 测试类型 | 当前状态 | 成熟度 |
| --- | --- | --- |
| Core smoke | 已覆盖最小玩家价值链。 | L3 |
| Commerce idempotency | 覆盖 mock 行为与 webhook key 传递。 | L2 |
| Ontology runtime | 覆盖 DAG、replay、BORS/RL、API、持久化 replay。 | L3 |
| Governance | 覆盖分类完整性和生产开关。 | L3 |
| 并发测试 | 基本缺失。 | L1 |
| 真实 DB 集成测试 | 局部不足。 | L1-L2 |
| 浏览器 E2E | 未形成发布门禁。 | L1 |

## 8. 推荐发布门禁

### 目前可作为 Beta 门禁

```powershell
pytest -q tests/test_api_governance.py tests/test_core_player_smoke.py tests/test_commerce.py tests/test_delivery.py tests/test_ontology_runtime_smoke.py tests/test_ontology_runtime_api.py tests/test_ontology.py::TestOntologyRuntimeKernel
ruff check src/gw2_progression/api/governance.py src/gw2_progression/api/routes/ontology_runtime.py src/gw2_progression/ontology/runtime_kernel.py
npx gitnexus detect-changes --scope unstaged --repo gw2-progression
```

### 进入 Production Ready 前必须新增

- 已新增 `tests/test_commerce_idempotency_db.py`：真实 SQLite，重复 idempotency key 并发创建订单只产生一个 order/license/delivery job。
- 已新增 `tests/test_payment_webhook_db.py`：同一 Stripe event 重放只记录一次 fulfilled。
- 已新增 `tests/test_license_atomic_usage.py`：并发使用 license 不超过 `max_uses`。
- 已新增 `tests/test_delivery_outbox.py`：delivery retry 不重复发送，失败可恢复。
- 已新增 `tests/test_ontology_runtime_tenant_replay.py`：不同 tenant runtime state 不互相污染。
- 已新增 `tests/test_ontology_runtime_persistence.py`：Ontology Runtime state/lineage 持久化后可重新加载并 durable replay。

## 9. 优先级路线图

1. Completed P0：修强商业化幂等的数据库并发安全。
2. Completed P0：为 payment webhook 增加事件 receipt/outbox 表。
3. Completed P1：把 license 使用计数改成原子条件更新。
4. Completed P1：为 delivery job 增加唯一约束和 outbox 发送记录。
5. Completed P1：为 Ontology Runtime 增加 tenant/session 隔离。
6. Completed P1：为 Ontology Runtime 增加 tenant-scoped state/lineage 持久化与 durable replay。
7. Completed P2：将 API governance 输出到运行时快照。
8. Completed P2：把 AI Lab 到生产决策的边界改成代码层依赖约束和 CI 检查。
9. Completed P2：移除 Ontology Runtime 冗余公开路由，保留单 action、DAG scheduler、durable replay 三类主入口。
10. Completed P2：新增 AI Lab Adapter 第一阶段，将实验层作为 Goal-Driven 内部证据增强器，而不是公开决策 API。
11. Completed P2：AI Lab Adapter 接入 Rule Engine v2 与 Lifecycle 的内部 validation/simulation evidence。

## 10. 总体评级

| 维度 | 当前评级 |
| --- | --- |
| 功能完整性 | L3 Beta |
| 商业化安全性 | L2-L3 |
| 架构治理 | L3 |
| 智能层职责收敛 | L3 |
| 生产运维 | L2 |
| 发布门禁 | L2-L3 |

总体判断：当前代码适合 Beta/受控试运行，不建议直接承诺强生产级商业化交付。下一轮最应该集中在 compiled manifest 持久化/签名、跨版本 replay 兼容、长 lineage checkpoint，以及 AI Lab adapter 收敛，这些会继续降低生产决策和审计风险。
