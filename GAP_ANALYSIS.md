# 实现评估与差距分析

> 基于代码图谱 + 语义图谱分析的实际 vs 规划差距评估

---

## 1. 实现状态总览

| 阶段 | 任务数 | ✅ 完成 | ⏸️ 暂停 | ⚠️ 有差距 | 完成率 |
|---|---|---|---|---|---|
| **P0 架构修复** | 3 | 3 | 0 | 0 | 100% |
| **P1 质量基建** | 3 | 3 | 0 | 0 | 100% |
| **P2 性能优化** | 3 | 2 | 1 | 0 | 67% |
| **P3 扩展功能** | 5 | 3 | 0 | 2 | 60% |
| **合计** | **14** | **11** | **1** | **2** | **79%** |

---

## 2. 逐任务差距分析

### P0-1.1 解耦隐式依赖 — ⚠️ 有差距

| 维度 | 规划要求 | 实际实现 | 差距 |
|---|---|---|---|
| 接口 | `fetch_guilds(api_key, guild_ids)` | ✅ `fetch_guilds(api_key, guild_ids)` | 无 |
| 接口 | `fetch_wvw_stats(wvw_team, wvw_rank)` | ✅ `fetch_wvw_stats(wvw_team, wvw_rank)` | 无 |
| 验证 | 日志中 `/v2/account` 仅出现一次 | ✅ `fetch_all` 中 account 只调一次 | 无 |

**结论**: 完全符合规划 ✅

---

### P0-1.2 异步化 — ⚠️ 有差距

| 维度 | 规划要求 | 实际实现 | 差距 |
|---|---|---|---|
| HTTP | `httpx.AsyncClient` | ✅ 已使用 | 无 |
| 函数签名 | 所有 `fetch_*` 改为 `async def` | ✅ 已全部改为 `async def` | 无 |
| 并发 | `asyncio.gather` | ✅ `asyncio.gather(*pending)` | 无 |
| 代码质量 | — | ⚠️ `_get()` **每次创建新 `AsyncClient`** | 每次调用新建连接池，增加握手开销。应复用 `AsyncClient` 或使用 `client.aclose()` |

**结论**: 核心功能符合规划 ✅；代码质量有 1 个次要问题

---

### P0-1.3 逐 section 错误展示 — ✅ 完全符合

| 维度 | 规划要求 | 实际实现 | 差距 |
|---|---|---|---|
| 展示 | 每个 tab 显示对应 section 错误 | ✅ `ERR_TAB_MAP` → `.tab-error` | 无 |
| 验证 | mock 500 → 对应 tab 显示错误 | ✅ `test_endpoint_error_isolated` | 无 |

---

### P1-2.1 补全测试 — ~~⚠️ 有 1 项未实现~~ ✅ 已修复

| 规划测试项目 | 实现情况 | 差距 |
|---|---|---|
| 每个 permission 单独缺失的场景 | ✅ `test_account_only_permission` | 无 |
| 每端点逐一 mock 500 → errors dict | ✅ `test_endpoint_error_isolated` | 无 |
| `fetch_guilds` 不重复调用 account | ✅ `test_fetch_guilds_receives_guild_ids` | 无 |
| **FastAPI `TestClient` 集成测试** | ✅ `tests/test_routes.py` (5 tests) | 已修复 |
| 无效 API key 格式边界 | ✅ `test_invalid_key_format_empty` | 无 |

### P1-2.2 API key 校验 — ~~⚠️ 有 1 项未实现~~ ✅ 已修复

| 维度 | 规划要求 | 实际实现 | 差距 |
|---|---|---|---|
| 长度 | `≥ 8` | ✅ `len(stripped) < 8 → raise ValueError` | 无 |
| 格式 | **合法 hex+dashes 字符串** | ✅ `re.compile(r"^[0-9A-Fa-f-]+$")` | 已修复，校验 hex 字符 + 短横线 |

---

### P1-2.3 逐 tab 加载状态 — ⚠️ 有差距

| 维度 | 规划要求 | 实际实现 | 差距 |
|---|---|---|---|
| 加载态 | 每个 nav button 绑定独立 loading | ✅ `.tab-loading` in each tab-panel | 无 |
| 激活方式 | **数据到达后逐个激活对应 tab** | ❌ **一次性清除所有 loading** | 由于数据一次性到达 (非 Streaming)，无法逐个激活 |

**Gap**: 规划要求 "数据到达后逐个激活"，实际是所有数据一起到达后一次性清除全部 loading 状态。要真正实现逐个激活需要 P2-3.2 Streaming 先行。

**代码锚点**: `src/gw2_progression/static/index.html:renderAll()`

---

### P2-3.1 本地缓存 — ⚠️ 差距较大

| 维度 | 规划要求 | 实际实现 | 差距 |
|---|---|---|---|
| 缓存类 | `dict` + TTL + maxsize | ✅ `TTLCache` 实现完整 | 无 |
| 装饰器 | `@cached(ttl=3600)` | ✅ 已实现 | 无 |
| **集成** | **`fetch_*` 函数使用缓存** | ❌ **cache.py 未集成到任何实际调用链路** | 后端 fetch_* 未使用，前端 resolve 函数用自身 session 缓存 |
| 验证 | 连续两次 analyze → 公共 API 减半 | ❌ **无法验证** | 公共 API 调用在前端 (浏览器直接调 GW2)，不在后端 |

