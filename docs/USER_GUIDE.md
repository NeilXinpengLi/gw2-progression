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
4. 分析完成后自动跳转到行动中心

> 💡 **首次使用？** 页面上方有欢迎引导，告诉你系统能做什么以及隐私保护说明。

---

## 🎯 行动中心 (首页)

分析完成后，你会看到以下内容：

### Hero Metrics（核心指标）

顶部三个大卡片：
- **💰 Total Value**：你账号的总资产价值
- **🪙 Wallet**：你的流动资金
- **👤 Characters**：角色数量和皮肤总数

### 🎯 Today You Should Do

按优先级排列的行动建议：

| 优先级 | 颜色 | 含义 |
|--------|------|------|
| **P0** | 🟠 橙色 | 关键路径——最高价值行动 |
| **P1** | 🟢 绿色 | 成长路径——有意义的前进 |
| **P2** | 🔵 蓝色 | 可选优化——锦上添花 |

每条建议都包含具体行动说明，点击即可跳转到相关功能 Tab。

### 📈 7-Day Growth Path

7 天成长时间线，每天一个建议行动，附带完成进度条：
- Day 1 → Sell & Liquidate
- Day 2 → Goal Progress
- Day 3 → Build Gear
- 以此类推，直到 Day 7 回顾计划

### 🎯 Weekly Quests

7 个周常任务，点击即可勾选完成状态：

| 任务 | 说明 |
|------|------|
| Sell & Liquidate | 检查 TP，卖多余材料，整合金币 |
| Goal Progress | 收集传奇材料，完成时间限制制作 |
| Build Gear | 获取缺失装备，打碎层 |
| Map Completion | 收集地图货币和烈性魔法 |
| Fractal Push | 完成 T4 日常和推荐 |
| WvW / PvP | 完成周常奖励，赚取兑换券 |
| Review & Plan | 评估本周进展，规划下周目标 |

所有完成状态会自动保存，跨会话持久化。

### 📊 Quick Stats

快速统计面板：总价值、钱包、材料、银行、角色数、皮肤数

### 📋 Account Details（折叠）

账号详情：创建时间、游戏时长、碎层等级、成就点数等

### 💡 Recommendations（折叠）

基于账号数据的个性化建议

---

## 💰 账号估值

**入口：Value 标签**

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

### Top Items

按价值排序的前 20 件物品，显示名称、数量、买价/卖价、定价状态。

### 价格质量

| 状态 | 含义 |
|------|------|
| ✅ Priced | 有完整买卖价格 |
| ❓ Unpriced | 缺少 TP 数据 |
| 🔒 Bound | 账号绑定 |
| 📊 Wide Spread | 买卖价差 > 20% |

---

## 🔍 物品搜索

**入口：Items 标签**

支持按名称或 ID 搜索，可筛选位置（银行/材料/角色/共享/TP）和状态。

点击搜索结果查看详情：
- **基本信息**：总数量、总买价/卖价、状态
- **市场深度**：最佳买价/卖价、价差、买/卖深度
- **位置分布**：每个位置的持有数量和估值

---

## ⚒ 制作计算器

**入口：Crafting 标签**

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

## 🎯 目标追踪与传奇规划

**入口：Goals 标签 + Planner 标签**

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

### 使用方式

1. 在 Goals 标签点击 **Create Goal**
2. 选择模板或自定义
3. 系统自动计算已完成材料百分比
4. 每次分析自动刷新进度

### Planner 标签

- 模板选择下拉
- 目标成本估算
- 材料清单
- 阻塞项检测

---

## ⚔ Build 推荐

**入口：Builds 标签**

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

### 覆盖 9 职业 20 Build

Guardian (3), Warrior (2), Revenant (2), Ranger (2), Thief (2), Engineer (2), Necromancer (2), Elementalist (2), Mesmer (2) + Heal Scourge

---

## 🤖 成长教练

**入口：Advisor 标签**

### Coach Plan（教练计划）

点击 **Generate Advice** 获取：
- **P0 关键路径**：最高优先级行动（资产变现、角色升级、接近完成的传奇）
- **P1 成长路径**：有意义的前进方向（皮肤解锁、新职业尝试、Build 准备）
- **P2 可选优化**：锦上添花的建议（日常收入、投资机会）

### 7 天日计划

每天一个明确的行动方向：
- Monday → Sell & Liquidate
- Tuesday → Goal Progress
- Wednesday → Build Gear
- Thursday → Map Completion
- Friday → Fractal Push
- Saturday → WvW / PvP
- Sunday → Review & Plan

---

## 👥 公会空间

**入口：Guild 标签**

> 适合开荒队、WvW 小队、公会管理团队。

### 公会价值

| 功能 | 说明 |
|------|------|
| 📊 成员对比 | 比较各成员的账号价值 |
| 🎭 职业覆盖 | 查看团队的职业分布和缺口 |
| 📈 资产追踪 | 跟踪组合资产增长 |
| 🏆 Build 就绪 | 识别谁最接近关键 Build |

### 创建公会

1. 输入公会名称
2. 点击 **Create Guild**
3. 系统生成邀请码，分享给成员

### 加入公会

1. 获取邀请码
2. 输入并点击 **Join Guild**
3. 你的数据会自动加入公会聚合视图

---

## 📄 报告与导出

**入口：Overview → Export Report**

点击 **Export Report** 下载 JSON 格式的完整账号报告，包含：
- 账号基本信息
- 总价值和分类价值
- Top 10 最有价值物品
- 报告生成时间

历史报告列表显示在 Overview 页面。

---

## ⚙ 设置

**入口：Settings 标签**

### Credentials（凭证管理）

| Provider | 用途 |
|---------|------|
| OpenAI | 报告生成、Advisor 建议 |
| Anthropic | 报告生成、Advisor 建议 |
| DeepSeek | 报告生成、Advisor 建议 |
| Ollama | 本地运行，无需 API Key |

所有 API Key 使用 Fernet 加密存储，只显示最后 4 位，支持随时删除。

### 周报订阅

输入邮箱，每周自动收到账号价值变化、目标进度、Build 更新。

### Affiliate 推荐

创建你的 Referral Code，分享给其他玩家，他人购买时你获得佣金。

### Seller 产品

可购买的报告产品：
- Account Value Report
- Legendary Gap Report
- Build Readiness Report
- Weekly Progression Subscription
- Guild Account Audit

---

## ❓ 常见问题

### 我的 API Key 安全吗？
✅ 只在内存中使用，不记录日志，加密存储可选，支持随时删除或撤销。

### 哪些权限是必须的？
最小：`account` + `inventories` + `characters` + `wallet`  
完整：加上 `tradingpost` + `progression` + `builds` + `unlocks`

### 为什么有些物品显示 ❓ Unpriced？
这些物品在交易所没有活跃订单。常见原因：极稀有、账号绑定、缺少 `tradingpost` 权限。

### Build 推荐没有结果？
确认 API Key 包含 `characters` 权限，且至少有一个 80 级角色。

---

## 📊 系统信息

| 项目 | 数值 |
|------|------|
| 测试 | 280 passed（269 单元 + 11 E2E） |
| 路由 | 103 API endpoints |
| CI | GitHub Actions（lint → test → docker） |
| 数据 | SQLite WAL |
| 安全 | Fernet 加密 + CORS + 安全头 + 审计日志 |
