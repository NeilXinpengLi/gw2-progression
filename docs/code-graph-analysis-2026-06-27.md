# GW2 Progression OS — 代码图谱与语义图谱分析

> 分析日期：2026-06-27  
> 分析范围：Landing / Account / Insight / Plan / Report 五页面 + 前后端全链路

---

## 一、总体架构图

```
┌─────────────────────────────────────────────────────────┐
│                   浏览器 (5 页面)                         │
│  Landing → Account → Insight → Plan → Report            │
│  session-manager.js (统一 Session)                       │
│  SVG icons.svg (44 符号内联)                             │
└────────────┬───────────────────────────────┬────────────┘
             │ HTTP                          │ Static Files
             ▼                               ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI (main.py)                                      │
│  Middleware: logging / security / rate-limit / session   │
│  Routes: /auth/* /api/account/* /api/insight/* /api/v1/* │
└────────────┬───────────────────────────────┬────────────┘
             │ Services                      │ DB
             ▼                               ▼
┌──────────────────────┐   ┌──────────────────────────────┐
│  auth_service        │   │  SQLite (aiosqlite)           │
│  snapshot_service    │   │  ├─ account_sessions          │
│  holdings_service    │   │  ├─ account_snapshots         │
│  price_service       │   │  ├─ item_holdings             │
│  event_bus           │   │  ├─ snapshot_registry         │
│  production_engine   │   │  └─ audit_log                 │
│  v4_economic_model   │   │                                │
│  ontology/*          │   │                                │
└──────────────────────┘   └──────────────────────────────┘
```

---

## 二、逐页分析

### 🟢 LANDING (`/`)

**前端文件**: `landing.html` + `style-landing.css`

**功能流程**:

```
用户访问 /
  ↓
Hero (价值展示 + 3 能力卡片)
  ↓
Value Proof (4 卡片：隐藏财富 / 构建 / 传奇 / 市场)
  ↓
Demo Snapshot (3,608g / 1,847g / 7/9 / 67%)
  ↓
How It Works (3 步骤时间线)
  ↓
Trust & Safety (4 条安全说明)
  ↓
Final CTA → [链接到 /account]
```

**完整度评估**: ✅ 95%

| 组件 | 状态 | 说明 |
|------|------|------|
| Hero 区域 | ✅ | 标题 + 副标题 + 3 pillars + 双 CTA 按钮 |
| Value Proof | ✅ | 4 卡片 grid，hover lift + 金边淡入动画 |
| Demo Snapshot | ✅ | 呼吸式 gold glow 动画边框 |
| How It Works | ✅ | 垂直时间线 + 数字 + 连接线 |
| Trust | ✅ | 4 条绿色 checkmark |
| Final CTA | ✅ | 脉冲光晕背景 + 双按钮 |
| 响应式 | ✅ | 3 个断点 (800px/500px) |

**风险**: 低。Landing 是纯静态页面，无 API 依赖。

---

### 🟢 ACCOUNT (`/account`)

**前端文件**: `account.html` + `app-account.v2.js` + `style-account.css`  
**后端文件**: `api/routes/account.py`

**功能流程**:

```
用户访问 /account
  ↓
session-manager.initSession() → 读取 localStorage
  ├─ 有 session → /auth/session/validate → 有效 → runAnalyze()
  └─ 无 session → 显示 Key 输入框
       ↓ 用户输入 Key + 点击 Analyze
  runAnalyze():
    1. createSession() → POST /auth/session
    2. GET /api/account/overview?api_key=<token>
    3. POST /analyze
    4. renderDashboard(data)
```

**后端 API 流程**:

```
GET /api/account/overview?api_key=xxx
  ↓
get_api_key() → 解析 token → 真实 Key
  ↓
fetch_all() → GW2 API 拉取原始数据
  ↓
normalize_account() → Layer 1→2 转换
  ↓
fetch_prices() → 注入市场价格
  ↓
derive_value() + derive_breakdown() → Layer 2→3
  ↓
返回 {account, kpis, assets, characters}
```

**完整度评估**: ✅ 90%

| 组件 | 状态 | 说明 |
|------|------|------|
| Session 创建 | ✅ | 含 validate 检查 |
| Key 输入 | ✅ | monospace 输入框 |
| KPI 卡片 (6) | ✅ | Value / Liquid Sell/Buy / Hidden / Legendary / Build |
| 趋势图 | ⚠️ | 使用随机数据，非真实快照历史 |
| 资产表 (7 类别) | ✅ | Wallet/Materials/Bank/Equipment/Char Inventory/Shared/TP |
| 角色表 | ✅ | 9 角色，含 profession/level/playtime/last_login |
| 状态面板 | ✅ | API 状态 / 新鲜度 / 权限 |
| 价格注入 | ✅ | 材料/银行/角色背包显示市价 |
| 错误处理 | ✅ | 401/500 均有 fallback |

**风险**:

| 风险 | 等级 | 说明 |
|------|------|------|
| 趋势图为随机数据 | 低 | 需要快照历史累积 |
| `fetch_all` 耗时 ~10s | 中 | GW2 API 多端点并发，用户体验可优化 |
| 角色装备价值估算 | 低 | 使用市场价格近似，非精确装备价值 |
| 无 Equipment 详细数据 | 低 | 仅显示装备数量，未显示具体装备名 |

---

### 🟡 INSIGHT (`/insight`)

**前端文件**: `insight.html` + `app-insight.v2.js` + `style-insight.css`  
**后端文件**: `api/routes/insight.py`

**功能流程**:

```
用户访问 /insight
  ↓
session-manager.initSession()
  ├─ 有 session → loadInsight(token)
  │   ↓
  │   GET /api/insight/data?api_key=<token>
  │   ↓
  │   渲染:
  │   ├─ Hidden Wealth 卡片 (unpriced 物品数)
  │   ├─ Build Readiness 卡片 (equipped/total chars)
  │   ├─ Legendary Progress 卡片 (占位)
  │   └─ Top Assets 列表 (按价值排序)
  └─ 无 session → 显示空状态
```

**后端 API 流程**:

```
GET /api/insight/data?api_key=xxx
  ↓
fetch_all() → 拉取原始数据
  ↓
extract_*_holdings() → 提取物品
  ↓
fetch_prices() → 注入价格
  ↓
计算:
  ├─ hidden_wealth: unpriced tradable items
  ├─ build_readiness: equipped chars / total chars
  ├─ top_items: 按 value_sell 排序
  └─ top_materials: 材料按价值排序
```

**完整度评估**: ⚠️ 65%

| 组件 | 状态 | 说明 |
|------|------|------|
| Hidden Wealth | ✅ | 正确显示 unpriced 物品数 |
| Build Readiness | ✅ | 装备角色数 / 总角色数 |
| Legendary Progress | ❌ | 占位数据 "—" |
| Top Assets | ✅ | 按价值排序显示 |
| Market Insight | ❌ | 未实现 |
| 导航跳转 | ✅ | 统一页面跳转 |

**风险**:

| 风险 | 等级 | 说明 |
|------|------|------|
| Legendary Progress 无数据 | 中 | 需要集成 goal_service |
| Market Insight 未实现 | 中 | 需要集成 listing_service |
| 无 goal tracking 集成 | 中 | ontology 中有 goal_mapper 但未接入 |
| 页面无自动刷新 | 低 | 用户需手动回到 Account 刷新数据 |

---

### 🔵 PLAN (`/plan`)

**前端文件**: `plan.html` + `app-plan.v2.js` + `style-plan.css`  
**后端文件**: `api/routes/production.py` + `services/production_engine.py` + `goal_driven.py`

**功能流程**:

```
用户访问 /plan
  ↓
session-manager.initSession()
  ↓
用户输入目标 或 选择快速目标
  ↓
generatePlan():
  1. POST /goal-driven/interpret (解析目标)
  2. 如有目标 → POST /goal-driven/generate
     无目标   → POST /api/v1/decide (策略驱动)
  ↓
渲染:
  ├─ P0/P1/P2 动作卡片
  ├─ 7天 Timeline
  ├─ Coach 推荐
  └─ Quest 列表
```

**后端 API 流程**:

```
POST /api/v1/decide { api_key, strategy }
  ↓
production_engine.decide()
  ↓
fetch_all() → 账号数据
  ↓
get_recommendations() → 构建推荐
  ↓
generate_explainable_actions() → v4 引擎评分
  ↓
返回 { p0, p1, p2, strategy_name, account_name }
```

**完整度评估**: ⚠️ 70%

| 组件 | 状态 | 说明 |
|------|------|------|
| 目标输入 | ✅ | 自由文本 + 快速目标 chips |
| 策略选择器 | ✅ | Balanced/Gold/Build/Legendary |
| P0/P1/P2 动作 | ⚠️ | decide API 返回 1 个动作，不够丰富 |
| 7天 Timeline | ⚠️ | 静态数据，未基于实际策略生成 |
| Coach 推荐 | ⚠️ | 需要 coach API 数据 |
| Quest 列表 | ⚠️ | 依赖 quest_service |
| Explanation Panel | ❌ | 未实现 |
| 策略切换 | ✅ | 切换后重新生成 plan |

**风险**:

| 风险 | 等级 | 说明 |
|------|------|------|
| decide API 返回动作少 | 中 | 数据不足时自动生成的 actions 有限 |
| Timeline 为静态 | 中 | 不基于实际策略 |
| Coach 无实际 AI 内容 | 中 | 需接入 LLM 或规则引擎 |
| Explanation Panel 缺失 | 低 | 用户看不到"为什么推荐这个" |

---

### 💰 REPORT (`/report`)

**前端文件**: `report.html` + `app-report.v2.js` + `style-report.css`

**功能流程**:

```
用户访问 /report
  ↓
session-manager.initSession()
  ├─ 有 session → loadReport(token)
  │   ↓
  │   GET /api/account/overview?api_key=<token>
  │   ↓
  │   显示免费预览:
  │   ├─ Account Name
  │   ├─ Total Value
  │   ├─ Characters
  │   └─ Build Ready
  │   ↓
  │   定价卡:
  │   ├─ Free (当前)
  │   ├─ Full Report ($5) — Stripe 占位
  │   └─ Weekly ($5/mo) — Stripe 占位
  │   ↓
  │   锁定内容预览 (blur)
  └─ 无 session → 显示空状态
```

**完整度评估**: ⚠️ 40%

| 组件 | 状态 | 说明 |
|------|------|------|
| 免费预览 | ✅ | 4 项基本数据 |
| 定价卡 | ✅ | 3 层定价 |
| Full Report 按钮 | ⚠️ | `alert()` 占位，无 Stripe |
| Subscribe 按钮 | ⚠️ | `alert()` 占位，无 Stripe |
| 锁定内容 | ✅ | blur + overlay 效果 |
| PDF 导出 | ❌ | 未实现 |
| 付费解锁逻辑 | ❌ | 无 Stripe webhook |
| 分享链接 | ❌ | 未实现 |

**风险**:

| 风险 | 等级 | 说明 |
|------|------|------|
| Stripe 未集成 | 高 | 无法真正收费 |
| PDF 导出未实现 | 中 | 报告核心功能缺失 |
| 无数据库持久化 | 中 | 报告内容不保存 |
| 定价策略未最终确定 | 低 | 价格可调整 |

---

## 三、跨页面数据流分析

### 3.1 Session 流

```
Landing (无 session)
  → click "Analyze" → /account
    → Account (输入 Key → createSession → token → localStorage)
      → 导航到 Insight
        → Insight (initSession → 读 localStorage → 有效 → 显示数据)
          → 导航到 Plan
            → Plan (initSession → 有效 → 可用)
              → 导航到 Report
                → Report (initSession → 有效 → 预览)
```

**问题**: 从 Landing → /account 不自动登录，需重新输入 Key。  
**方案**: Landing 按钮已改为指向 `/account`，用户到 Account 页面输入 Key。

### 3.2 API 依赖

| 页面 | 依赖 API | 数据源 |
|------|----------|--------|
| Landing | 无 | 纯静态 |
| Account | `/api/account/overview`, `/analyze` | GW2 API + 市价 |
| Insight | `/api/insight/data` | GW2 API + 市价 |
| Plan | `/api/v1/decide`, `/goal-driven/*` | 决策引擎 |
| Report | `/api/account/overview` | Account API |

---

## 四、安全与错误处理分析

| 场景 | 当前处理 | 评级 |
|------|----------|------|
| API Key 无效 | 401 错误 + 用户提示 | ✅ |
| GW2 API 超时 | `httpx.TimeoutException` 捕获 + 重试 3 次 | ✅ |
| DB 连接池耗尽 | `asyncio.TimeoutError` → RuntimeError → 500 | ✅ |
| Session 过期 | validate 返回 404 → 自动清除 | ✅ |
| 跨页面 session 丢失 | initSession 自动恢复 | ✅ |
| SVG ID 冲突 | sym- 前缀 | ✅ |
| CTA 按钮被遮挡 | `pointer-events: none` | ✅ |
| XSS | `escHtml()` 过滤 | ✅ |
| CSRF | FastAPI 自动处理 | ✅ |
| SQL 注入 | aiosqlite 参数化查询 | ✅ |

---

## 五、功能完整度总表

| 页面 | 核心功能 | 完整度 | 主要缺失 |
|------|---------|--------|---------|
| Landing | 转化引导 | 95% | 无 |
| Account | 数据展示 | 90% | 趋势图真实数据 |
| Insight | AI 分析 | 65% | Legendary Progress, Market Insight |
| Plan | 决策系统 | 70% | Timeline 动态, Explanation, Coach |
| Report | 商业化 | 40% | Stripe, PDF, 持久化 |

**总体完整度**:约 70%

---

## 六、建议修复优先级

| 优先级 | 问题 | 页面 | 预估 |
|--------|------|------|------|
| **P0** | Legendary Progress 无数据 | Insight | 2h |
| **P0** | Trend chart 使用随机数据 | Account | 1h |
| **P1** | Plan Timeline 静态 | Plan | 3h |
| **P1** | Stripe 集成 | Report | 8h |
| **P1** | Market Insight 缺失 | Insight | 4h |
| **P2** | PDF 导出 | Report | 4h |
| **P2** | Explanation Panel | Plan | 2h |
| **P3** | Coach AI 内容 | Plan | 8h |
| **P3** | 报告持久化 | Report | 4h |

---

## 七、代码质量指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 前端文件数 | ~20 | HTML+CSS+JS |
| 后端 Python 文件 | ~50 | 含 services/routes/ontology |
| 测试数 | 47 | 核心 UI + API 测试 |
| 测试通过率 | 92% | 4 个预存失败 |
| SVG 图标 | 44 | 全部带 sym- 前缀 |
| CSS 自定义属性 | ~25 | `--gw2-*` token |
| API 端点 | ~30 | 含 auth/account/insight/plan |