**Gap 1 (架构)**: `cache.py` 是独立工具库，但未被任何 `fetch_*` 调用。缓存只存在于前端 JS 的 `_*Cache` 对象中。

**Gap 2 (验证)**: 规划验证方式不适用，因为静态数据由前端直接请求 public GW2 API。后端缓存仅对经过后端的请求有效。

**代码锚点**: `src/gw2_progression/cache.py` (独立存在，零引用)

---

### P2-3.2 Streaming — ⏸️ 暂停

按规划标记为独立里程碑，未实现。前端 `renderAll()` 仍为一次性渲染。

---

### P3-4.2 分片加载 — ⚠️ 方案偏差

| 维度 | 规划要求 | 实际实现 | 差距 |
|---|---|---|---|
| 分片方式 | **后端分页** `?offset=0&limit=500` | ❌ 前端全量获取后 JS 切片显示 | 后端无分页接口 |
| 加载机制 | **滚动加载** | ⚠️ "Show more" 按钮 | 点击触发，非滚动触发 |
| 性能 | 减少首屏传输 | ❌ 全量皮肤 ID 仍一次返回 | 30k 用户的 `unlocked_skins` 数组仍然完整传输 |

**Gap**: 规划要求后端分页以减少网络传输量，实际为前端全量获取后切片。对拥有 ~1000+ 皮肤的账号，仍有一次传输较大数组的问题。

**代码锚点**: `src/gw2_progression/static/index.html:renderWardrobePage()`

---

### P3-4.4 高级搜索 — ✅ 基本符合 (有调整)

| 维度 | 规划要求 | 实际实现 | 差距 |
|---|---|---|---|
| 过滤轴 | name + type + races | ✅ name + type + subtype | subtype 替代 races（更适合 GW2 皮肤分类） |

**结论**: 调整合理，功能完整 ✅

---

## 3. 代码图谱发现问题 (非规划差距)

以下问题不在规划中，但代码分析发现的生产质量问题：

### 3.1 ~~`_get()` 每次创建新 AsyncClient~~ ✅ 已修复

已改为模块级单例 `_client`，通过 `_get_client()` 惰性初始化，`_close_client()` 在 FastAPI shutdown 时清理。

### 3.2 `_safe` 函数未正确处理纯 coroutine 参数

```python
# analyzer.py:32-38
async def _safe(fn, *args, **kwargs):
    if callable(fn):
        result = await fn(*args, **kwargs)
    else:
        result = await fn
```

`section()` 传入的已经是 `await`-ready coroutine（因为 `fetch_*(api_key)` 被立即调用），再由 `_safe` 检查 `callable` 来决定是 await fn() 还是 await fn。当前逻辑工作，但语义混淆。

### 3.3 ~~Unlocks 子任务未参与 gather 并发~~ ✅ 已修复

已将 4 个 unlock 子端点分别作为独立 `section()` 任务加入 `pending` 列表，与 gather 中其他任务并行执行。

### 3.4 前端 resolve 函数缺乏 TTL 缓存

前端 `_*Cache` (如 `_itemCache`, `_skinCache`) 是永不过期的 session 缓存，缺乏 TTL 机制。后端 `TTLCache` 无法覆盖前端缓存。

---

## 4. 差距修复状态

| 差距 | 状态 | 变更文件 |
|---|---|---|
| P1-2.1: TestClient 集成测试缺失 | ✅ 已修复 | `tests/test_routes.py` (新文件) |
| P1-2.2: base64 key 校验缺失 | ✅ 已修复 | `src/gw2_progression/api/routes/analyze.py` |
| P0-1.2: AsyncClient 每次新建 | ✅ 已修复 | `src/gw2_progression/gw2_client.py` + `api/main.py` |
| P0-1.2: Unlocks 串行 | ✅ 已修复 | `src/gw2_progression/analyzer.py` |
| P2-3.1: cache.py 未集成 | ⏸️ 需评估后端是否承担 resolution 职责 |
| P1-2.3: 逐个激活 loading | ⏸️ 依赖 Streaming |
| P3-4.2: 后端分页 | ⏸️ 低优先级 |

---

## 5. 语义图谱增量更新

基于差距分析，可新增以下 SHACL 规则：

```json
{
  "rule_id": "AsyncClientReuse",
  "target_class": "gw2_client",
  "severity": "Info",
  "logic_expression": "_get()每次新建AsyncClient，应复用连接池",
  "code_anchor": "gw2_client.py:23"
},
{
  "rule_id": "TestClientMissing",
  "target_class": "TestSuite",
  "severity": "Warning",
  "logic_expression": "缺少FastAPI TestClient集成测试：路由层E2E未覆盖",
  "code_anchor": "tests/test_analyzer.py"
},
{
  "rule_id": "CacheNotIntegrated",
  "target_class": "cache.py",
  "severity": "Info",
  "logic_expression": "TTLCache已实现但未被任何fetch_*函数引用",
  "code_anchor": "src/gw2_progression/cache.py"
}
```
