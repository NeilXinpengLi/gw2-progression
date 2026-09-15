# GW2 Progression GitNexus 重建后差异版架构报告

生成日期：2026-07-01  
仓库：`D:\Projects\gw2-progression`  
旧报告：`docs/architecture-code-graph-analysis.md`  
本报告目的：记录 GitNexus 索引权限修复、重新索引结果，以及新旧图谱对系统架构判断的差异。

## 1. 修复结果

### 1.1 问题

上一版分析时 GitNexus 报告：

- 索引落后 HEAD 7 个提交。
- 执行 `npx gitnexus analyze` 失败。
- 失败点：`.gitnexus\lbug`
- 错误：`Access is denied`

### 1.2 已执行修复

处理过程：

1. 检查 `.gitnexus` 目录属性，发现目录带 `ReadOnly` 属性。
2. 清理 `.gitnexus` 及子项的只读属性。
3. 发现旧 `lbug` 文件仍无法改名，进一步检查到多个 `gitnexus mcp` Node 进程正在运行。
4. 停止 `gitnexus mcp` 进程以释放旧索引数据库句柄。
5. 重新执行：

```powershell
npx gitnexus analyze --force
```

结果：

```text
Repository indexed successfully (77.8s)
15,430 nodes | 28,143 edges | 541 clusters | 300 flows
D:\Projects\gw2-progression
```

### 1.3 新索引状态

`npx gitnexus status` 输出：

```text
Repository: D:\Projects\gw2-progression
Indexed: 2026/7/1 00:26:17
Indexed commit: edb6fc7
Current commit: edb6fc7
Status: ✅ up-to-date
```

`.gitnexus\meta.json` 显示：

| 项 | 值 |
|---|---|
| indexed commit | `edb6fc7b3c29b4d729fec3b01d1baccee77670a0` |
| indexedAt | `2026-06-30T16:26:17.578Z` |
| files | 441 |
| nodes | 15430 |
| edges | 28143 |
| communities | 541 |
| processes | 300 |
| graph provider | `ladybugdb` available |
| FTS provider | `ladybugdb-fts` available |
| embeddings | 0 |

说明：索引权限问题已修复，CLI 侧图谱已是最新。

## 2. 新旧图谱规模差异

| 指标 | 旧图谱 | 新图谱 | 变化 |
|---|---:|---:|---:|
| indexed commit | `ffe0dc1` | `edb6fc7` | 前进 7 个提交 |
| files | 431 | 441 | +10 |
| nodes / symbols | 14701 | 15430 | +729 |
| edges / relationships | 26880 | 28143 | +1263 |
| communities / clusters | 520 | 541 | +21 |
| processes / flows | 300 | 300 | 0 |
| embeddings | 0 | 0 | 0 |
| index status | stale | up-to-date | 已修复 |

结论：近 7 个提交主要增加了文件、符号、关系和功能社区数量，但 GitNexus 仍截取 300 条执行流；核心执行流集合没有出现结构性替换。

## 3. 新索引下的图谱发现

### 3.1 最高步数执行流

新索引下按 `stepCount` 排序的前 20 个执行流仍以跨社区 API 流程为主：

| 流程 | 类型 | 步数 |
|---|---|---:|
| `Api_feedback -> _with_retry` | cross_community | 8 |
| `Post_plan -> _get_client` | cross_community | 7 |
| `V4_optimize -> _get_client` | cross_community | 7 |
| `Post_experience -> _with_retry` | cross_community | 7 |
| `Api_feedback -> _create_connection` | cross_community | 7 |
| `Post_webhook -> _create_connection` | cross_community | 7 |
| `Insight_data -> _create_connection` | cross_community | 6 |
| `Post_generate -> _safe` | cross_community | 6 |
| `Post_decide -> _safe` | cross_community | 6 |
| `Post_plan -> _safe` | cross_community | 6 |
| `V4_decide -> _safe` | cross_community | 6 |
| `Get_report_html -> _get_client` | cross_community | 6 |
| `V4_optimize -> _safe` | cross_community | 6 |
| `Generate_plan_from_goal -> _get_client` | cross_community | 6 |
| `Post_value_analyze -> _get_client` | cross_community | 6 |
| `Post_experience -> _create_connection` | cross_community | 6 |
| `Get_weights -> _create_connection` | cross_community | 6 |
| `Get_quests -> _create_connection` | cross_community | 6 |
| `Post_generate_plan -> _get_client` | cross_community | 6 |
| `Api_decide -> _get_client` | cross_community | 6 |

