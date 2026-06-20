# GW2 Progression — 实现汇总与成熟度评估

> 基于 GitNexus 代码图谱 & 语义图谱分析
> Index: 371 nodes | 570 edges | 11 clusters | 21 flows

---

## 1. 项目总览

| 维度 | 值 |
|---|---|
| **项目名称** | gw2-progression |
| **技术栈** | Python 3.12 / FastAPI / httpx / Pydantic v2 / Vanilla JS |
| **代码规模** | 6 模块, 10 个前端 tab, 22 个 GW2 API 端点 |
| **测试** | 18 tests (13 unit + 5 integration), 0.84s |
| **CI** | ruff lint + pytest (3.12/3.13 matrix) |
| **部署** | Docker (python:3.12-slim) + docker-compose |
| **代码图谱** | 371 节点, 570 边, 11 集群, 21 流程 |
| **语义图谱** | 2 实体, 32 属性, 8 SHACL 规则 |

---

## 2. GitNexus 代码图谱

### 2.1 模块依赖图

```
                       ┌──────────────┐
                       │  index.html  │  ← Vanilla SPA, 10 tabs
                       │  (JS SPA)    │     resolve*() → public GW2 API
                       └──────┬───────┘
                              │ fetch POST /analyze
                              ▼
                    ┌─────────────────┐
                    │  api/main.py    │  ← FastAPI app, lifespan shutdown
                    └────────┬────────┘
                             │ include_router
                             ▼
                   ┌──────────────────┐
                   │ routes/analyze.py│  ← POST /analyze, key validation
                   └────────┬─────────┘
                            │ fetch_all()
                            ▼
                   ┌──────────────────┐
                   │   analyzer.py    │  ← AccountContents (Pydantic model)
                   │   fetch_all()    │     _safe() error isolation
                   │   section()      │     asyncio.gather 并行 22 端点
                   └────────┬─────────┘
                            │ 22× _safe(fetch_*)
                            ▼
                   ┌──────────────────┐
                   │  gw2_client.py   │  ← _get() + retry 5xx(3x)
                   │  _get_client()   │     AsyncClient 单例
                   │  _close_client() │     Gw2ApiError
                   └────────┬─────────┘
                            │ httpx → api.guildwars2.com
                            ▼
                   ┌──────────────────┐
                   │    cache.py      │  ← TTLCache / @cached
                   └──────────────────┘
```

### 2.2 调用关系 (GitNexus: 570 edges)

```
post_analyze ──calls──▶ fetch_all
fetch_all ────calls────▶ fetch_tokeninfo     (gate: 401 → abort)
fetch_all ────calls────▶ fetch_account       (gate: guild_ids + wvw)
fetch_all ────gather────▶ fetch_characters
                         fetch_wallet
                         fetch_bank
                         fetch_materials
                         fetch_inventory
                         fetch_achievements
                         fetch_masteries
                         fetch_mastery_points
                         fetch_builds
                         fetch_guilds(guild_ids)
                         fetch_pvp_stats
                         fetch_pvp_games
                         fetch_pvp_standings
                         fetch_tradingpost_buys
                         fetch_tradingpost_sells
                         fetch_unlocked_skins
                         fetch_unlocked_dyes
                         fetch_unlocked_minis
                         fetch_unlocked_finishers
                         fetch_wvw_stats(wvw_team, rank)

22× fetch_* ──calls────▶ _get(path, api_key)
_get ────────calls──────▶ _get_client()  →  httpx.AsyncClient
_get ────────retry──────▶ 5xx: sleep(1s/2s/4s), max 3

_safe ───────catches────▶ Gw2ApiError + Exception → errors dict
AccountContents ◀──has── 32 properties (fields)
AnalyzeRequest ◀──has── 1 property (api_key)
```

### 2.3 执行流程 (GitNexus: 21 flows)

