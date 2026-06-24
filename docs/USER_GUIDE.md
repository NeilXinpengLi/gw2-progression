# GW2 Progression — 用户指南

> **你的 Guild Wars 2 个人成长教练。**  
> 输入 API Key，立刻了解账号价值、最接近的传奇、Build 可达性，并获得每日行动计划和周常任务。

---

## 📖 目录

1. [快速开始](#-快速开始)
2. [Page 1: 行动中心](#-page-1-行动中心-home)
3. [Page 2: 成长教练](#-page-2-成长教练-coach)
4. [Page 3: 成长路径](#-page-3-成长路径-timeline)
5. [Page 4: 高级工具](#-page-4-高级工具-tools)
6. [常见问题](#-常见问题)

---

## 🚀 快速开始

### 获取 API Key

1. 访问 [ArenaNet 应用管理](https://account.arena.net/applications)
2. 点击 **Create New Key**
3. 勾选权限（越多分析越完整）：

| 权限 | 用途 | 建议 |
|------|------|------|
| `account` | 显示你的账号名和世界 | ✅ **必须** |
| `characters` | 角色装备和背包分析 | ✅ **必须** |
| `inventories` | 银行、材料、共享背包估值 | ✅ **必须** |
| `wallet` | 金币和货币显示 | ✅ **必须** |
| `tradingpost` | 交易所订单资产计算 | ⭐ **推荐** |
| `progression` | 传奇/成就目标分析 | ⭐ **推荐** |
| `builds` | Build 可达性检测 | ⭐ **推荐** |
| `unlocks` | 皮肤/染料收藏统计 | 可选 |
| `guilds` | 公会信息 | 可选 |
| `pvp` | PvP 数据 | 可选 |
| `wvw` | WvW 数据 | 可选 |

4. 复制生成的 Key（格式如 `ABCDEF01-2345-6789-ABCD-EF0123456789AB`）

### 第一次使用

1. 在首页粘贴你的 API Key
2. 点击 **Analyze** 按钮
3. 观察进度条——系统会依次请求 16 个 GW2 API 端点
4. 分析完成后首先进入 **Insight Screen**（惊喜结果页）
5. 点击 "Continue to Action Center" 进入主界面

> 🔒 **隐私说明：** 你的 API Key 只在内存中使用，不会保存到服务器日志。加密保存是可选的，你可以随时删除或撤销 Key。

### 页面导航

系统底部有 4 个导航按钮：

```
┌──────────────────────────────────────────────┐
│  🏠 Home    🤖 Coach    📆 Timeline    🧰 Tools  │
└──────────────────────────────────────────────┘
```

| 页面 | 功能 | 适合谁 |
|------|------|--------|
| **Home** | 行动中心 + 决策入口 | **所有人** |
| **Coach** | 统一成长规划 | 想深入规划的用户 |
| **Timeline** | 7 天执行路径 | 需要执行节奏的用户 |
| **Tools** | 高级功能 | 需要深入分析的用户 |

---

## 🏠 Page 1: 行动中心 (Home)

行动中心是整个系统的核心页面。每次分析完成后，你首先看到的是 Insight Screen。

### Insight Screen（惊喜结果页）

这是你每次分析后看到的第一屏——**不展示功能，只展示结果**：

```
┌──────────────────────────────────────┐
│         🎉 Your GW2 Snapshot         │
│                                      │
│          💰 12,340g                   │
│      total estimated account value    │
│                                      │
│  🪙 500g    👤 5    🎨 150    ⚔ 92%  │
│  Wallet  Chars  Skins  Best Build    │
│                                      │
│  🚨 KEY INSIGHT                      │
│  You are 87% toward Bolt!            │
│  Focus on the remaining materials.   │
│                                      │
│  [ Continue to Action Center → ]    │
└──────────────────────────────────────┘
```

**Insight 卡片解读：**

| 卡片 | 说明 |
|------|------|
| 💰 **Total Value** | 你账号的总资产价值（所有物品估值总和） |
| 🪙 **Wallet** | 流动资金（可直接使用的金币） |
| 👤 **Characters** | 角色数量 |
| 🎨 **Skins** | 已解锁皮肤数 |
| ⚔ **Best Build** | 当前最匹配的 Build 就绪度 |
| 🏆 **Closest Goal** | 最接近完成的传奇进度 |

**Key Insight** 基于你的数据动态生成：

| 场景 | 你会看到 |
|------|---------|
| Build 就绪度 > 80% | "You are X% ready for Build X. Acquire the missing items." |
| 传奇进度 > 50% | "You are X% toward Legendary X. Focus on remaining materials." |
| 有资产价值 | "Your account holds Xg in assets. Review your Top Items." |

---

### Action Center（主界面）

点击 "Continue to Action Center" 后进入主界面。

#### 核心指标 (Hero Metrics)

顶部三个大卡片展示你最关心的数据：

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│   💰    │  │   🪙    │  │   👤    │
│ 12,340g │  │   500g  │  │    5    │
│ Total   │  │  Wallet │  │  Chars  │
│ Value   │  │         │  │ 150skins│
└──────────┘  └──────────┘  └──────────┘
```

#### Today You Should Do（核心功能）

这是最重要的区域。系统会调用决策引擎 `/engine/decide`，根据你的账号数据实时生成优先级行动。

**优先级颜色：**

```
🟠 P0 — 关键路径（最高价值，立刻行动）
🟢 P1 — 成长路径（重要但不紧急）
🔵 P2 — 可选优化（锦上添花）
```

**每条行动包含：**
- 优先级标签（P0/P1/P2）
- 行动标题（如 "Review Top Items"）
- 具体原因说明
- 预期收益（如 "+12,000g"）
- 点击直接跳转到相关功能页面

**示例：**

| 优先级 | 行动 | 原因 | 收益 |
|--------|------|------|------|
| 🟠 P0 | Review Top Items | 你的账号价值 12,000g | +12,000g |
| 🟠 P0 | Level Characters | 2 个角色未满级 | Build Access |
| 🟢 P1 | Earn Gold | 流动资金不足 | ~20g/day |
| 🔵 P2 | Complete Dailies | 稳定收益来源 | ~10g/day |

#### Quick Stats

六个快速统计卡片：

```
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ Total  │ │ Wallet │ │Materials│ │  Bank  │ │Chara-  │ │ Skins  │
│ Value  │ │        │ │        │ │        │ │cters   │ │        │
│12,000g │ │  500g  │ │ 1,200g │ │ 3,000g │ │   5    │ │  150   │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

---

## 🤖 Page 2: 成长教练 (Coach)

Coach 页面是统一的决策入口，替代了传统的 "Advisor / Planner / Goals" 多 Tab 结构。

### P0 — Critical（关键路径）

最高优先级的行动，通常是：

| 行动 | 典型触发条件 |
|------|-------------|
| 审查 Top Items | 总资产价值 > 0 |
| 角色升级 | 存在未满级角色 |
| 完成传奇 | 传奇进度 > 50% |
| 装备 Build | Build 就绪度 > 70% |

### P1 — Growth（成长路径）

中等优先级的行动：

| 行动 | 典型触发条件 |
|------|-------------|
| 开始传奇目标 | 已有目标但进度 < 50% |
| 朝 Build 前进 | Build 就绪度 30-70% |
| 赚钱 | 流动资金 < 100g |

### P2 — Optional（可选优化）

日常优化建议：

| 行动 | 说明 |
|------|------|
| Complete Dailies | 日常成就和世界 boss |
| Check TP | 交易所投资机会 |

---

## 📆 Page 3: 成长路径 (Timeline)

### 7 天计划

每天一个明确的行动主题：

```
Day 1 → Sell & Liquidate     ░░░░░░░░  0%
Day 2 → Goal Progress        █░░░░░░░ 15%
Day 3 → Build Gear           ██░░░░░░ 30%
Day 4 → Map Completion       ███░░░░░ 45%
Day 5 → Fractal Push         ████░░░░ 60%
Day 6 → WvW / PvP            █████░░░ 75%
Day 7 → Review & Plan        ██████░░ 90%
```

| 天 | 主题 | 具体任务 |
|----|------|---------|
| **Day 1** | Sell & Liquidate | 检查 TP 列表、卖多余材料、整合金币 |
| **Day 2** | Goal Progress | 收集时间限制材料、使用 mystic forge、检查传奇需求 |
| **Day 3** | Build Gear | 获取缺失装备、打 T4 碎层、检查属性可选奖励 |
| **Day 4** | Map Completion | 收集烈性魔法、farm 地图货币、完成地图日常 |
| **Day 5** | Fractal Push | T4 日常 + 推荐、碎层专精、卖碎层垃圾 |
| **Day 6** | WvW / PvP | 完成周常奖励、赚取兑换券、Gift of Battle 进度 |
| **Day 7** | Review & Plan | 评估本周进展、规划下周目标、导出周报 |

### Weekly Quests

7 个周常任务，点击即可勾选完成状态：

```
✅ Sell & Liquidate — Review TP listings, sell excess materials
⬜ Goal Progress — Farm time-gated materials, use mystic forge
⬜ Build Gear — Acquire missing items, run T4 fractals
✅ Map Completion — Gather volatile magic, farm currencies
⬜ Fractal Push — Complete dailies + recommended
⬜ WvW / PvP — Earn skirmish tickets & pips
⬜ Review & Plan — Assess progress, plan next week
```

完成状态跨会话自动保存。顶部显示进度：`(3/7)`

---

## 🧰 Page 4: 高级工具 (Tools)

Tools 页面收纳了所有高级分析功能，以卡片形式展示：

```
┌──────────┐ ┌──────────┐ ┌──────────┐
│   💰    │ │    ⚒    │ │    🔍    │
│  Value  │ │ Crafting │ │   Item   │
│  Engine │ │Calculator│ │  Search  │
├──────────┤ ├──────────┤ ├──────────┤
│    ⚔    │ │    🏆    │ │    👤    │
│  Build  │ │  Goals & │ │Charact-  │
│ Explorer│ │Legendaries│ │   ers    │
├──────────┤ ├──────────┤ ├──────────┤
│    🪙   │ │    👥    │ │    ⚙    │
│  Wallet │ │  Guild   │ │ Settings │
│         │ │Workspace │ │          │
└──────────┘ └──────────┘ └──────────┘
```

点击任意卡片展开对应的功能面板。

### 功能详情

| 工具 | 页面内容 |
|------|---------|
| **💰 Value Engine** | 三口径估值、资产构成饼图、位置柱图、历史折线图、Top 20 物品、材料分类、持仓列表、估值警告 |
| **⚒ Crafting Calculator** | 目标物品搜索、数量设置、已有材料抵扣、购买 vs 制作对比、Shopping List、Crafting Steps、替代配方 |
| **🔍 Item Search** | 按名称/ID 搜索、位置筛选（银行/材料/角色/TP）、状态筛选（已定价/未定价/绑定）、物品详情、市场深度、套利检测 |
| **⚔ Build Explorer** | 20 个 curated Build、Readiness Score、缺失装备检测、Build 详情 |
| **🏆 Goals & Legendaries** | 13 个内置模板（Bolt/Twilight/Sunrise/Bifrost/Frostfang/Incinerator/Nevermore/Astralaria/Ad Infinitum/Vision/Aurora/Zojja/Ascended Armor）、自定义目标、进度追踪、Planner |
| **👤 Characters** | 角色列表、装备查看、衣柜、Equipment Templates、Build Templates |
| **🪙 Wallet** | 金币、karma、各货币余额 |
| **👥 Guild Workspace** | 创建/加入公会、成员列表、组合资产统计、职业覆盖矩阵 |
| **⚙ Settings** | 凭证管理（OpenAI/Anthropic/DeepSeek/Ollama）、周报订阅、Affiliate 推荐、Product 购买 |

---

## ❓ 常见问题

### 安全性

**Q: 我的 API Key 安全吗？**
A: ✅ 完全安全。Key 只在内存中使用，不写入日志。加密保存是可选项（Settings 中设置）。你随时可以删除或撤销 Key。

**Q: 系统会保存我的密码吗？**
A: 不会。GW2 API Key 不是密码，它只提供你授权的读取权限，不包含账号登录信息。

### 使用

**Q: 为什么系统只有 4 个页面？**
A: 2024 年 UI 重构后，从原来的 18 个功能 Tab 精简为 4 个主页面。这样你不需要在多个功能之间选择——系统会告诉你下一步该做什么。

**Q: 为什么有些物品显示 "Unpriced"？**
A: 这些物品在交易所没有活跃的买卖订单。常见原因：物品非常稀有很少交易、账号绑定不可交易、API Key 缺少 `tradingpost` 权限。

**Q: Build 推荐没有结果？**
A: 确认你的 API Key 包含 `characters` 权限，并且账号至少有一个 80 级角色。系统通过装备 ID 匹配 Build，不是通过职业名称。

**Q: Coach 页面是空的？**
A: 需要先完成一次完整的账号分析。如果已经有分析数据，尝试切换到其他页面再回来。

### 权限

**Q: 哪些权限是必须勾选的？**
A: 
- **最小推荐**：`account` + `inventories` + `characters` + `wallet`
- **完整功能**：加上 `tradingpost` + `progression` + `builds` + `unlocks`

**Q: 每个权限的用途是什么？**
A: 
| 权限 | 用途 |
|------|------|
| `account` | 账号名、世界、注册时间 |
| `characters` | 角色装备、背包、制作专业 |
| `inventories` | 银行、材料、共享背包 |
| `wallet` | 金币、karma 等货币 |
| `tradingpost` | 买卖订单、资产定价 |
| `progression` | 成就、专精、传奇进度 |
| `builds` | 保存的 Build 模板 |
| `unlocks` | 皮肤、染料、迷你 |

### 技术

**Q: 系统支持哪些浏览器？**
A: 支持 Chrome、Firefox、Edge、Safari 的现代版本。需要支持 ES Module。

**Q: 数据保存在哪里？**
A: 数据保存在服务器端的 SQLite 数据库中。分析结果会生成快照，历史记录保留最近 20 次。

**Q: 如何删除我的数据？**
A: 删除 API Key 或撤销 ArenaNet 上的 Key 即可。系统不会保留没有关联会话的数据。

---

## 📊 系统信息

| 项目 | 数值 |
|------|------|
| 测试覆盖 | 276 单元测试 + Playwright E2E |
| API 路由 | 105 endpoints |
| 页面架构 | 4 页（Home/Coach/Timeline/Tools） |
| 决策引擎 | 实时 P0/P1/P2 优先级生成 |
| 数据库 | SQLite WAL |
| CI/CD | GitHub Actions（lint → test → docker） |
| 部署 | Docker + nginx（支持 HTTPS） |
| 安全 | Fernet 加密 + CORS + 安全头 + 审计日志 |
| 隐私 | Key 不记录日志、不保存、可随时删除 |
