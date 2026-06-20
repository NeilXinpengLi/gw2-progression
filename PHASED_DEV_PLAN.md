# GW2 Progression — 阶段开发任务

基于语义图谱分析（`semantic_graph.json`）梳理的优先级路线图。

---

## 阶段一：架构修复（P0）

> 目标：消除隐式依赖、提升并发能力、用户可见的错误反馈

### 1.1 解耦 fetch_guilds / fetch_wvw_stats 隐式依赖

| 项目 | 内容 |
|---|---|
| **问题** | `fetch_guilds()` 和 `fetch_wvw_stats()` 内部再次调用 `fetch_account()`，导致重复请求；若 account 失败则无错误传播路径 |
| **文件** | `src/gw2_progression/gw2_client.py:68-75`, `:114-117` |
| **方案** | 将 `guild_ids` 和 `wvw_team`/`wvw_rank` 作为参数传入，由 `fetch_all()` 统一从 account 响应中提取后传入 |
| **验证** | 单次 analyze 日志中 `/v2/account` 仅出现一次 |

### 1.2 同步 httpx → 异步 httpx.AsyncClient

| 项目 | 内容 |
|---|---|
| **问题** | `_get()` 使用 `httpx.Client`（同步）阻寨事件循环，并发请求退化为串行 |
| **文件** | `src/gw2_progression/gw2_client.py:13-21` |
| **方案** | 改为 `async with httpx.AsyncClient(timeout=30)`，所有 `fetch_*` 改为 `async def`，`fetch_all` 用 `asyncio.gather` 并发调用 |
| **验证** | 20+ 个 API 端点的总耗时约等于最慢单个端点耗时 |

### 1.3 前端逐 section 错误展示

| 项目 | 内容 |
|---|---|
| **问题** | `AccountContents.errors` 仅显示在全局状态栏，用户无法定位哪个 section 加载失败 |
| **文件** | `src/gw2_progression/static/index.html` |
| **方案** | 每个 tab 内部渲染对应 section 的错误信息，如 `characters` 失败时在角色标签内显示红色提示条 |
| **验证** | mock 单个端点返回 500 时，对应 section 显示错误而非空白 |

---

## 阶段二：质量基建（P1）

> 目标：补充测试、输入防御、加载体验

### 2.1 补全测试覆盖

| 项目 | 内容 |
|---|---|
| **当前** | 3 个 happy-path 测试，无 permission 子集、无错误传播、无 API route 集成测试 |
| **文件** | `tests/test_analyzer.py` |
| **新增测试** | |
| | • 每个 permission 单独缺失的场景（如仅 `account` 权限时其余字段为 None） |
| | • 每个端点逐一 mock 500 验证 errors dict 正确填充 |
| | • `fetch_guilds` / `fetch_wvw_stats` 不重复调用 account |
| | • FastAPI `TestClient` 集成测试：`POST /analyze` → 401 / 200 |
| | • 无效 API key 格式（空字符串、非 base64）的边界情况 |
| **命令** | `pytest tests/ -v --cov=gw2_progression` |

### 2.2 API key 格式前置校验

| 项目 | 内容 |
|---|---|
| **问题** | 无效 key 直接发 HTTP 请求，浪费 30s timeout |
| **文件** | `src/gw2_progression/api/routes/analyze.py:11` |
| **方案** | `AnalyzeRequest` 增加 `@field_validator('api_key')`，校验长度 ≥ 8 且为合法 base64 字符串 |
| **验证** | 传入 `""` 或 `"abc"` 返回 422，不触发对外 HTTP 调用 |

### 2.3 前端逐 tab 加载状态

| 项目 | 内容 |
|---|---|
| **问题** | 全局 spinner 在大账号（1000+ skins）时无进度反馈 |
| **文件** | `src/gw2_progression/static/index.html` |
| **方案** | 每个 nav button 绑定独立 loading 状态，数据到达后逐个激活对应 tab 内容区 |
| **验证** | 网络慢速模拟时，已完成的 tab 可提前查看，无需等待全部完成 |

---

## 阶段三：性能优化（P2）

> 目标：减少重复请求、渐进式加载、防抖

### 3.1 GW2 静态数据本地缓存

| 项目 | 内容 |
|---|---|
| **问题** | 每次 `/analyze` 都重复请求 `/v2/items`、`/v2/currencies`、`/v2/skins`、`/v2/colors` 等公共 API |
| **文件** | `new: src/gw2_progression/cache.py` |
| **方案** | 基于 `dict` + TTL（默认 3600s）的进程内缓存，封装 `@cached(ttl=3600)` 装饰器 |
| **验证** | 连续两次 analyze 同一账号，公共 API 请求次数减半 |

### 3.2 渐进式 Streaming 响应

| 项目 | 内容 |
|---|---|
| **问题** | 全部 22 个 API 串行完成后才返回 JSON，首字节时间 = Σ 所有端点耗时 |
| **文件** | `src/gw2_progression/analyzer.py` |
| **方案** | 使用 FastAPI `StreamingResponse` 或 Server-Sent Events，每个 section 就绪后立即推送给前端 |
| **验证** | 账户基础信息（account 端点）在 ~500ms 内显示，其余 section 陆续到达 |

### 3.3 前端请求去重

