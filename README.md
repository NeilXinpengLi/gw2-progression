# GW2 Progression — 用户指南

> **你的 Guild Wars 2 账号资产与成长助手。**  
> 输入 API Key，立刻了解账号价值、传奇目标进度、Build 可达性和成长建议。

---

## 📖 目录

1. [快速开始](#1-快速开始)
2. [账号估值](#2-账号估值)
3. [物品搜索](#3-物品搜索)
4. [制作计算器](#4-制作计算器)
5. [目标追踪与传奇规划](#5-目标追踪与传奇规划)
6. [Build 推荐](#6-build-推荐)
7. [成长 Agent](#7-成长-agent)
8. [公会空间](#8-公会空间)
9. [报告与导出](#9-报告与导出)
10. [设置与凭证](#10-设置与凭证)
11. [常见问题](#11-常见问题)

---

## 1. 快速开始

### 1.1 获取 API Key

1. 访问 [ArenaNet 应用管理](https://account.arena.net/applications)
2. 点击 **"Create New Key"**
3. 勾选以下权限（越多越好）：

| 权限 | 用途 | 不勾选的影响 |
|------|------|-------------|
| `account` | 账号名、世界、注册时间 | 无法识别你的账号 |
| `characters` | 角色装备、背包 | 无法计算角色资产和 Build |
| `inventories` | 银行、材料、共享背包 | 估值缺少 60%+ 的资产 |
| `wallet` | 金币和货币 | 缺少最直接的流动性资产 |
| `progression` | 成就、专精 | 无法分析传奇目标 |
| `builds` | Build 存储 | 无法做 Build 可达性 |
| `tradingpost` | 买卖订单 | 无法计算 TP 资产 |
| `unlocks` | 皮肤、染料 | 无法统计收藏 |
| `guilds` | 公会 | 公会分析需要（可选） |
| `pvp` | PvP 数据 | PvP 推荐不可用（可选） |
| `wvw` | WvW 数据 | WvW 推荐不可用（可选） |

4. 复制生成的 Key（以 `ABCDEF01-...` 格式）

### 1.2 开始分析

1. 在首页粘贴 API Key
2. 点击 **"Analyze"**
3. 观察进度条 — 系统会依次请求 15 个 GW2 API 端点
4. 完成后自动跳转到 Overview 面板

### 1.3 Quick Actions

分析完成后，Overview 面板顶部显示 Quick Actions：

| 卡片 | 点击效果 |
|------|---------|
| 📊 Export Report | 导出 JSON 报告 |
| 🪙 Wallet | 跳转 Wallet 标签 |
| 👤 Characters | 跳转角色列表 |
| 🎨 Wardrobe | 跳转衣柜 |
| 💰 Unpriced Items | 跳转物品搜索 |

---

## 2. 账号估值

**入口：Value 标签**

### 2.1 三个估值口径

| 口径 | 含义 | 典型用途 |
|------|------|---------|
| **Instant Sell** (即卖) | 按最高买价 × 0.85 | 你想立刻卖出的实际收入 |
| **Listing** (挂卖) | 按最低卖价 | 你挂交易所的理论收入 |
| **Net Sell** (净卖) | Listing − 15% 手续费 | 挂卖后的实际收入 |

### 2.2 资产构成

- **饼图**：资产按位置分布（银行、材料、角色、TP）
- **柱图**：各位置价值对比
- **折线图**：历史价值趋势（需要多次快照）

### 2.3 Top Items

按价值排序的前 20 件物品。每件物品显示：
- 名称与图标
- 持有数量
- 买价/卖价估值
- 定价状态（已定价 / 未定价 / 账号绑定）

### 2.4 价格质量

每件物品都有价格质量评分：

| 状态 | 含义 |
|------|------|
| ✅ Priced | 有完整买卖价格 |
| ❓ Unpriced | 缺少 TP 数据 |
| 🔒 Bound | 账号绑定 |
| 📊 Wide Spread | 买卖价差 > 20% |
| ⚠️ Low Liquidity | 交易量低 |

---

## 3. 物品搜索

**入口：Items 标签**

### 3.1 搜索

- 输入物品名称或 ID
- 支持按位置筛选（银行/材料/角色/共享/TP）
- 支持按状态筛选（已定价/未定价/绑定）

### 3.2 物品详情

点击搜索结果中的物品，查看：

| 区域 | 内容 |
|------|------|
| 总览 | 总数量、总买价、总卖价、状态 |
| 市场深度 | 最佳买价、最佳卖价、价差、买/卖深度、毛利 |
| 位置分布 | 每个位置的具体持有数量和估值 |
| 套利提示 | 如果存在套利空间会显示 |

---

## 4. 制作计算器

**入口：Crafting 标签**

### 4.1 基本使用

1. 输入目标物品 ID
2. 设置数量
3. 可选：勾选"Use Owned Materials"
4. 点击 Calculate

### 4.2 输出结果

| 区域 | 内容 |
|------|------|
| 费用对比 | 购买成本 vs 制作成本 |
| Shopping List | 需要购买的原材料清单 |
| Crafting Steps | 分步制作流程 |
| Missing Materials | 缺口材料明细 |
| Alternative Recipes | 替代配方列表 |

### 4.3 配方搜索

- 支持搜索物品名称找到对应 ID
- 制作前自动解析目标名称

---

## 5. 目标追踪与传奇规划

**入口：Goals 标签 + Planner 标签**

### 5.1 目标模板

系统内置 13 个传奇/升华目标模板：

| 模板 | 类型 | 难度 |
|------|------|------|
| Bolt | 传奇大剑 | 中等 |
| Twilight | 传奇大剑 | 中等 |
| Sunrise | 传奇大剑 | 中等 |
| The Bifrost | 传奇法杖 | 中等 |
| Frostfang | 传奇斧 | 中等 |
| Incinerator | 传奇匕首 | 中等 |
| Nevermore | 传奇法杖 | 困难 |
| Astralaria | 传奇斧 | 困难 |
| Ad Infinitum | 传奇背部 | 困难 |
| Vision | 传奇戒指 | 困难 |
| Aurora | 传奇饰品 | 困难 |
| Zojja's Greatsword | 升华大剑 | 简单 |
| Berserker Armor | 升华护甲 | 中等 |

### 5.2 追踪目标

1. 在 Goals 标签点击 **Create Goal**
2. 选择模板或自定义目标
3. 系统自动计算已完成材料百分比
4. 每次分析自动刷新进度

### 5.3 Planner 规划

Planner 标签提供：
- 模板选择下拉
- 目标成本估算
- 材料清单
- 阻塞项链检测

---

## 6. Build 推荐

**入口：Builds 标签**

### 6.1 分析流程

1. 在 Builds 标签点击 **"Analyze Build Readiness"**
2. 系统将 20 个 curated Build 与你的账号对比
3. 按 Readiness Score 排序展示最接近的 Build

### 6.2 Build Readiness 指标

| 指标 | 说明 |
|------|------|
| Readiness Score | 0-100%，装备匹配度 |
| Missing Items | 还缺多少件装备 |
| Missing Cost | 补齐缺口的大致成本 |
| Profession Match | 你是否有该 Build 的职业 |

### 6.3 Curated Builds

覆盖 9 个职业、20 个 Build：

| 职业 | Build 数量 |
|------|-----------|
| Guardian | 3 (Power DH, Condi FB, Heal FB) |
| Warrior | 2 (Power Berserker, Condi Berserker) |
| Revenant | 2 (Power Vindicator, Condi Renegade) |
| Ranger | 2 (Power Soulbeast, Condi Soulbeast) |
| Thief | 2 (Power Daredevil, Condi Specter) |
| Engineer | 2 (Power Holo, Condi Mech) |
| Necromancer | 2 (Power Reaper, Condi Scourge) |
| Elementalist | 2 (Power Tempest, Condi Weaver) |
| Mesmer | 2 (Power Virtuoso, Condi Mirage) |
| 其他 | 1 (Heal Scourge) |

---

## 7. 成长 Agent

**入口：Advisor 标签**

Agent 会综合以下数据生成个性化建议：

| 数据来源 | 用途 |
|---------|------|
| 账号价值 | 总资产、流动性、风险资产 |
| 目标进度 | 最接近完成的目标 |
| Build 可达性 | 最匹配的 Build |
| TP 信号 | 推荐买卖的物品 |
| LLM (可选) | 自然语言总结（需配置 API Key） |

点击 **"Generate Advice"** 获取 7 天周计划。

---

## 8. 公会空间

**入口：Guild 标签**

### 8.1 创建公会

1. 输入公会名称
2. 点击 **Create Guild**
3. 系统生成邀请码，分享给成员

### 8.2 加入公会

1. 输入邀请码
2. 点击 **Join Guild**
3. 你的账号数据会加入公会聚合视图

### 8.3 公会聚合

| 指标 | 说明 |
|------|------|
| 成员数 | 公会成员数量 |
| 总金币 | 所有成员的 wallet 总和 |
| 总角色数 | 所有成员的角色数量 |
| 总皮肤数 | 所有成员的皮肤解锁总数 |
| 职业分布 | 各职业的成员数量 |

---

## 9. 报告与导出

**入口：Overview 标签 → Export Report**

### 9.1 生成报告

1. 完成账号分析
2. 点击 **Export Report**
3. 浏览器下载 JSON 格式报告文件

### 9.2 报告内容

报告包含：
- 账号基本信息
- 总价值和分类价值
- Top 10 最有价值物品
- 报告生成时间

### 9.3 报告历史

完成分析后，Overview 页面显示历史报告列表。

---

## 10. 设置与凭证

**入口：Settings 标签**

### 10.1 LLM Provider

可选的 AI 能力配置：

| Provider | 用途 |
|---------|------|
| OpenAI | 报告生成、Advisor 建议 |
| Anthropic | 报告生成、Advisor 建议 |
| DeepSeek | 报告生成、Advisor 建议 |
| Ollama (Local) | 本地运行，无需 API Key |

### 10.2 凭证安全

所有 API Key：
- 使用 Fernet 加密存储
- 只显示最后 4 位字符
- 支持随时删除
- 默认 session-only（不保存）

### 10.3 周报订阅

| 功能 | 说明 |
|------|------|
| 订阅 | 输入邮箱，每周收到账号更新 |
| 周报内容 | 价值变化、目标进度、Build 更新 |
| 取消订阅 | 随时可取消 |

### 10.4 Affiliate 推荐

1. 在 Settings 创建你的 Referral Code
2. 分享给其他玩家
3. 他人购买时使用你的 Code，你获得佣金

---

## 11. 常见问题

### 我的 API Key 安全吗？

- ✅ Key 只在内存中使用
- ✅ 加密存储（可选保存）
- ✅ 不在日志中记录
- ✅ 不支持 ArenaNet 密码
- ✅ 随时可以删除或撤销

### 哪些权限必须勾选？

**最小推荐**: `account` + `inventories` + `characters` + `wallet`  
**完整功能**: 加上 `tradingpost` + `progression` + `builds` + `unlocks`

### 为什么有些物品显示 ❓ Unpriced？

这些物品在交易所没有活跃订单，无法自动估值。常见原因：
- 极稀有物品（很少交易）
- 账号绑定物品（无法交易）
- 需要 `tradingpost` 权限

### 制作计算提示 "No recipe found"？

- 确认物品 ID 正确
- 该物品可能没有已知配方
- 部分一代传奇需要先在 GW2 中解锁配方

### Build 推荐没有结果？

- 确认 API Key 包含 `characters` 权限
- 系统需要至少一个 80 级角色
- Build 数据基于装备 ID 匹配，非职业名称

### Agent 建议是空的？

Agent 需要以下数据之一：
- 有目标的 Goals
- Build Readiness 结果
- TP 信号
- LLM API Key（可选，用于自然语言总结）

---

## 技术信息

| 项目 | 值 |
|------|-----|
| 测试 | 269 单元测试 + 11 E2E |
| CI | GitHub Actions |
| 部署 | Docker + nginx |
| 数据 | SQLite WAL |
| License | MIT |