| 流程 | 步骤 | 类型 |
|---|---|---|
| `POST /analyze → _get_client` | 5 | cross_community |
| `POST /analyze → _safe` | 4 | intra_community |
| `fetch_account → _get_client` | 3 | intra_community |
| `fetch_characters → _get_client` | 3 | cross_community |
| `fetch_bank → _get_client` | 3 | cross_community |
| `fetch_inventory → _get_client` | 3 | cross_community |
| `fetch_pvp_stats → _get_client` | 3 | cross_community |
| `fetch_pvp_standings → _get_client` | 3 | cross_community |
| ... (14 more fetch_* → _get_client flows) | 3 | - |

---

## 3. 语义图谱分析

### 3.1 三轴抽象法

```
轴         计数    代表实体
──────────────────────────────────
State      11     PermissionAccount..PermissionWvw (API scopes)
Entity     2      AccountContents, AnalyzeRequest
Constraint 1      Gw2ApiError
SHACL      8      约束规则 (Critical: 2, Warning: 3, Info: 3)
```

### 3.2 核心实体: AccountContents (32 属性)

```
AccountContents
├── identity (9): token_name, account_name, account_world,
│                 account_created, account_age_hours, fractal_level,
│                 daily_ap, monthly_ap, wvw_rank
├── per-section (22): characters, wallet, bank, materials,
│                     shared_inventory, achievements, masteries,
│                     mastery_points, builds, guilds, pvp_stats,
│                     pvp_games, pvp_standings, tradingpost_buys,
│                     tradingpost_sells, unlocked_skins, unlocked_dyes,
│                     unlocked_minis, unlocked_finishers, wvw
└── error (1): errors
```

### 3.3 SHACL 约束规则

| 规则 | 严重度 | 逻辑 |
|---|---|---|
| `AuthValidation` | 🔴 Critical | tokeninfo必须在任何fetch前验证 |
| `PermissionGuard` | 🔴 Critical | 每数据段按API scope门控 |
| `SafeCallWrapper` | 🟡 Warning | _safe()隔离异常到errors dict |
| `ApiKeyFormatValidation` | 🟡 Warning | hex+dashes格式+≥8长度校验 |
| `TestClientMissing` | 🟡 Warning | 路由层E2E测试覆盖 |
| `AsyncClientReuse` | 🔵 Info | 单例AsyncClient复用连接池 |
| `CacheNotIntegrated` | 🔵 Info | TTLCache未接入fetch链 |
| `UnlocksSerialInsideGather` | 🔵 Info | unlock子端点已在gather内并行(已修复) |

---

## 4. 功能实现清单

### 4.1 数据获取 (22 GW2 API 端点)

| # | 端点 | 功能 | 状态 |
|---|---|---|---|
| 1 | `/v2/tokeninfo` | API key 验证 + 权限发现 | ✅ |
| 2 | `/v2/account` | 账号基础信息 | ✅ |
| 3 | `/v2/characters` | 角色装备 + 属性 | ✅ |
| 4 | `/v2/account/wallet` | 钱包货币 | ✅ |
| 5 | `/v2/account/bank` | 银行物品 | ✅ |
| 6 | `/v2/account/materials` | 材料库存 | ✅ |
| 7 | `/v2/account/inventory` | 共享背包 | ✅ |
| 8 | `/v2/account/achievements` | 成就进度 | ✅ |
| 9 | `/v2/account/masteries` | 精通信息 | ✅ |
| 10 | `/v2/account/mastery/points` | 精通点数 | ✅ |
| 11 | `/v2/account/buildstorage` | 装备模板 | ✅ |
| 12 | `/v2/guild?id=` | 公会详情 | ✅ |
| 13 | `/v2/pvp/stats` | PvP 统计 | ✅ |
| 14 | `/v2/pvp/games` | PvP 最近比赛 | ✅ |
| 15 | `/v2/pvp/standings` | PvP 天梯 | ✅ |
| 16 | `/v2/commerce/transactions/current/buys` | 买入订单 | ✅ |
| 17 | `/v2/commerce/transactions/current/sells` | 卖出订单 | ✅ |
| 18 | `/v2/account/skins` | 解锁皮肤 | ✅ |
| 19 | `/v2/account/dyes` | 解锁染料 | ✅ |
| 20 | `/v2/account/minis` | 解锁迷你 | ✅ |
| 21 | `/v2/account/finishers` | 解锁终结技 | ✅ |
| 22 | `/v2/account`(派生) | WvW 信息 | ✅ |

