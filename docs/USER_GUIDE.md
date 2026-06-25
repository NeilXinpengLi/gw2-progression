# GW2 Progression OS — 专业玩家使用指南

> **目标驱动的 GW2 成长系统。**  
> 告诉系统你想要什么，它把你的账号数据转化为最优行动方案。

---

## 目录

1. [核心理念](#1-核心理念)
2. [快速开始](#2-快速开始)
3. [五个实战场景](#3-五个实战场景)
4. [深度理解你的方案](#4-深度理解你的方案)
5. [迭代修改：用自然语言调整](#5-迭代修改用自然语言调整)
6. [报告与导出](#6-报告与导出)
7. [高级工具](#7-高级工具)
8. [专业技巧](#8-专业技巧)

---

## 1. 核心理念

这不是传统的功能导航工具。你不需要在 "Value / Crafting / Goals / Build / Advisor" 之间来回切换。

**只需要说一句话：**

```
I want to finish Bolt in the cheapest way.
```

系统会自动：
1. 读取你的账号状态（金币、材料、银行、角色）
2. 识别目标类型和策略偏好
3. 生成 7 天渐进式行动方案
4. 允许你用自然语言继续修改
5. 支持导出报告

---

## 2. 快速开始

### 2.1 获取 API Key

访问 [ArenaNet Applications](https://account.arena.net/applications)，创建新 Key。

**必需权限：**

| 权限 | 用途 |
|------|------|
| `account` | 账号名称 |
| `characters` | 角色等级与装备 |
| `inventories` | 银行、材料、共享背包 |
| `wallet` | 金币与货币 |

**推荐额外开启：** `tradingpost`、`builds`、`progression`、`unlocks`

### 2.2 连接账号

1. 将 API Key 粘贴到首页输入框
2. 点击 **Connect & Analyze**
3. 系统自动拉取 16+ 个 GW2 API 端点

### 2.3 先试试 Demo

没有 API Key？点击 **"Try Demo"** 按钮：

```
系统展示示例账号 "DemoPlayer.1234"
→ 总价值 12,450g
→ 最佳目标：Bolt（67% 完成）
→ 推荐卖出 3 类高价值材料
→ 21 天 7 天行动方案
```

Demo 模式展示了完整的渐进式加载流程和方案界面，帮助你快速了解系统能力。

---

## 3. 五个实战场景

### 场景 1：完成传奇武器

```
"I want to finish Bolt"
```

系统响应：
```
你 67% 接近 Bolt
最省路线需要 21 天，约 830g
今天先做 3 件事：
1. 卖出 3 类高流动性材料 → +180g
2. Farm T4 Fractals → 预计 45g/天
3. 开始 Gift of Might 材料准备
```

### 场景 2：本周赚钱

```
"Make gold this week"
```

系统响应：
```
总赚钱潜力：~140g/周
推荐行动：
1. T4 碎层日常 + 推荐 → 20g/天
2. 日常成就 + 世界boss → 10g/天
3. TP 倒卖机会 → 额外收益
4. 清理材料库存 → 即时金币
```

### 场景 3：准备副本 Build

```
"I need a fractal-ready build"
```

系统响应：
```
检测到游戏模式：fractal
最佳 Build 匹配：Power Virtuoso（72% 就绪）
缺少 3 件装备，约 240g
推荐先去 T4 碎层获取 ascended 首饰
```

### 场景 4：清理背包

```
"Clean my inventory"
```

系统响应：
```
1. 分解所有 masterwork/rare 装备
2. 出售材料库存溢出（>250 堆叠）
3. 一键存入材料库
```

### 场景 5：制定周计划

```
"Plan my week"
```

系统响应：
```
Monday    卖出清理 + 整合金币
Tuesday   推进传奇材料
Wednesday 获取 Build 装备
Thursday  地图完成 + 货币收集
Friday    碎层冲刺
Saturday  WvW / PvP 奖励
Sunday    周回顾 + 下周规划
```

---

## 4. 深度理解你的方案

### 4.1 渐进式加载

提交目标后，系统分 4 阶段返回结果：

```
阶段 1 (1-3s)  账号名称、钱包金币、角色数
阶段 2 (3-8s)  总资产估值、隐藏财富、Top 10 资产
阶段 3 (8-15s) 最佳 Build、最近目标、首要行动
阶段 4 (15-30s) 完整方案、行动计划、7 天日程
```

每一步完成后界面自动更新，无需等待全部完成。

### 4.2 Insight 摘要

方案顶部显示关键摘要：

```
📊 INSIGHT
你 67% 接近 Bolt。钱包: 520g。
首要行动：卖出高价值材料。
```

附加快捷指标：
- 📅 方案总天数
- 💰 预估总成本
- 🎯 完成百分比
- ⚡ 当前策略

### 4.3 Top 3 行动

每条行动包含：
- **图标**：💰 卖出 / 🛒 买入 / 🔨 制作 / ⚔️ 刷金 / 🏆 成就
- **标题**：行动名称
- **理由**：为什么推荐这个
- **收益/成本**：金币影响
- **时间**：预计花费分钟数

### 4.4 7 天计划

按天分组的行动日程，每天最多 3 个行动：

```
Mon  卖出清理     Tue  传奇材料     Wed  装备获取
Thu  地图货币     Fri  碎层冲刺     Sat  WvW/PvP
Sun  回顾规划
```

### 4.5 策略选择

一键切换方案策略，系统重新排序所有行动：

| 策略 | 适用场景 | 效果 |
|------|----------|------|
| **Balanced** | 默认综合 | 均衡考虑金币/进度/Build |
| **Frugal** | 金币紧张 | 最小化金币支出，增加 farming 步骤 |
| **Fast** | 时间优先 | 最大化金币投入，缩短天数 |
| **Gold First** | 急需金币 | 优先高收益行动 |
| **Build First** | 装备优先 | 优先 Build 相关行动 |
| **Low Effort** | 休闲玩家 | 最小化每日花费时间 |

---

## 5. 迭代修改：用自然语言调整

这是系统最强大的功能。方案生成后，你可以随时用自然语言修改：

### 5.1 修改策略

```
"Make it cheaper"
```

系统响应：
```
策略从 Balanced → Frugal
变化：
- 总成本：1,200g → 420g
- 时间：14天 → 35天
- 新增 farming 步骤
- 减少 TP 购买
```

### 5.2 调整焦点

```
"Focus on gold"
"Focus on build"
```

系统重新计算所有行动评分，优先与焦点相关的行动。

### 5.3 排除内容

```
"Avoid WvW"
"No fractals"
"Without PvP"
```

系统移除所有涉及排除内容的行动。

### 5.4 设定时间预算

```
"I only have 1 hour per day"
"Only 30 minutes a day"
```

系统过滤超出时间预算的行动，保留最短的行动组合。

### 5.5 每次修改都有 Delta 摘要

系统会清晰展示修改前后的差异：

```
✅ Plan Updated
策略从 Balanced 调整为 Frugal
移除了 3 个涉及 WvW 的行动
总成本从 830g 降至 420g
时间从 21 天延长至 35 天
```

---

## 6. 报告与导出

### 6.1 免费报告

点击 **"Generate Report"** 生成基础报告：
- 账号摘要
- 价值概览
- 目标进度
- 创建时间

### 6.2 付费完整报告（$5）

购买后获得：
- 完整行动方案（含排序和评分）
- 7 天日程表
- Build 就绪度分析 + 缺口装备检测
- 目标进度详情
- 个性化建议
- HTML 报告预览（可打印/转 PDF）

### 6.3 周订阅（$5/月）

自动每周收到：
- 更新的 7 天行动方案
- 目标进度变化
- 市场信号更新
- Build 变化追踪

### 6.4 复制方案

点击 **"Copy Plan"** 将完整方案以文本格式复制到剪贴板：

```
GW2 Progression OS Plan
═══════════════════════════════
Account: Player.1234
Strategy: cheapest
Estimated: 21 days
...

TOP 5 ACTIONS:
1. Sell 3 high-value materials
   Generate liquid gold
   Reward: +180g
   Time: 15min
```

### 6.5 分享

点击 **"Share"** 通过 Web Share API 分享方案链接，或复制到剪贴板。

---

## 7. 高级工具

在 **Tools** 页面可以访问完整的传统功能套件：

| 工具 | 用途 |
|------|------|
| **Overview** | 账号总览卡片、权限网格 |
| **Coach** | P0/P1/P2 行动建议 + 周计划 |
| **Timeline** | 7 天成长路径 + 每周任务 |
| **Advanced** | 完整 15 个功能面板：价值/角色/Build/目标/背包/制作/市场等 |

---

## 8. 专业技巧

### 8.1 目标描述越具体越好

```
❌ "I need help"
✅ "I want to finish Bolt cheaply, only 1 hour per day"
```

包含目标物品、策略偏好、时间预算会让方案更加精准。

### 8.2 组合使用策略切换 + 自然语言修改

1. 先生成方案（默认 Balanced）
2. 点击 **"Frugal"** 切换到省钱模式
3. 输入 `"Avoid WvW"` 排除不想玩的内容
4. 输入 `"Only 1 hour per day"` 设时间预算

每一步系统都会展示变化摘要。

### 8.3 通过定价卡片购买完整报告

方案生成后，可以在 Report 页面查看定价：
- **Free**：基础报告 + 1 条行动建议
- **$5 Full Report**：完整行动方案 + Build 分析 + PDF
- **$5/mo Weekly**：自动更新 + 市场警报

购买流程：点击按钮 → 输入邮箱 → 支持 Stripe 信用卡或直接获取 License Key。

### 8.4 API Key 安全须知

- 🔒 系统**从不**请求 ArenaNet 密码
- 🔑 API Key 默认仅会话使用，不持久存储
- 🔄 随时可以在 [ArenaNet Applications](https://account.arena.net/applications) 撤销 Key
- 👁️ Key 只读，无法交易、删除物品、修改账号

---

> **版本：** 2.0.0（Goal-Driven OS）  
> **核心流程：** 目标输入 → 账号分析 → 方案生成 → 迭代修改 → 报告导出  
> **数据来源：** Guild Wars 2 API · 非 ArenaNet 官方产品
