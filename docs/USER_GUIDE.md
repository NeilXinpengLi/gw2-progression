# GW2 Progression — 用户指南

> **你的 Guild Wars 2 个人成长 AI 教练。**  
> v5 自进化系统：会从你的行为中学习，越来越懂你的 GW2 成长方式。

---

## 📖 目录

1. [快速开始](#-快速开始)
2. [系统架构](#-系统架构)
3. [Page 1: 行动中心](#-page-1-行动中心-home)
4. [Page 2: 成长教练](#-page-2-成长教练-coach)
5. [Page 3: 成长路径](#-page-3-成长路径-timeline)
6. [Page 4: 高级工具](#-page-4-高级工具-tools)
7. [策略系统](#-策略系统)
8. [自进化学习](#-自进化学习)
9. [常见问题](#-常见问题)

---

## 🚀 快速开始

### 获取 API Key

1. 访问 [ArenaNet 应用管理](https://account.arena.net/applications) 创建 API Key
2. 勾选权限：

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

3. 粘贴 Key 到首页，点击 **Analyze**

### 首次体验流程

```
API Key 输入 → 分析进度条 (16 步) → Insight Screen (惊喜页)
    → Action Center (决策) → Coach (规划) → Timeline (执行)
```

---

## 🧭 系统架构

### 导航栏

底部 4 个导航按钮：

```
🏠 Home     🤖 Coach     📆 Timeline     🧰 Tools
```

| 页面 | 功能 | 适合 |
|------|------|------|
| **Home** | 行动中心 + Insight | 日常使用 |
| **Coach** | 统一决策 + 规划 | 深入规划 |
| **Timeline** | 7 天执行路径 | 执行节奏 |
| **Tools** | 高级功能 | 深入分析 |

### 系统版本演进

| 版本 | 能力 | 状态 |
|------|------|------|
| v1 | 基础数据分析和估值引擎 | ✅ |
| v2 | Crafting + Goals + Build 推荐 | ✅ |
| v3 | LLM Agent + 周计划 | ✅ |
| v4 | 可解释优化引擎 + 多策略 | ✅ |
| **v5** | **自进化学习系统** | ✅ **最新** |

---

## 🏠 Page 1: 行动中心 (Home)

### Insight Screen（首次进入）

分析完成后首先看到惊喜结果页：

```
💰 Your GW2 Snapshot
   12,340g total estimated account value

🪙 500g Wallet  |  👤 5 Characters  |  🎨 150 Skins
⚔ 92% Best Build  |  🏆 87% Closest Legendary

🚨 KEY INSIGHT
"你离 Condi Necro 就绪度仅差 2 件装备，优先补齐缺失部位."
```

点击 **"Continue to Action Center"** 进入主界面。

### 策略选择器

在 Action Center 顶部，你可以切换优化策略：

| 策略 | 优先级 | 适合玩家 |
|------|--------|---------|
| **Balanced**（默认） | 均衡发展 | 大多数玩家 |
| **Gold Farming** | 金币最大化 | 想快速赚钱 |
| **Build Completion** | Build 完成 | 想组新 Build |
| **Legendary Rush** | 传奇优先 | 想做传奇 |

系统会根据你的选择，重新计算所有行动的优先级和评分。

### 行动卡片

每条建议显示：

```
🟠 P0  Review Top Items: 账号价值 12,000g         92分
     gold: 0.8  build: 0.0  time: -0.1  risk: 0.0
```

| 元素 | 说明 |
|------|------|
| 🟠 **P0** | 优先级标签 (P0/P1/P2) |
| **行动名** | 建议的具体行动 |
| **原因** | 为什么做这个 |
| **92分** | 综合评分 (0-100) |
| **评分拆解** | gold/build/time/risk 各维度分数 |

### 核心指标

三个大卡片展示你最关心的数据：总资产、流动资金、角色数。

### Quick Stats

六个快速统计卡片：总价值、钱包、材料、银行、角色数、皮肤数。

---

## 🤖 Page 2: 成长教练 (Coach)

Coach 页面是统一的决策入口，替代了传统的多 Tab 结构。

### P0 — Critical（关键路径）

最高优先级的行动，基于 `/v4/decide` 引擎实时生成。

| 典型行动 | 触发条件 |
|---------|---------|
| Review Top Items | 总资产 > 0 |
| Level Characters | 存在未满级角色 |
| Complete Legendary | 传奇进度 > 50% |
| Equip Build | Build 就绪度 > 70% |

### P1 — Growth（成长路径）

| 典型行动 | 触发条件 |
|---------|---------|
| Start Goal | 已有目标但进度 < 50% |
| Build Toward | Build 就绪度 30-70% |
| Earn Gold | 流动资金 < 100g |

### P2 — Optional（可选优化）

日常优化建议：Complete Dailies、Check TP。

---

## 📆 Page 3: 成长路径 (Timeline)

### 7 天计划

每天一个明确的行动主题，附带进度条：

```
Day 1 → Sell & Liquidate     ░░░░░░░░
Day 2 → Goal Progress        █░░░░░░░
Day 3 → Build Gear           ██░░░░░░
Day 4 → Map Completion       ███░░░░░
Day 5 → Fractal Push         ████░░░░
Day 6 → WvW / PvP            █████░░░
Day 7 → Review & Plan        ██████░░
```

### Weekly Quests

7 个周常任务，点击即可勾选完成状态，跨会话持久化保存。

```
✅ Sell & Liquidate
⬜ Goal Progress
⬜ Build Gear
✅ Map Completion
⬜ Fractal Push
⬜ WvW / PvP
⬜ Review & Plan
```

顶部显示进度：`(3/7 43%)`

---

## 🧰 Page 4: 高级工具 (Tools)

所有高级功能收纳在此，点击卡片展开对应面板：

| 工具 | 说明 |
|------|------|
| **💰 Value Engine** | 三口径估值、资产构成饼图、Top 20 物品、材料分类 |
| **⚒ Crafting Calculator** | 配方树、已有材料抵扣、5 种优化策略、Shopping List |
| **🔍 Item Search** | 按名称/ID 搜索、市场深度、套利检测 |
| **⚔ Build Explorer** | 20 个 curated Build + Readiness Score |
| **🏆 Goals & Legendaries** | 13 个模板 + 进度追踪 + Planner |
| **👤 Characters** | 角色装备 + 衣柜 + Build Templates |
| **🪙 Wallet** | 金币、karma、各货币余额 |
| **👥 Guild Workspace** | 创建/加入公会、成员对比、职业覆盖 |
| **⚙ Settings** | 凭证管理 + 订阅 + Affiliate + 产品购买 |

---

## 🎯 策略系统

### 四种策略模式

| 模式 | 权重分配 | 适用场景 |
|------|---------|---------|
| **Balanced** | gold: 0.3 / build: 0.3 / leg: 0.3 | 默认均衡 |
| **Gold Farming** | gold: 0.6 / build: 0.1 / leg: 0.1 | 快速赚钱 |
| **Build Completion** | gold: 0.1 / build: 0.7 / leg: 0.1 | 组 Build |
| **Legendary Rush** | gold: 0.1 / build: 0.1 / leg: 0.6 | 做传奇 |

### 可解释评分

每个行动都有完整的评分拆解：

```
final_score =
    gold_gain × gold_weight
    + build_impact × build_weight
    + legendary_impact × legendary_weight
    + time_efficiency × time_weight
    - risk × risk_weight
    + liquidity_bonus
```

### 多路径优化

`/v4/optimize` 为每个目标生成三条优化路径：

| 路径 | 时间 | 成本 | 适合 |
|------|------|------|------|
| **Fast Path** | 14 天 | 2,500g | 有金币储备 |
| **Efficient Path** | 30 天 | 1,200g | 大多数玩家 |
| **Frugal Path** | 60 天 | 300g | 有时间但金币少 |

---

## 🧠 自进化学习

### v5 学习引擎

系统会记录你的每个行为，并不断调整策略权重：

```
你的行为 → 记录经验 → 计算奖励 → 更新权重 → 优化决策
```

### 个性化权重

每个用户有独立的 `user_models` 模型：

| 权重 | 默认值 | 学习方向 |
|------|--------|---------|
| gold_weight | 0.3 | 你赚金多 → 上升 |
| build_weight | 0.3 | 你做 Build 多 → 上升 |
| legendary_weight | 0.3 | 你做传奇多 → 上升 |
| time_weight | -0.2 | 你效率高 → 下降（惩罚减少）|
| risk_weight | -0.05 | 你冒险多 → 下降 |

### API 查看学习状态

```
GET /v5/model/{account_name}     → 你的完整用户模型
GET /v5/weights/{account_name}   → 你的个性化权重
GET /v5/experiences/{account}    → 你的历史行为记录
```

### 策略自动进化

`POST /v5/strategy/evolve` 会根据你的行为历史，自动推荐最适合你的策略模式。

---

## ❓ 常见问题

### 安全性

**Q: 我的 API Key 安全吗？**
A: ✅ Key 只在内存中使用，不写入日志。加密保存可选。可随时删除或撤销。

**Q: v5 学习系统会记录什么？**
A: 只记录你在系统内的操作（点击了哪个 Action、获得了多少金币等）。不会记录你的 GW2 密码或个人身份信息。

### 使用

**Q: 四个策略模式有什么区别？**
A: 它们改变的是 Action Center 中行动排序的权重。
- **Balanced**: 均衡推荐
- **Gold Farming**: 优先推荐赚钱行动
- **Build Completion**: 优先推荐组 Build
- **Legendary Rush**: 优先推荐传奇进度

**Q: 评分拆解中的数字是什么意思？**
A: 每个维度 0-1 之间的分数，乘以对应策略权重后求和得到最终评分。

**Q: 为什么有些物品显示 "Unpriced"？**
A: 缺少 `tradingpost` 权限或物品在交易所没有活跃订单。

### 自进化

**Q: 系统多久学习一次？**
A: 每次你与系统交互（点击 Action、记录经验）后立即更新。

**Q: 学习结果可以重置吗？**
A: 可以。删除 `user_models` 表中对应的记录即可重置为默认权重。

**Q: 学习会影响其他用户吗？**
A: 不会。每个用户的 `user_models` 完全独立。

---

## 📊 系统信息

| 项目 | 数值 |
|------|------|
| 版本 | v5 (自进化系统) |
| 测试 | 295 单元测试 + Playwright E2E |
| 路由 | 116 endpoints |
| 演进 | v1 排序 → v2 规划 → v3 Agent → v4 可解释 → v5 自进化 |
| 策略 | 4 种 (Balanced/Gold/Build/Legendary) |
| 学习 | 个性化权重自动调整 |
| 数据库 | SQLite WAL |
| CI/CD | GitHub Actions |
| 安全 | Fernet 加密 + CORS + 审计日志 |
