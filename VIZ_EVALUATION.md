# API Key 账号信息操作 — 数据可视化评估

> 基于代码图谱 + 语义图谱的端到端可视化质量分析
> 覆盖链路: API Key 输入 → 验证 → 数据获取 → 前端渲染 → 错误处理

---

## 1. 可视化链路总览

```
[key-input] ──▶ POST /analyze ──▶ Backend ──▶ GW2 API ──▶ AccountContents JSON
     │                                                          │
     │  ┌───────────────────────────────────────────────────────┘
     │  ▼
     ├─ renderOverview()    → 统计卡片 + 权限徽章 + 错误展示
     ├─ renderCharacters()  → 纸娃娃 + 武器切换 + 饰品 + 列表
     ├─ renderWallet()      → 货币排序列表 + 金币格式化
     ├─ renderInventory()   → 材料 Top40 + 银行槽位
     ├─ renderProgression() → 精通表 + 点数卡 + 成就计数
     ├─ renderPvp()         → 统计网格 + 最近比赛表
     ├─ renderUnlocks()     → 解锁计数网格 + Finisher 表
     ├─ renderWvw()         → WvW 信息卡
     └─ setupWardrobe()     → 皮肤网格 (懒加载 + 分页 + 搜索)
```

---

## 2. 逐阶段评估

### 2.1 API Key 输入阶段

| 评估维度 | 状态 | 详情 |
|---|---|---|
| 输入引导 | ✅ | `placeholder="Paste your GW2 API key…"`, `autocomplete="off"` |
| Enter 提交 | ✅ | `keydown` 监听 Enter 键触发 `runAnalyze()` |
| 按钮禁用 | ✅ | `btn.disabled = true/false`，防止重复提交 |
| **空输入保护** | ⚠️ 部分 | `if (!key) return;` 提前返回，但无 UI 提示 |
| 格式校验 | ✅ 后端 | 422 返回含 `detail` 信息，但前端 `catch` 中显示通用错误消息 |
| 加载提示 | ✅ | 3 阶段状态消息: "Fetching" → "Resolving" → "Loaded" |

**发现问题**:
- 空 key 无声无息返回，用户无反馈
- 后端 422 错误消息 (`"API key must be at least 8 characters"`) 通过 `err.detail` 传到前端，但前端 catch 统一显示，格式为 "Error: API key must be at least 8 characters"，对非技术用户不够友好
- 无 "API key 获取方式" 引导链接（如 GW2 官网 API 页面）

---

### 2.2 数据获取阶段

| 评估维度 | 状态 | 详情 |
|---|---|---|
| 后端异步并发 | ✅ | `asyncio.gather()` 并行 22 个端点 + 4 unlock 子端点 |
| 权限门控 | ✅ | 仅获取已授权的 scope |
| 错误隔离 | ✅ | `_safe()` 异常 → `errors` dict, 不阻塞其他端点 |
| 超时保护 | ✅ | 30s timeout |
| 重试机制 | ✅ | 5xx 重试 3 次 (1s/2s/4s) |
| 连接池复用 | ✅ | 单例 `AsyncClient` |

**发现问题**:
- 无请求取消：用户输入新 key 后旧请求仍在飞
- 无加载进度：所有结果一次返回，无法逐 section 显示

---

### 2.3 Overview 可视化

| 评估维度 | 状态 | 详情 |
|---|---|---|
| 统计卡片 | ✅ | 8 项核心指标：Account/Playtime/Fractal/AP/WvW/Characters/Skins/Dyes |
| 权限网格 | ✅ | 11 个 scope 的 ✓/✗ 徽章 |
| **缺失字段** | ❌ | `monthly_ap` 已从后端获取但未在前端展示 |
| **账号创建日** | ❌ | `account_created` 已获取但未可视化 |
| **Build 存储** | ❌ | `builds` 已获取但 Overview 未显示 |
| 错误展示 | ✅ | `ERR_TAB_MAP` 将错误路由到对应 tab，known limitations 高亮显示 |

---

### 2.4 Characters 可视化