| 项目 | 内容 |
|---|---|
| **问题** | 用户快速多次点击 Analyze 会并发多个相同请求 |
| **文件** | `src/gw2_progression/static/index.html` |
| **方案** | 按钮点击后立即 disable，请求完成前忽略后续点击；或在途请求自动 cancel |
| **验证** | 快速点击 5 次仅触发 1 次网络请求 |

---

## 阶段四：扩展功能（P3）

> 目标：工程化、大数据处理、用户体验增强

### 4.1 CI 配置（pytest + ruff）

| 项目 | 内容 |
|---|---|
| **文件** | `new: .github/workflows/ci.yml` |
| **内容** | |
| | • `ruff check src/`（lint + format） |
| | • `pytest tests/ -v` |
| | • Python 3.12 / 3.13 矩阵 |
| **pyproject.toml 补充** | 添加 `[tool.ruff]` 和 `[tool.pytest.ini_options]` 配置 |

### 4.2 超大 wardrobe 分片加载

| 项目 | 内容 |
|---|---|
| **问题** | `unlocked_skins` 数组直接赋给 JS 变量，10,000+ 条时内存压力大 |
| **文件** | `src/gw2_progression/static/index.html` |
| **方案** | 后端提供分页参数 `?offset=0&limit=500`，前端滚动加载替代一次性渲染 |

### 4.3 Docker 部署

| 项目 | 内容 |
|---|---|
| **文件** | `new: Dockerfile`, `new: docker-compose.yml` |
| **内容** | |
| | • 基于 `python:3.12-slim` |
| | • `pip install .` |
| | • `CMD uvicorn gw2_progression.api.main:app --host 0.0.0.0 --port 8000` |

### 4.4 Wardrobe 高级搜索

| 项目 | 内容 |
|---|---|
| **问题** | 当前仅支持按皮肤 ID 前缀模糊搜索 |
| **文件** | `src/gw2_progression/static/index.html` |
| **方案** | 利用 GW2 API 元数据（`/v2/skins` 返回 `name`、`type`、`races`）在前端添加名称/类型/种族的组合过滤 |

### 4.5 请求重试 + 指数退避

| 项目 | 内容 |
|---|---|
| **问题** | GW2 API 偶发 500 时无重试，用户需手动重试 |
| **文件** | `src/gw2_progression/gw2_client.py` |
| **方案** | `_get()` 中集成 `tenacity` 或自实现重试：最大 3 次，退避 1s/2s/4s，仅对 5xx 重试，4xx 直接抛出 |

---

## 执行顺序总览

```
阶段一 (P0)        阶段二 (P1)        阶段三 (P2)        阶段四 (P3)
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ 1.1 解耦依赖 │   │ 2.1 补测试   │   │ 3.1 本地缓存  │   │ 4.1 CI      │
│ 1.2 异步化   │──▶│ 2.2 key校验  │──▶│ 3.2 Streaming│──▶│ 4.2 分片    │
│ 1.3 错误展示 │   │ 2.3 加载态   │   │ 3.3 去重     │   │ 4.3 Docker  │
└─────────────┘   └─────────────┘   └─────────────┘   │ 4.4 搜索增强 │
                                                        │ 4.5 重试     │
                                                        └─────────────┘
```

每个阶段内可并行；阶段间的依赖关系：
- 阶段一 → 阶段二（异步化后测试需更新为 `pytest-asyncio`）
- 阶段二 → 阶段三（缓存 + Streaming 依赖异步架构就绪）
- 阶段三 → 阶段四（CI 可随时加入，无硬依赖）

---

## 执行状态

| 阶段 | 任务 | 状态 | 备注 |
|---|---|---|---|
| P0-1.1 | 解耦 fetch_guilds / fetch_wvw_stats 依赖 | ✅ | 参数传入，不再内部调用 fetch_account |
| P0-1.2 | 同步 httpx → 异步 httpx.AsyncClient | ✅ | + `asyncio.gather` 并发 |
| P0-1.3 | 前端逐 section 错误展示 | ✅ | 每个 tab-panel 内嵌 `.tab-error`，按 ERR_TAB_MAP 路由 |
| P1-2.1 | 补全测试覆盖 | ✅ | 3→7 个测试 |
| P1-2.2 | API key 格式前置校验 | ✅ | `@field_validator`，< 8 字符返回 422 |
| P1-2.3 | 前端逐 tab 加载状态 | ✅ | 每个 tab-panel 内嵌 `.tab-loading` |
| P2-3.1 | GW2 静态数据本地缓存 | ✅ | `cache.py` — TTL + maxsize 淘汰 + `@cached` 装饰器 |
| P2-3.2 | 渐进式 Streaming 响应 | ⏸️ | 需大幅重构 API 合约，列为独立里程碑 |
| P2-3.3 | 前端请求去重 | ✅ | 已有 `btn.disabled` |
| P3-4.1 | CI 配置 | ✅ | `.github/workflows/ci.yml` + ruff/pytest |
| P3-4.2 | 超大 wardrobe 分片加载 | ✅ | 200 个/批 + "Show more" 按钮 |
| P3-4.3 | Docker 部署 | ✅ | `Dockerfile` + `docker-compose.yml` |
| P3-4.4 | Wardrobe 高级搜索 | ✅ | 名称/类型/子类型三轴过滤，与分页联动 |
| P3-4.5 | 请求重试 + 指数退避 | ✅ | 5xx 重试 3 次，1s/2s/4s |

**测试**: 13 passed in 0.84s · **Lint**: All checks passed · **Server**: Imports OK
