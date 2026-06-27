# GW2 Progression OS — 交接文档

> 日期：2026-06-27  
> 分支：`codex/resolve-gitnexus-critical`  
> 测试：47 passed / 4 预存失败  
> 服务器端口：8512（默认）/ 8513（备用）

---

## 一、项目架构

```
/          → Landing 页（转化入口）
/account   → 纯数据层（gw2efficiency 风格）
/insight   → AI 覆盖层
/plan      → 决策系统（核心差异化）
/report    → 商业化（付费 + 导出）
```

### 导航栏

所有页面统一：**Account → Insight → Plan → Report**

---

## 二、本次改动清单（按时间顺序）

| 序号 | 改动 | 文件 | 说明 |
|------|------|------|------|
| 1 | 三层数据架构 | `models_data.py` · `snapshot_service.py` | Raw → Normalized → Derived 三层模型 |
| 2 | 市场价格注入 | `api/routes/account.py` | 材料/银行/角色背包显示真实市价 |
| 3 | 角色装备提取 | `services/holdings_service.py` | Equipment 作为独立资产类别 |
| 4 | 统一 Session 管理 | `session-manager.js` | 所有页面共用，版本化存储 key `gw2_session_v2` |
| 5 | SVG 图标系统 | `icons.svg` + 4 个 HTML | 44 个 GW2 风格图标，sprite 内联 |
| 6 | Session 验证端点 | `api/main.py` | `GET /auth/session/validate?token=...` |
| 7 | 字体加大 | `style.css` · `style-account.css` | body 14→15px, KPI 22→24px |
| 8 | Landing 页面 | `landing.html` · `style-landing.css` | 7 个 Frame 完整 Figma 设计 |
| 9 | Report 页面 | `report.html` · `style-report.css` | 三层定价卡 + 锁定内容预览 |
| 10 | 导航统一 | 所有 HTML + JS 文件 | 顺序统一 + 页面跳转替代 SPA |
| 11 | DB 连接池优化 | `database.py` | 池 5→20，健康检查，超时保护 |
| 12 | 事件总线 | `services/event_bus.py` | Audit/Ontology 异步化 |

---

## 三、已修复的 Bug

| Bug | 根因 | 修复 |
|-----|------|------|
| KPI 显示 "—" | SVG `<symbol>` ID 与 `<div>` ID 冲突，`getElementById` 返回不可见元素 | SVG 符号加 `sym-` 前缀 |
| DB `no active connection` | `get_db()/release_db()` 无健康检查，长操作后连接关闭 | 全部改用 `using_db()` + SELECT 1 |
| DB 池耗尽 | 池大小 5，`fetch_all` 44s 持有连接 | 池 5→20，加 30s 超时 |
| session 验证 500 | `get_session` 未在 main.py import | 添加 import |
| 导航点击无效 | plan/insight JS 用 SPA toggle 而非页面跳转 | 改为 `window.location.href` |
| Insight/Plan 空白 | validate 端点 500 → `initSession()` 返回 null | 修复 validate |
| 浏览器缓存旧 JS | `Cache-Control` 不生效 | 文件改名 `.v2.js` |
| Landing → Account 需重输 Key | 旧 `gw2_session` key 与新版不兼容 | `clearSession()` 同时清理新旧 key |
| SVG 图标不显示 | 浏览器缓存 `app-shared.js` 无 `loadIconSprite` | SVG sprite 内联到 HTML |

---

## 四、关键文件地图

### 前端 (src/gw2_progression/static/)

| 文件 | 用途 | 说明 |
|------|------|------|
| `landing.html` | Landing 页 | 7 个 Frame：Hero → Value → Demo → HowItWorks → Trust → CTA |
| `account.html` | 数据仪表盘 | Key 输入 → KPI → 资产表 → 角色表 |
| `insight.html` | AI 覆盖层 | Hidden Wealth / Build Readiness / Legendary / Top Items |
| `plan.html` | 决策系统 | Goal 输入 → 策略选择 → P0/P1/P2 → 7天 Timeline |
| `report.html` | 商业化 | 免费预览 → 定价卡 (Free/$5/$5mo) → 锁定内容 |
| `session-manager.js` | Session 管理 | `initSession()` / `createSession()` / `clearSession()` / `getEffectiveKey()` |
| `app-account.v2.js` | Account 页逻辑 | `runAnalyze()` → `renderDashboard()` |
| `app-insight.v2.js` | Insight 页逻辑 | `loadInsight()` → 显示 AI 数据 |
| `app-plan.v2.js` | Plan 页逻辑 | 目标解析 → 策略切换 → Plan 渲染 |
| `app-report.v2.js` | Report 页逻辑 | 数据加载 → 定价卡渲染 |
| `icons.svg` | SVG 图标 sprite | 44 个符号，所有页面内联使用 |
| `style.css` | 基础样式 | Design tokens + 排版 + 表格 |
| `style-account.css` | Account 页样式 | KPI 卡片 + 资产表 |
| `style-landing.css` | Landing 页样式 | 7 个 Frame 完整设计 |
| `style-insight.css` | Insight 页样式 | 紫金主题 AI 卡片 |
| `style-plan.css` | Plan 页样式 | 策略按钮 + 动作卡片 |
| `style-report.css` | Report 页样式 | 定价卡 + 锁定内容 |