| 评估维度 | 状态 | 详情 |
|---|---|---|
| 角色切换 | ✅ | 按钮式角色选择器 |
| 纸娃娃网格 | ✅ | 6 行 × 2 列 CSS grid，皮肤图标 + 染色圆点 |
| 武器切换 | ✅ | Set 1 / Set 2 并列显示 |
| 饰品行 | ✅ | 6 种饰品槽位 |
| 公会徽章 | ✅ | 名称 + tag |
| 装备列表 | ✅ | 全部装备平铺列表，带图标/名称/类型 |
| **tab 内空白态** | ⚠️ | 无角色时显示空选择器，无提示消息 |
| **装备缺失图标** | ⚠️ | `skinIcon()` / `itemIcon()` 失败时显示 `?` 占位符，合理 |
| **大账号性能** | ⚠️ | 50+ 角色全部一次获取，前端全部遍历提取装备数据 |

---

### 2.5 Wardrobe 可视化

| 评估维度 | 状态 | 详情 |
|---|---|---|
| 懒加载 | ✅ | 切换到 Wardrobe tab 才触发 `loadWardrobeOnce()` |
| 分片 | ✅ | 200 个/批 + "Show more" 按钮 |
| 搜索 | ✅ | 按名称实时过滤 |
| 类型过滤 | ✅ | 下拉选择 Armor/Weapon/Back |
| 子类型过滤 | ✅ | 自动从当前数据提取 |
| 计数 | ✅ | "Showing X of Y skins" |
| **搜索防抖** | ❌ | `input` 事件每次触发重建列表，无 debounce |
| **无结果提示** | ❌ | 过滤后 0 结果不显示空状态提示 |
| **图标加载** | ⚠️ | 图标来自 GW2 CDN，加载失败无 fallback 样式 |

---

### 2.6 Wallet 可视化

| 评估维度 | 状态 | 详情 |
|---|---|---|
| 排序 | ✅ | 按 `value` 降序 |
| 金币格式化 | ✅ | `fmtCoin()` → "12g 34s 56c" |
| 名称/描述 | ✅ | 通过 `_currencyCache` 解析 |
| **大数量截断** | ⚠️ | 50+ 货币全部渲染，无截断或分组 |
| **数量单位** | ⚠️ | 非 coin 货币仅显示数字 `.toLocaleString()`，缺少后缀说明 |

---

### 2.7 Inventory 可视化

| 评估维度 | 状态 | 详情 |
|---|---|---|
| 材料 Top 40 | ✅ | 按数量排序，前 40 条 |
| 图标 + 名称 | ✅ | `itemIcon()` + `itemName()` |
| 分类名 | ✅ | `matCatName()` 从 `/v2/materials` 获取 |
| 银行槽位 | ✅ | "used / total" 统计卡 |
| **非 material 物品** | ❌ | `bank` 中的物品仅计数，无列表显示 |
| **共享背包** | ❌ | `shared_inventory` 已获取但未在前端展示 |
| **Top 40 硬限制** | ⚠️ | 硬编码 `slice(0, 40)`，无展开选项 |

---

### 2.8 Progression 可视化

| 评估维度 | 状态 | 详情 |
|---|---|---|
| 精通表 | ✅ | 名称 + 区域 + 等级三列 |
| 精通点数 | ✅ | `spent / earned` 按区域统计卡片 |
| 成就计数 | ✅ | 总成就数 |
| 空数据 | ✅ | `'No mastery data'` 占位行 |
| **无区域筛选** | ⚠️ | 精通列表不可按区域过滤 |
| **成就深度** | ⚠️ | 仅显示计数，无成就列表/进度条 |

---

### 2.9 PvP 可视化

| 评估维度 | 状态 | 详情 |
|---|---|---|
| 统计网格 | ✅ | rank/wins/losses/win rate/desertions/byes |
| 最近比赛表 | ✅ | 10 场 map/result/score/profession |
| **无天梯展示** | ❌ | `pvp_standings` 已获取但未可视化 |
| **无地图名称 fallback** | ⚠️ | `resolveMaps()` 失败时表列为空 |

---

### 2.10 Unlocks + WvW 可视化

| 评估维度 | 状态 | 详情 |
|---|---|---|
| Unlock 计数 | ✅ | skins/dyes/minis 数量 + finisher 表 |
| Finisher 表 | ✅ | ID + 永久/数量状态 |
| WvW 信息 | ✅ | team + rank |
| **无迷你/染料列表** | ⚠️ | 仅计数，无可视化列表 |

