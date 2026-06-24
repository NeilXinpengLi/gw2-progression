# GW2 Progression — 用户指南

> **你的 Guild Wars 2 个人成长教练。**  
> 输入 API Key，立刻了解账号价值、最接近的传奇、Build 可达性，并获得每日行动计划和周常任务。

---

## 📖 快速上手

### 1. 获取 API Key

1. 访问 [ArenaNet 应用管理](https://account.arena.net/applications)
2. 点击 **Create New Key**
3. 勾选以下权限（越多分析越准确）：

| 权限 | 用途 | 必须？ |
|------|------|--------|
| `account` | 显示你的账号名和世界 | ✅ |
| `characters` | 角色装备和背包分析 | ✅ |
| `inventories` | 银行、材料、共享背包估值 | ✅ |
| `wallet` | 金币和货币显示 | ✅ |
| `tradingpost` | 交易所订单资产计算 | ⭐ 推荐 |
| `progression` | 传奇/成就目标分析 | ⭐ 推荐 |
| `builds` | Build 可达性检测 | ⭐ 推荐 |
| `unlocks` | 皮肤/染料收藏统计 | 可选 |

4. 复制生成的 Key 回到本系统

### 2. 开始分析

1. 在首页粘贴你的 API Key
2. 点击 **Analyze**
3. 观察进度条——系统会依次请求 16 个 GW2 API 端点
4. 分析完成后先进入 **Insight Screen**（惊喜结果页）
5. 点击 "Continue to Action Center" 进入主界面

> 💡 **首次使用？** 页面上方有欢迎引导，告诉你系统能做什么以及隐私保护说明。

---

## 🧭 页面导航

系统底部有 4 个导航按钮：

| 页面 | 位置 | 功能 |
|------|------|------|
| 🏠 **Home** | 默认首页 | Action Center + Insight |
| 🤖 **Coach** | 导航栏 | 统一决策与规划 |
| 📆 **Timeline** | 导航栏 | 7 天成长路径 + 周常任务 |
| 🧰 **Tools** | 导航栏 | 高级功能入口 |

---

## 🎯 Page 1: Home（行动中心）

### Insight Screen（首次进入）

分析完成后，首先看到惊喜结果页：

- **💰 Total Value** — 你的总资产价值
- **🪙 Wallet** — 流动资金
- **🎨 Skins** — 皮肤解锁数
- **⚔ Best Build** — 当前最匹配的 Build
- **🏆 Closest Goal** — 最接近完成的传奇

下方显示 **KEY INSIGHT**（关键洞察），根据你的数据动态生成：
- Build 就绪度 > 80% → 建议补齐缺失装备
- 传奇进度 > 50% → 建议专注收集材料
- 否则 → 建议检查高价值物品

点击 **"Continue to Action Center"** 进入主界面。

### Action Center（主界面）

#### Hero Metrics

顶部三个大卡片：
- **💰 Total Value**：你账号的总资产价值
- **🪙 Wallet**：你的流动资金
- **👤 Characters**：角色数量和皮肤总数

#### 🎯 Today You Should Do（核心功能）

由决策引擎 `/engine/decide` 实时生成，按优先级排列：

| 优先级 | 颜色 | 含义 |
|--------|------|------|
| **P0** | 🟠 橙色 | 关键路径——最高价值行动 |
| **P1** | 🟢 绿色 | 成长路径——有意义的前进 |
| **P2** | 🔵 蓝色 | 可选优化——锦上添花 |

每条建议包含：
- 行动名称和原因
- 预期收益（金币/Build 进度/传奇解锁）
- 点击直接跳转到相关功能页面

#### 📊 Quick Stats

快速统计面板：总价值、钱包、材料、银行、角色数、皮肤数

#### 📋 Account Details（折叠）

账号详情：创建时间、游戏时长、碎层等级、成就点数等

---

## 🤖 Page 2: Coach（统一决策）

替代旧的 Advisor / Planner / Goals 多 Tab 结构，所有建议统一入口。

### P0 — Critical（关键路径）

基于账号数据生成的关键行动：
- 总资产价值和 Top Items 审查
- 角色等级提升建议

### P1 — Growth（成长路径）

- 流动资金不足时的赚钱建议
- Build 和传奇进度推进

### P2 — Optional（可选优化）

- 日常成就和世界 boss 收益

---

## 📆 Page 3: Timeline（7 天成长路径）

### 7 天计划

每天一个明确的行动方向：

| 天 | 主题 | 任务 |
|----|------|------|
| Day 1 | Sell & Liquidate | 检查 TP，卖多余材料，整合金币 |
| Day 2 | Goal Progress | 收集传奇材料，使用 mystic forge |
| Day 3 | Build Gear | 获取缺失装备，打 T4 碎层 |
| Day 4 | Map Completion | 收集烈性魔法和地图货币 |
| Day 5 | Fractal Push | 完成日常 + 推荐 |
| Day 6 | WvW / PvP | 赚取兑换券和 pips |
| Day 7 | Review & Plan | 评估本周进展，规划下周 |

### ✅ Weekly Quests

7 个周常任务，点击即可勾选完成状态，跨会话持久化保存。

| 任务 | 说明 |
|------|------|
| Sell & Liquidate | 检查 TP，卖多余材料 |
| Goal Progress | 收集时间限制材料 |
| Build Gear | 获取缺失装备 |
| Map Completion | 收集地图货币 |
| Fractal Push | 完成 T4 日常 |
| WvW / PvP | 完成周常奖励 |
| Review & Plan | 评估本周进展 |

---

## 🧰 Page 4: Tools（高级功能）

所有高级功能收纳在此，点击卡片展开对应面板：

| 工具 | 说明 |
|------|------|
| **💰 Value Engine** | 完整资产估值 + 图表 + Top Items |
| **⚒ Crafting Calculator** | 配方树 + 已有材料抵扣 + 5 种优化策略 |
| **🔍 Item Search** | 按名称/ID 搜索 + 位置钻取 + 市场深度 |
| **⚔ Build Explorer** | 20 个 curated Build + Readiness Score |
| **🏆 Goals & Legendaries** | 13 个模板 + 进度追踪 + Planner |
| **👤 Characters** | 角色装备 + 背包 + 衣柜 |
| **🪙 Wallet** | 金币、 karma 和货币 |
| **👥 Guild Workspace** | 多账号聚合 + 角色覆盖矩阵 |
| **⚙ Settings** | 凭证管理 + 订阅 + Affiliate |

---

## 💰 Value Engine（估值引擎）

**入口：Tools → Value Engine**

### 三个估值口径

| 口径 | 含义 | 用途 |
|------|------|------|
| **Instant Sell**（即卖价） | 按最高买价 × 0.85 | 立刻卖出的实际收入 |
| **Listing Price**（挂卖价） | 按最低卖价 | 挂交易所的理论收入 |
| **Net Sell**（净卖价） | 挂卖价 − 15% 手续费 | 挂卖后的实际收入 |

### 图表

- **饼图**：资产按位置分布（银行、材料、角色、TP）
- **柱图**：各位置价值对比
- **折线图**：历史价值趋势（需要多次快照）

---

## ⚒ Crafting Calculator（制作计算器）

**入口：Tools → Crafting Calculator**

1. 输入目标物品 ID（支持名称搜索）
2. 设置数量
3. 可选勾选 "Use Owned Materials"
4. 点击 Calculate

**输出结果：**
- 购买成本 vs 制作成本对比
- Shopping List——需要购买的原材料
- Crafting Steps——分步制作流程
- Missing Materials——缺口材料明细
- Alternative Recipes——替代配方列表

---

## ⚔ Build Explorer（Build 推荐）

**入口：Tools → Build Explorer**

### 分析流程

1. 点击 **Analyze Build Readiness**
2. 系统将 20 个 curated Build 与你的账号装备对比
3. 按 Readiness Score 排序展示最接近的 Build

### Build Readiness 指标

| 指标 | 说明 |
|------|------|
| Readiness Score | 0-100%，装备匹配度 |
| Missing Items | 还缺多少件装备 |
| Missing Cost | 补齐缺口的大致成本 |
| Profession Match | 你是否有该 Build 的职业 |

---

## 🏆 Goals & Legendaries（目标追踪）

**入口：Tools → Goals & Legendaries**

### 13 个内置模板

| 模板 | 类型 | 难度 |
|------|------|------|
| Bolt / Twilight / Sunrise | 传奇大剑 | 中等 |
| The Bifrost | 传奇法杖 | 中等 |
| Frostfang | 传奇斧 | 中等 |
| Incinerator | 传奇匕首 | 中等 |
| Nevermore / Astralaria | 传奇武器 | 困难 |
| Ad Infinitum | 传奇背部 | 困难 |
| Vision / Aurora | 传奇饰品 | 困难 |
| Zojja's Greatsword | 升华大剑 | 简单 |
| Berserker Armor Set | 升华护甲 | 中等 |

---

## 👥 Guild Workspace（公会空间）

**入口：Tools → Guild Workspace**

> 适合开荒队、WvW 小队、公会管理团队。

### 公会价值

| 功能 | 说明 |
|------|------|
| 📊 成员对比 | 比较各成员的账号价值 |
| 🎭 职业覆盖 | 查看团队的职业分布和缺口 |
| 📈 资产追踪 | 跟踪组合资产增长 |
| 🏆 Build 就绪 | 识别谁最接近关键 Build |

---

## ⚙ Settings（设置）

**入口：Tools → Settings**

| 功能 | 说明 |
|------|------|
| **Credentials** | OpenAI/Anthropic/DeepSeek/Ollama API Key 管理 |
| **Weekly Subscription** | 输入邮箱，每周自动收到账号更新 |
| **Affiliate** | 创建 Referral Code，分享获得佣金 |
| **Products** | 可购买的报告产品 (Value/Legendary/Build Report) |

---

## ❓ 常见问题

### 我的 API Key 安全吗？
✅ 只在内存中使用，不记录日志，加密存储可选，支持随时删除或撤销。

### 为什么系统只有 4 个页面？
2024 年重构后从 18 个功能 Tab 精简为 4 个主页面：
- Home（行动入口）
- Coach（决策入口）
- Timeline（执行节奏）
- Tools（高级功能）

所有复杂功能收纳至 Tools 页面。

### 哪些权限是必须的？
最小：`account` + `inventories` + `characters` + `wallet`  
完整：加上 `tradingpost` + `progression` + `builds` + `unlocks`

### Build 推荐没有结果？
确认 API Key 包含 `characters` 权限，且至少有一个 80 级角色。

---

## 📊 系统信息

| 项目 | 数值 |
|------|------|
| 测试 | 276 passed（+7 engine tests） |
| 路由 | 105 API endpoints |
| 页面 | 4（Home/Coach/Timeline/Tools） |
| 闭环 | API Key → `/engine/decide` → Action Center |
| 数据 | SQLite WAL |
| 安全 | Fernet 加密 + CORS + 安全头 + 审计日志 |
| CI | GitHub Actions（lint → test → docker） |