差异判断：

- 上一版同样显示估值、计划、V4、feedback、webhook、商业报告是高频跨社区流程。
- 新增可见项包括 `Api_decide -> _get_client`，但没有改变“核心 API 编排 + service 层 + DB/GW2 client”的总体架构判断。

### 3.2 核心链路查询差异

#### 账号分析与估值

新索引查询 `account analysis valuation fetch GW2 API account holdings price snapshots` 返回的关键流程：

- `Post_value_analyze -> _get_client`
- `Post_value_analyze -> _safe`
- `Get_items_search -> _row_value`
- `Get_items_search -> _decode_data_sources`
- `Account_overview -> Extract_wallet_holdings`

关键符号：

- `post_value_analyze`：`src/gw2_progression/api/routes/valuation.py`
- `run_full_analysis`：`src/gw2_progression/services/snapshot_service.py`
- `search_latest_holdings`：`src/gw2_progression/database.py`
- `search_items_by_name`：`src/gw2_progression/services/item_search_service.py`
- `normalize_account`：`src/gw2_progression/services/snapshot_service.py`

差异判断：

- 上一版估值主链路为 `post_value_analyze -> run_full_analysis`，新图谱保持一致。
- 新图谱额外把 `Account_overview -> Extract_wallet_holdings` 纳入相关结果，说明账号概览链路在当前 HEAD 中和估值/持仓能力的关系更明确。
- 成熟度判断维持：高。

#### Goal-Driven 计划生成

新索引查询 `goal driven plan generation interpret goal progression plan actions` 返回的关键流程：

- `Post_generate -> _safe`
- `Generate_commercial -> _safe`
- `Get_report_html -> _get_client`
- `Get_report_html -> _safe`
- `Post_generate -> _get_client`

关键符号：

- `post_generate`：`src/gw2_progression/api/routes/goal_driven.py`
- `generate_plan_from_goal`：`src/gw2_progression/services/goal_driven_engine.py`
- `generate_commercial_report`：`src/gw2_progression/services/report_generator.py`
- `generate_commercial`：`src/gw2_progression/api/routes/commercial.py`
- `get_report_html`：`src/gw2_progression/api/routes/commercial.py`

差异判断：

- Goal-Driven 主流程仍是 `post_generate -> generate_plan_from_goal`。
- 商业报告流程在同一查询中排序靠前，说明“计划生成 -> 报告/商业化输出”的连接在图谱中较强。
- 成熟度判断维持：中高。

#### Expert AI

新索引查询 `expert AI training infrastructure simulation feedback scheduler celery agents` 仍没有返回主执行流程，只返回 definitions：

- `celery_app.py`
- `process_expert_ai_task`
- `api/routes/expert_ai.py`
- `TrainingPipeline`
- `ExpertAISystem`
- `TrainingScheduler`
- `scripts/bootstrap_expert_ai.py`

差异判断：

- 与上一版一致：Expert AI 基础设施模块存在且内聚，但尚未成为主业务图谱执行流的中心。
- 它更像独立平台/实验基础设施，而不是当前玩家核心路径的强依赖。
- 成熟度判断维持：中到中低，主要风险仍是外部依赖多、生产闭环复杂。

## 4. 源码层补充统计

在新 HEAD 下，源码与测试统计如下：

| 指标 | 当前值 |
|---|---:|
| `src/tests/docs` 下文件数 | 453 |
| `src/gw2_progression/api/routes` route 文件数 | 33 |
| service 文件数 | 45 |
| HTTP/WebSocket decorator 数 | 279 |
| `def test_` / `class Test` 匹配数 | 1378 |

这些统计强化了上一版结论：系统是宽功能 FastAPI 单体，业务 service 层较厚，测试覆盖面广，但全量测试需要分层执行。

## 5. 架构结论变化

### 5.1 未变化的结论

以下判断保持不变：

- 系统主体仍是 FastAPI 单体应用。
- SQLite 仍是主应用默认持久化。
- 核心玩家功能仍围绕账号抓取、估值、物品搜索、制作优化、目标计划、Build 推荐展开。
- 商业化、订阅、许可证、交付、联盟分销已形成独立运营层。
- Cognitive OS、Ontology、Rule Engine、Expert AI 仍是偏智能/实验/平台化的增强层。
- Data Mesh 仍是数据治理和多源接入的基础设施层，尚未成为所有核心流程的必经路径。