---

### 2.11 错误与边界状态

| 评估维度 | 状态 | 详情 |
|---|---|---|
| 网络错误 | ✅ | catch 显示 "Error: ..." |
| 401 未授权 | ✅ | 后端返回 401 → 前端显示错误消息 |
| 422 格式错误 | ✅ | 后端校验 → 422 → 前端显示 detail |
| 逐 tab 错误 | ✅ | `ERR_TAB_MAP` 精确路由 |
| known limitations | ✅ | guilds 特殊说明框 |
| **500+ 后端错误** | ⚠️ | 前端统一显示 `err.detail`，无细分 |
| **重试中无用户提示** | ❌ | `_get()` 内部重试对前端透明，用户不知正在重试 |
| **并发中止** | ❌ | 无 AbortController，旧请求可能与新请求竞争 |

---

## 3. 语义图谱 — 可视化缺失映射

| 后端已有数据 | 前端未展示 | 严重度 | 建议 |
|---|---|---|---|
| `account_created` | Overview 无创建日期 | Low | 加入统计卡片 |
| `monthly_ap` | Overview 无月度 AP | Low | 加入统计卡片 |
| `builds` | 任何 tab 均无装备模板展示 | Medium | 新增 "Builds" tab |
| `pvp_standings` | PvP 无天梯分段 | Low | 加入 PvP tab |
| `shared_inventory` | Inventory 无共享背包物品 | Medium | 加入 Inventory tab |
| `unlocked_dyes` (list) | Unlocks 仅显示计数 | Low | 可选展开染料列表 |
| `unlocked_minis` (list) | Unlocks 仅显示计数 | Low | 可选展开迷你列表 |

---

## 4. 可视化质量评分

| Tab | 覆盖率 | 交互性 | 容错性 | 性能 | 总分 | 评级 |
|---|---|---|---|---|---|---|
| Overview | 6/8 (75%) | 低 | 高 | 高 | 8.0/10 | 🟢 |
| Characters | 9/10 (90%) | 中 | 中 | 中 | 8.5/10 | 🟢 |
| Wardrobe | 7/8 (88%) | 高 | 中 | 中 | 8.0/10 | 🟢 |
| Wallet | 5/5 (100%) | 低 | 中 | 高 | 8.5/10 | 🟢 |
| Inventory | 5/7 (71%) | 低 | 低 | 高 | 6.5/10 | 🟡 |
| Progression | 5/6 (83%) | 低 | 中 | 高 | 7.5/10 | 🟢 |
| PvP | 4/6 (67%) | 低 | 中 | 高 | 6.5/10 | 🟡 |
| Unlocks | 4/6 (67%) | 低 | 中 | 高 | 6.5/10 | 🟡 |
| WvW | 2/2 (100%) | 低 | 高 | 高 | 8.0/10 | 🟢 |

---

## 5. 改进优先级

### P0 — 缺失功能导致信息丢失

| 问题 | 影响 | 修复难度 |
|---|---|---|
| `shared_inventory` 未展示 | 用户看不到共享背包物品 | 低（~0.5h） |
| `pvp_standings` 未展示 | 用户看不到天梯信息 | 低（~0.5h） |

### P1 — 体验缺口

| 问题 | 影响 | 修复难度 |
|---|---|---|
| 空 key 无 UI 反馈 | 用户点击 Analyze 无反应 | 低（~0.2h） |
| 422 错误消息不友好 | 非技术用户看不懂 | 低（~0.3h） |
| 搜索防抖缺失 | 高频输入触发大量重渲染 | 低（~0.3h） |
| 无过滤空结果提示 | 用户不知搜索无结果 | 低（~0.2h） |
| 请求无取消 (AbortController) | 快速切换 key 时竞争条件 | 中（~0.5h） |

### P2 — 增强

| 问题 | 影响 | 修复难度 |
|---|---|---|
| 后端重试对前端透明 | 用户不知正在重试 | 低（~0.3h） |
| 装备模板 (build) 无 tab | 无法查看已保存的 Build | 中（~1h） |
| 材料 Top 40 无展开 | 无法查看全部材料 | 低（~0.3h） |
| 银行物品无列表 | 仅显示占用槽位数 | 中（~1h） |