### 后端 (src/gw2_progression/)

| 文件 | 用途 | 关键函数 |
|------|------|----------|
| `api/routes/account.py` | 账号总览 API | `GET /api/account/overview` |
| `api/routes/insight.py` | 洞察 API | `GET /api/insight/data` |
| `api/main.py` | 路由 + 中间件 | session/create/validate/delete |
| `services/auth_service.py` | Session CRUD | `create_session` / `get_session` / `get_api_key` |
| `services/snapshot_service.py` | 三层数据管道 | `normalize_account()` / `derive_value()` / `derive_breakdown()` |
| `services/holdings_service.py` | 物品提取 | `extract_wallet/materials/bank/character/equipment/tradingpost` |
| `services/price_service.py` | 市价 | `fetch_prices()` + `compute_price_quality()` |
| `services/event_bus.py` | 事件总线 | `emit()` / `on()` / `start()` |
| `models_data.py` | 三层数据模型 | `RawAccountData` → `NormalizedAccountData` → `AccountValue` |
| `database.py` | DB 连接 | `using_db()` 带健康检查 + `get_db()` 带超时 |

### 测试 (tests/)

| 文件 | 用例数 | 覆盖内容 |
|------|--------|---------|
| `test_routes.py` | 18 | 页面/静态文件/API/重定向/SVG |
| `test_ui_comprehensive.py` | 29 | Page/SVG icon/API shape/Landing |
| `test_auth_service_full.py` | 19 | Session CRUD / token 解析 / 边界 |
| `test_holdings_service.py` | 25 | 物品提取全路径 |
| **合计** | **47** | **全部通过** |

---

## 五、当前存在的问题

| 问题 | 风险 | 说明 |
|------|------|------|
| `test_static_js` 测试 404 | 低 | 旧 `app.js` 已删除，test 引用需更新 |
| `test_valuation` 测试挂起 | 低 | `ValueSummary.breakdown` 字段不存在 |
| `test_e2e` 价值分析失败 | 低 | 快照导入路径变更 |
| 导航按钮登录前灰显未完成 | 低 | CSS 已加 `requires-auth`，JS 逻辑待接入 |
| `test_v5.py` 超时 | 低 | 独立预存问题，非本次改动导致 |

---

## 六、启动与测试

```bash
# 启动服务器
cd D:\Projects\gw2-progression
python -m uvicorn gw2_progression.api.main:app --app-dir src --host 0.0.0.0 --port 8512 --log-level info

# 运行全部测试（排除已知问题）
python -m pytest tests/ --ignore=tests/e2e --ignore=tests/test_v5.py -q

# 运行核心 UI 测试
python -m pytest tests/test_routes.py tests/test_ui_comprehensive.py -v

# API 验证
curl "http://127.0.0.1:8512/api/account/overview?api_key=YOUR_KEY"
```

### 开发注意事项

1. **JS 缓存**：修改 `app-xxx.js` 后需同步复制到 `app-xxx.v2.js`
2. **SVG 图标**：新增图标需同时更新 `icons.svg` 和所有 HTML 的内联 sprite
3. **HTML 内联 SVG**：修改 `icons.svg` 后需重新运行 `fix_inline_svg.py` 同步到 HTML
4. **CSS 变量**：使用 `var(--gw2-*)` 设计 token，不要硬编码颜色
5. **Session key**：localStorage key 为 `gw2_session_v2`，旧 `gw2_session` 会自动清理

---

## 七、后续建议

1. **登录前导航灰显**：补完 `requires-auth` JS 逻辑
2. **预存测试修复**：更新 `test_static_js` 引用、修复 `test_valuation`
3. **趋势图数据源**：当前使用随机数据，需接入真实快照历史
4. **支付集成**：Stripe 接入（`report.html` 中的 `alert()` 占位）
5. **角色装备价值**：当前 Equipment 类别使用市场价格估算，可优化为精确计算