### 5.2 有变化的结论

新图谱带来的修正：

- 上一版报告中的“索引落后 7 个提交”已失效；当前索引已对齐 HEAD。
- 图谱规模增加明显，说明近 7 个提交不是纯文档变更，而是带来了新增符号和关系。
- `Account_overview -> Extract_wallet_holdings` 进入估值相关查询结果，账号概览与估值链路的图谱相关性增强。
- `Api_decide -> _get_client` 进入最高步数流程列表，V4/决策类 API 在当前图谱中更突出。
- FTS 现在显示 `available`，上一版分析时 CLI 输出曾提示 FTS extension unavailable；本次重建后检索能力状态改善。

### 5.3 成熟度矩阵修订

| 功能域 | 上一版成熟度 | 新版成熟度 | 变化 |
|---|---|---|---|
| 账号抓取与估值 | 高 | 高 | 不变 |
| 物品搜索与价格质量 | 高 | 高 | 不变 |
| 制作计算与优化 | 高-中高 | 高-中高 | 不变 |
| Goal-Driven 计划生成 | 中高 | 中高 | 不变，和商业报告关系更清晰 |
| Build 推荐 | 中高 | 中高 | 不变 |
| Data Mesh | 中 | 中 | 不变 |
| Ontology Runtime | 中 | 中 | 不变 |
| Cognitive OS / Rule Engine v2 | 中 | 中 | 不变，决策/V4 流程更突出 |
| Expert AI | 中-中低 | 中-中低 | 不变，仍未进入主执行流 |
| 商业化 | 中 | 中 | 不变，报告链路在 Goal 查询中更突出 |
| 部署运维 | 中 | 中 | GitNexus 索引维护能力改善 |
| 测试体系 | 中高 | 中高 | 不变，本次未重跑全量 pytest |

## 6. 当前仍需注意的问题

1. 本次为了释放 `.gitnexus\lbug` 文件句柄，停止了当前会话中的 `gitnexus mcp` Node 进程。CLI 查询已可正常使用，但当前 Codex 会话里的 MCP transport 仍可能需要重启会话或重新拉起 MCP 才能恢复。
2. `.gitnexus` 是生成产物，重建成功后只有 `.gitignore`、`lbug`、`meta.json`，旧的 `csv` 临时目录已被清理。
3. 新索引已经 up-to-date，但如果后续提交代码，仍应按 `AGENTS.md` 要求在提交前运行 `gitnexus_detect_changes()` 或 CLI `npx gitnexus detect-changes`。
4. 本次任务未修改业务符号，因此不涉及符号级 impact analysis；仅新增文档。

## 7. 更新后的建议

1. 将“GitNexus MCP 占用 lbug 导致 analyze 失败”记录到项目维护手册：分析前如遇 `Access is denied`，先检查并停止旧 `gitnexus mcp` 进程。
2. 在 CI 或本地脚本中加入 `npx gitnexus status`，把 stale index 作为架构分析前置检查。
3. 继续推进上一版报告建议：按 Core Product、Commerce、AI Lab、Infrastructure 分层标记 API 稳定性。
4. 对 `Api_decide`、V4 optimize/decide、Goal-Driven generate、commercial report 这几条跨社区流程做专门的契约测试，因为它们在新图谱中仍是高耦合流程。
5. 对 Expert AI 保持“实验平台”隔离，避免未稳定的训练/图谱/外部存储能力直接阻塞核心玩家路径。

## 8. 总结

GitNexus 索引权限问题已修复，索引已从 `ffe0dc1` 更新到 `edb6fc7`，图谱规模从 14701 symbols / 26880 relationships / 520 communities 增长到 15430 nodes / 28143 edges / 541 clusters。新图谱没有推翻上一版架构判断，而是增强了两个观察：账号概览和估值链路关系更明确，V4/决策类 API 在跨社区流程中更突出。

因此，当前最可靠的架构结论仍是：这是一个核心玩家功能较成熟、商业化与智能平台并行扩展的宽功能 FastAPI 单体。后续重点不在“发现缺失架构”，而在收敛边界、分层测试、稳定核心 API，并把实验性 AI 子系统和生产路径保持清晰隔离。