### 4.2 前端可视化 (10 Tabs)

| Tab | 可视化内容 | 交互 | 状态 |
|---|---|---|---|
| **Overview** | 10 统计卡片 + 权限徽章 + 错误展示 | 静态展示 | ✅ |
| **Characters** | 纸娃娃 + 武器切换 + 饰品 + 公会徽章 + 装备列表 | 角色切换 | ✅ |
| **Wardrobe** | 皮肤网格 + 名称搜索 + 类型/子类型过滤 + 分页(200/批) | 搜索/分页 | ✅ |
| **Wallet** | 货币排序列表 + 金币格式 `Xg Xs Xc` | 静态排序 | ✅ |
| **Inventory** | 材料 Top40 + 银行槽位 + 共享背包物品网格 | 静态展示 | ✅ |
| **Progression** | 精通表 + 点数卡 + 成就计数 | 静态展示 | ✅ |
| **PvP** | 统计网格 + 最近比赛表 + 天梯分段表 | 静态展示 | ✅ |
| **Unlocks** | 解锁计数 + Finisher 永久/数量表 | 静态展示 | ✅ |
| **Builds** | 装备模板物品预览 + 技能模板ID | 静态展示 | ✅ |
| **WvW** | WvW Rank + Team | 静态展示 | ✅ |

### 4.3 基础设施

| 功能 | 实现 | 状态 |
|---|---|---|
| 异步并发 | `asyncio.gather` 并行 22 端点 | ✅ |
| 权限门控 | 仅获取已授权 scope | ✅ |
| 错误隔离 | `_safe()` → errors dict, 不阻塞 | ✅ |
| 连接池复用 | 单例 `AsyncClient` | ✅ |
| 请求重试 | 5xx 3 次 (1s/2s/4s) | ✅ |
| 超时保护 | 30s timeout | ✅ |
| API key 格式校验 | hex+dashes regex + ≥8 长度 | ✅ |
| 请求取消防竞态 | AbortController | ✅ |
| 进程内缓存 | `TTLCache` + `@cached` 装饰器 | ✅ |
| 逐 tab 错误展示 | `ERR_TAB_MAP` 路由到对应 tab | ✅ |
| 逐 tab 加载态 | `.tab-loading` spinner | ✅ |
| CI 流水线 | ruff lint + pytest (3.12/3.13) | ✅ |
| Docker 部署 | Dockerfile + docker-compose.yml | ✅ |
| 空 key 反馈 | 红色提示消息 | ✅ |
| Wardrobe 防抖 | 200ms debounce | ✅ |
| Wardrobe 空结果 | 占位提示 | ✅ |

---

## 5. 成熟度评估

### 5.1 评级标准

| 等级 | 含义 | 标准 |
|---|---|---|
| **S** | 生产就绪 | 全覆盖测试, 文档完整, 监控/告警, 性能优化 |
| **A** | 功能完整 | 核心功能齐备, 测试覆盖 > 80%, 主要边界处理 |
| **B** | 可用 | 主要功能可用, 有测试, 有错误处理 |
| **C** | 原型 | 基础功能, 测试不足, 边界未处理 |
| **D** | 概念验证 | 仅核心链路, 无测试 |

### 5.2 逐维度评分

#### 后端 (Backend)

