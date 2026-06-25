# GW2 Progression OS — 玩家成长指南

> **目标驱动的 GW2 成长系统。**  
> 新手、回归玩家、传奇党、Build 玩家、经济玩家都可以用。

---

## 快速入口：你是哪类玩家？

- [🆕 新手](#3-新手路线--第一次用gw2-progression-os)
- [🔄 回归玩家](#4-回归玩家路线--一段时间没玩了)
- [⚔️ 传奇党](#5-传奇党路线--我要做传奇)
- [🛡️ PvE 玩家](#6-pve-玩家路线--我要打碎层raidstrike)
- [💰 经济玩家](#7-经济玩家路线--我要赚钱)
- [😌 休闲玩家](#8-休闲玩家路线--每天30分钟)
- [🏢 公会管理者](#9-公会管理者路线--团队成长)

---

## 🚀 30 秒版

```
不知道做什么？  输入 Plan my week
想做传奇？     输入 I want to finish Bolt
想赚钱？       输入 Make gold this week
想打副本？     输入 I need a fractal-ready build
回归玩家？     输入 I came back after a long break
没有 API Key？ 点击 Try Demo
```

---

## 1. 这是什么？

一句话：**告诉系统你想要什么，它自动生成行动方案。**

不再需要在 `Value / Crafting / Goals / Build / Advisor` 之间切换。

```
I want to finish Bolt in the cheapest way.
```

系统自动：
1. 读取你的账号（金币、材料、银行、角色）
2. 识别目标类型（传奇/赚钱/Build/整理背包）
3. 生成 7 天行动方案
4. 让你用自然语言继续调整
5. 支持导出报告

---

## 2. 3 分钟开始

### 2.1 获取 API Key

访问 [ArenaNet Applications](https://account.arena.net/applications)，创建新 Key。

**必需权限：** `account`、`characters`、`inventories`、`wallet`  
**推荐：** `tradingpost`、`builds`、`progression`、`unlocks`

### 2.2 连接账号

1. 粘贴 API Key 到首页 → 点击 **Connect & Analyze**
2. 系统自动拉取 16+ 个 GW2 API 端点
3. 看到你的账号总览

### 2.3 先试 Demo

没有 Key？点击 **"Try Demo"** → 立刻看到示例方案，无需任何凭证。

### 2.4 输入第一个目标

在输入框输入：

```
Plan my week
```

或点击任一快速目标卡片。系统分 4 阶段返回结果：

```
阶段 1 (1-3s)   账号名称、钱包、角色数
阶段 2 (3-8s)   总资产估值、隐藏财富
阶段 3 (8-15s)  最佳 Build、最近目标
阶段 4 (15-30s) 完整方案 + 7 天日程
```

---

## 3. 新手路线 — 第一次用 GW2 Progression OS

### 适合你吗？

- 刚开始玩 GW2 不久
- 不知道每天该做什么
- 背包和材料库很乱
- 看到"T4 Fractals""Mystic Forge"等术语不太熟悉

### 推荐的第一个目标

```
"Plan my week"
```

系统会给你一个简单的 7 天计划，不需要理解复杂概念。

### 进阶

```
"Clean my inventory"
"Make gold"
"What should I do today?"
```

> 💡 **小提示：** 暂时不用看"策略切换"和"高级工具"。先用"Plan my week"建立节奏。

### 术语参考

| 术语 | 说明 |
|------|------|
| **T4 Fractals** | 最高难度的碎层副本，稳定金币来源 |
| **TP** | Trading Post（交易行） |
| **Build** | 角色技能/装备配置 |
| **Ascended** | 橙色品质装备，最高属性 |
| **Legendary** | 紫色品质，可免费切换属性的装备 |

---

## 4. 回归玩家路线 — 一段时间没玩了

### 适合你吗？

- 退坑几个月或几年
- 包里一堆东西不知道值不值钱
- 不知道现在流行什么 Build
- 不知道先做什么目标

### 🔥 推荐入口：Returning Player Audit

这是系统目前最强大的场景之一。点击 **Home 页的 "Returning Player" 卡片**，或直接输入：

```
I came back after a long break, tell me what to do first
```

系统会执行一次完整的回归审计：

```
📋 RETURNING PLAYER AUDIT

1. 🛡️ Build 评估
   - 当前 Build vs SnowCrows/MetaBattle 最新数据
   - 来源: verified · 角色: DPS / Heal / Alac / Quick
   - 状态: 过时 / 部分匹配 / 已验证

2. 💰 资产审计
   - 账号总价值
   - 隐藏财富（未定价物品 + 供应商价值）
   - 高价值旧物品检测

3. 🧹 背包清理
   - 可清理的物品和材料
   - 有价值的旧收藏品

4. 🎯 最近目标
   - 最接近完成的传奇
   - 剩余成本和天数

5. 💳 金币重建（如需要）
   - 每日推荐收入路径
```

### 你还可以

```
"Check my old build"         → Build 过时检测
"What's changed since I left" → 版本变化概览
"Audit my inventory"          → 资产清理清单
```

> 💡 **小提示：** 回归玩家是系统价值最高的用户群之一。你的旧账号可能隐藏着你没意识到的财富。先用 Returning Player Audit 全面评估，再决定长期目标。

---

## 5. 传奇党路线 — 我要做传奇

### 适合你吗？

- 正在做或计划做传奇武器/首饰/护甲
- 想知道还差多少材料/金币
- 想选最省钱或最快的路线

### 推荐输入

```
"I want to finish Bolt"
"I want to finish Bolt in the cheapest way"
"I want to finish Twilight as fast as possible"
```

系统输出：

```
📊 INSIGHT
你 67% 接近 Bolt。最省路线需要 21 天，约 830g。

Materials:    72%   Currency:    40%
Achievement: 100%   Time-gated:  30%

Top 3 Actions:
1. 卖出 3 类高流动性材料 → +180g
2. Farm T4 Fractals → 预计 45g/天
3. 开始 Gift of Might 材料准备
```

### 调整方案

```
"Make it cheaper"       → 切换到 cheapest 策略
"Focus on gold"         → 优先赚钱步骤
"I only have 1 hour"    → 过滤超时行动
"Avoid WvW"             → 排除 WvW 相关内容
```

> 💡 **小提示：** 传奇完成度拆分为 4 个维度——材料、货币、成就、时间门控，让你更清楚瓶颈在哪。

### 完成度如何计算

很多玩家问："67% 是怎么算的？是不是只看金币？"

**不是。** 系统按 4 个维度独立计算再综合：

| 维度 | 说明 | 示例 |
|------|------|------|
| **Materials** | 可交易材料的持有量 vs 需求量 | 你拥有 180/250 T6 Claws = 72% |
| **Currency** | 钱包金币 + 地图货币 | 你持有 500g，需要 1200g = 42% |
| **Achievement** | 成就/收藏步骤完成情况 | 3/3 前置收藏完成 = 100% |
| **Time-gated** | 每日/每周限量的材料 | 你有 60/100 Mystic Coins = 60% |

**为什么不是简单的金币估算？**  
因为纯金币估算会忽略账号绑定材料、成就阻塞和时间门控。一个目标可能只需要 200g，但如果差 40 个 Mystic Clover（时间门控 40 天），实际等待时间比金币成本更重要。

### 系统会识别的特殊阻塞

```
✅ 可交易材料     → 可从 TP 直接购买
✅ 账号绑定材料   → 必须用对应角色获取
⏳ 时间门控材料   → 每日/每周限量（Mystic Coin、Crystalline Ore）
🏆 成就阻塞      → 必须先完成前置收藏
⚔️ WvW 阻塞      → 需要 Gift of Battle（WvW 奖励）
🔄 PvP 阻塞      → 需要特定 PvP 奖励
🎁 特殊组件      → Mystic Clover、Gift of Mastery 等组合组件
```

系统会在方案中标注哪些阻塞当前无法通过金币解决，哪些只能等待。

---

## 6. PvE 玩家路线 — 我要打碎层/Raid/Strike

### 适合你吗？

- 想进入高难度 PvE 内容
- 需要一个经过验证的 meta Build
- 想知道还缺什么装备、花多少钱

### 推荐输入

```
"I need a fractal-ready build"
"I want a raid-ready Heal Alac build"
"Prepare a strike build for me"
```

系统输出：

```
🎯 Best Build: Power Virtuoso
Source: SnowCrows (verified)
Mode: Fractal
Readiness: 72%
Missing: 3 items (~240g)

Top Actions:
1. 装备 Power Virtuoso（碎层）
2. 购买缺失装备
3. 通过 T4 碎层获取 ascended 首饰
```

### Build 信任标记

每条 Build 推荐显示来源和版本：

```
✅ Source: SnowCrows
✅ Patch: 2026-xx
✅ Role: DPS / Heal / Quick / Alac
✅ Mode: Fractal / Raid / Strike
```

> 💡 **小提示：** 如果你需要特定角色（Heal/Quick/Alac），在目标中注明即可。

---

## 7. 经济玩家路线 — 我要赚钱

### 适合你吗？

- 想知道账号总价值
- 想找到被低估的资产
- 想做 TP 倒卖
- 想优化每周收入

### 推荐输入

```
"Make gold this week"
"How much is my account worth"
"Find sell candidates"
```

系统输出：

```
💰 Total earning potential: ~140g/week
💎 Hidden wealth: 890g（未充分利用资产）
💰 Wallet: 45g

Top Actions:
1. T4 碎层日常 + 推荐 → ~140g/周
2. 日常成就 + 世界Boss → ~70g/周
3. TP 倒卖机会检测
4. 清理材料库存 → 即时现金
```

### 价值如何计算

```
Instant Sell Value = highest buy order × 0.85（-15% TP fee）
Listing Value     = lowest sell listing
Net Sell Value    = listing × 0.85
Liquidity         = buy volume + sell volume（高/中/低/无）
Spread            = sell price - buy price
TP Opportunity    = spread after fee > threshold
```

> 💡 **小提示：** 系统默认用 Instant Sell 口径（最保守），确保你不会高估资产。

### 经济模型设置

| 参数 | 值 | 说明 |
|------|-----|------|
| TP 手续费 | 15% | 卖出时扣除的标准交易税 |
| 价格刷新频率 | 每 15 分钟 | TP 缓存自动更新 |
| 低流动性阈值 | buy + sell volume < 100 | 低于此值标记为低流动性 |
| 价差阈值（TP 机会） | spread 比例 > 15% | 扣除手续费后有套利空间 |
| 套利检测 | 买一价 vs 卖一价 | 扣除 15% 手续费后仍有正利润 |
| 数据来源 | GW2 API /v2/commerce/prices | 官方实时数据 |

**什么是低流动性？**  
如果某个物品的买入+卖出总量 < 100，系统会标记为"低流动性"。它可能显示高价值，但实际难以快速卖出。系统在估值时会降低这类资产的权重。

**什么是 TP 机会？**  
当买一价和卖一价的差价 > 15%（扣除手续费后仍有正利润），系统标记为 TP 机会。但请注意：套利需要资本和耐心，不一定适合所有玩家。

### CSV 导出

当前支持的导出格式：
- **Copy Plan** — 文本格式，可粘贴到任何应用
- **HTML 报告** — 付费报告可保存为 HTML，支持打印/转 PDF
- **CSV 导出** — 计划中，后续版本提供

---

## 8. 休闲玩家路线 — 每天 30 分钟

### 适合你吗？

- 每天只有少量时间玩游戏
- 不想高压力内容
- 想要简单、稳定的成长路径

### 推荐输入

```
"Plan my week"
"I only have 30 minutes a day"
```

系统自动切换到 **Low Effort** 策略，每天行动不超过你的时间预算。

### 推荐策略

```
"Plan my week"     
→ 切换到 "Low Effort" 策略
→ 或输入 "I only have 1 hour per day"
```

### 快速目标

```
"Clean my inventory"
"Make gold"
"Plan my week"
```

> 💡 **小提示：** 如果某天没时间，跳过即可。系统不会因为你跳过行动而惩罚你。

---

## 9. 公会管理者路线 — 团队成长

### 适合你吗？

- 管理公会，想了解成员成长情况
- 想知道谁缺什么 Build 角色
- 想制定公会周计划

### 当前主版本的个人模式

GW2 Progression OS **当前版本主要面向个人成长**。如果你需要团队管理能力，目前可以：

- **分享方案** — 生成方案链接发给成员
- **报告导出** — 生成 HTML 报告分享给团队
- **付费周报** — 订阅账号进度更新

### 推荐的用法

```
"Plan my week" → 导出报告 → 分享给公会频道
"Check build" → 查看成员 Build 就绪度 → 一对一指导
```

### 公会管理者目前还不能做的事

```
❌ 批量查看所有成员的 Build coverage
❌ 团队 Role gap 分析（谁缺 heal/quick/alac）
❌ 成员进度横向对比
❌ 自动推荐替补阵容
```

> 📌 **Guild Edition（独立版本）：**  
> 完整的公会管理功能正在独立开发中，包括 Build coverage 矩阵、Role gap 检测、成员总览仪表盘、团队周计划生成器。  
> 如果你有公会管理需求，当前版本适合先用个人报告 + 分享功能做轻量管理，完整功能将在 Guild Edition 中提供。

---

## 10. 如何相信系统

### API Key 安全

| 问题 | 回答 |
|------|------|
| 需要我的 ArenaNet 密码吗？ | **从不** |
| Key 保存在哪里？ | 默认仅会话使用，不保存到磁盘 |
| 可以撤销 Key 吗？ | 随时在 ArenaNet Applications 撤销 |
| 能修改我账号吗？ | **不能**，Key 只读 |
| 分享链接会暴露我账号吗？ | 默认匿名，隐藏账号名 |

### 隐私模式

```
🟢 Session Mode（默认）：Key 仅内存使用，关闭即丢弃
🟡 Saved Mode（可选）：加密保存 Key，用于周报自动更新
🔵 Share Mode：匿名分享，隐藏账号名和完整资产明细
```

### 数据来源

- 所有数据来自 **Guild Wars 2 官方 API**
- Build 模板来源：**SnowCrows**（Raid）和 **MetaBattle**（开放世界/ fractals）
- 价格数据：**GW2 交易行实时数据**
- 估值口径：**Instant Sell / Listing / Net Sell 三口径**

---

## 11. 免费与付费区别

| 功能 | Free | Full Report ($5) | Weekly ($5/月) |
|------|------|-----------------|--------------|
| 目标解读 | ✅ | ✅ | ✅ |
| 方案生成 | ✅ | ✅ | ✅ |
| 自然语言修改 | ✅ | ✅ | ✅ |
| 策略切换 | ✅ | ✅ | ✅ |
| 7 天计划 | ✅ | ✅ | ✅ |
| 行动排序 | 3 条 | 全部 | 全部 |
| Build 分析 | — | ✅ | ✅ |
| Crafting 路径 | — | ✅ | ✅ |
| HTML 报告 | — | ✅ 可转 PDF | ✅ 可转 PDF |
| 每周自动更新 | — | — | ✅ |
| 市场警报 | — | — | ✅ |
| 进度追踪 | — | — | ✅ |

---

> **版本：** 2.0.0（Goal-Driven OS）  
> **核心流程：** 目标输入 → 账号分析 → 方案生成 → 迭代修改 → 报告导出  
> **数据来源：** Guild Wars 2 API · 非 ArenaNet 官方产品