| 维度 | 评分 | 依据 |
|---|---|---|
| **API 设计** | **A** | RESTful POST /analyze, Pydantic 响应模型, 自动 OpenAPI |
| **数据获取** | **A** | 22 端点全覆盖, async 并发, 权限门控, 超时+重试 |
| **错误处理** | **A** | `_safe` 隔离, errors dict, 401/422/500 分层处理 |
| **安全** | **B+** | key 格式校验, 无存储, 无 CORS 配置 (本地工具可接受) |
| **测试** | **B+** | 18 tests, analyzer + routes + cache, 无 E2E 测试 |

#### 前端 (Frontend)

| 维度 | 评分 | 依据 |
|---|---|---|
| **信息密度** | **A** | 10 tab 覆盖 GW2 账号全数据域 |
| **交互性** | **B** | 角色切换/搜索/分页, 整体偏静态展示 |
| **错误展示** | **A** | 逐 tab 错误路由 + known limitations 说明 |
| **性能** | **B** | 懒加载(wardrobe), 分片, 防抖, 但全部数据一次传输 |
| **响应式** | **B** | CSS grid 布局, 桌面优先, 移动端可读但未优化 |
| **可维护性** | **C** | 单 HTML 文件 ~1000 行, 无框架, 无组件化 |

#### 架构 (Architecture)

| 维度 | 评分 | 依据 |
|---|---|---|
| **模块化** | **B+** | 清晰的 6 模块分层, 但有循环依赖隐患 |
| **异步** | **A** | 全异步链路, gather 并行, AsyncClient 复用 |
| **缓存** | **C** | cache.py 独立但未集成, 前端缓存无 TTL |
| **可扩展性** | **B** | 添加新端点 = 3 步: fetch_* + section + render |
| **部署** | **A** | Docker 构建, 单容器可部署 |

### 5.3 综合成熟度: **B+ (可用→功能完整)**

```
后端:      A-    ████████████░░   85%
前端:      B+    ██████████░░░░   78%
架构:      B+    █████████░░░░░   75%
测试:      B+    ██████████░░░░   78%
────────────────────────────────
综合:      B+    ██████████░░░░   79%
```

### 5.4 提升至 A 级的路径

| 改进项 | 当前状态 | 目标 | 工作量 |
|---|---|---|---|
| `cache.py` 集成到 fetch 链 | C → A | 后端缓存 resolution 数据 | ~2h |
| E2E 测试 (Playwright/Cypress) | 无 → A | UI 自动化测试覆盖 10 个 tab | ~4h |
| 前端组件化拆分 | C → A | 多文件, 构建工具(Vite) | ~4h |
| 后端 resolution 代理 | 无 → A | 替代前端直接调 public GW2 API | ~3h |
| 前端缓存 TTL + maxsize | 无 → B | 控制 session 缓存增长 | ~1h |
| Streaming 渐进加载 | 暂停 → B | SSE 逐 section 推送 | ~4h |

---

## 6. GitNexus 代码图谱指标

| 指标 | 值 |
|---|---|
| **Nodes** | 371 |
| **Edges** | 570 |
| **Clusters** | 11 |
| **Processes** | 21 |
| **Cross-Community Flows** | 12 |
| **Intra-Community Flows** | 9 |
| **Top Functions** | `fetch_all` (22 outgoing calls), `_get` (22 incoming calls) |

### 核心社区 (Clusters)

| Cluster | 主要符号 |
|---|---|
| **analyzer** | `fetch_all`, `AccountContents`, `_safe`, `section` |
| **gw2_client** | `_get`, `_get_client`, `_close_client`, `Gw2ApiError`, 22× `fetch_*` |
| **routes** | `post_analyze`, `AnalyzeRequest` |
| **api_main** | `app`, `lifespan`, `health`, `index` |
| **cache** | `TTLCache`, `get_cache`, `cached` |
| **test_analyzer** | 7 tests |
| **test_cache** | 6 tests |
| **test_routes** | 5 tests |
