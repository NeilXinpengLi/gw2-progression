# GW2Radar / AegisRadar 可上线系统架构设计（Production MVP）

> 版本：v1.0 Production Architecture  
> 目标：从“技术原型 + 信任体系”升级为“可上线 SaaS + BYOK + 报告商业闭环系统”  
> 适用：GW2Radar / AegisRadar / AetherTwin / EnvConsole

---

# 1. 总体目标

当前系统已经具备：

- GW2 API 全量接入
- 账号价值计算
- Crafting / Goal / Build 系统
- Credential / BYOK 信任设计

下一阶段目标：

> **让系统具备真实可上线能力：用户注册 → 输入 Key → 生成报告 → 付费 → 订阅 → 周报 → 留存**

---

# 2. 系统总体架构（Production SaaS）

```
┌──────────────────────────────────────────────┐
│                Frontend (Next.js / SPA)     │
│  - Dashboard                                │
│  - Reports                                  │
│  - Credential Center                       │
│  - Subscription UI                         │
└──────────────────────┬──────────────────────┘
                       │ HTTPS
                       ▼
┌──────────────────────────────────────────────┐
│               API Gateway (FastAPI)          │
│  - Auth / Session                          │
│  - Rate Limit                              │
│  - Billing Guard                           │
│  - Request Router                          │
└──────────────┬───────────────┬──────────────┘
               │               │
               ▼               ▼
┌──────────────────┐   ┌──────────────────────┐
│ GW2Radar Engine  │   │ AegisRadar Engine    │
│ - Value Engine   │   │ - Market Intelligence│
│ - Crafting       │   │ - Competitive Graph  │
│ - Build System   │   │ - SKU Analysis       │
└────────┬─────────┘   └─────────┬────────────┘
         │                       │
         ▼                       ▼
┌──────────────────────────────────────────────┐
│         Credential & BYOK Layer              │
│  - GW2 API Key                              │
│  - LLM Providers                            │
│  - Search / Commerce APIs                   │
│  - Encryption / Vault                      │
│  - Usage Audit                             │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│        Data Layer (PostgreSQL + Redis)       │
│  - Snapshots                                │
│  - Price Cache                              │
│  - Reports                                  │
│  - Goals                                    │
│  - Builds                                   │
│  - Credentials                              │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│      External APIs (BYOK + Platform APIs)    │
│  - GW2 API                                  │
│  - OpenAI / Claude / DeepSeek              │
│  - Google / SerpAPI                        │
│  - Amazon / Walmart                        │
│  - Map Providers                          │
└──────────────────────────────────────────────┘
```

---

# 3. 核心数据流（User Journey）

## 3.1 用户主流程

```
User Visit
   ↓
Landing Page (Report Product)
   ↓
Purchase / Free Tier
   ↓
Login / Session
   ↓
Input GW2 API Key
   ↓
Permission Explain UI
   ↓
Select Mode:
   - Session-only
   - Save encrypted
   ↓
Run Analysis Engine
   ↓
Generate:
   - Value Report
   - Crafting Report
   - Build Report
   - Goal Report
   ↓
Dashboard View
   ↓
Download PDF
   ↓
Email Delivery
   ↓
Weekly Subscription (optional)
```

---

## 4. Credential / BYOK 架构（核心）

```
┌────────────────────────────┐
│ Credential Center          │
├────────────────────────────┤
│ GW2 API Key               │
│ LLM Providers             │
│ Search Providers          │
│ Commerce APIs             │
└────────────┬──────────────┘
             ▼
┌────────────────────────────┐
│ Credential Vault          │
│ - Encrypted Storage       │
│ - Fingerprint Hash        │
│ - Rotation Support        │
│ - Audit Logs             │
└────────────┬──────────────┘
             ▼
┌────────────────────────────┐
│ Credential Runtime Layer  │
│ - Session-only mode       │
│ - Persistent mode         │
│ - Team workspace mode     │
└────────────────────────────┘
```

---

# 5. 报告生成系统（核心商业能力）

## 5.1 Report Pipeline

```
Input:
  - API Key
  - User Intent
  - Product Type

↓

Step 1: Data Fetch
  - GW2 API
  - Price API
  - Build data

↓

Step 2: Analysis Engine
  - Value calculation
  - Crafting optimization
  - Goal evaluation
  - Build readiness

↓

Step 3: Intelligence Layer
  - Recommendations
  - Risk detection
  - Opportunity detection

↓

Step 4: Report Generator
  - PDF
  - Dashboard JSON
  - CSV export

↓

Step 5: Delivery
  - Email
  - Web dashboard
  - Share link
```

---

# 6. 产品化系统（Gumroad式）

## 6.1 产品模型

```
Product
- Account Value Report
- Legendary Gap Report
- Build Readiness Report
- Weekly Progression Report
- Market Intelligence Pack (AegisRadar)
```

## 6.2 交付模型

```
Order → License → DeliveryJob → ReportArtifact → Access
```

---

## 6.3 订阅模型

```
Free:
- One-time report preview

Pro:
- Full report
- History
- Weekly update

Team:
- Multi-account
- Guild analytics
- Shared dashboard
```

---

# 7. 安全架构（Trust Layer）

## 7.1 三层模型

```
Layer 1: UI Trust
- Permission explanation
- Transparent usage
- Mode selection

Layer 2: System Security
- AES encryption
- Session-only execution
- Audit logs
- Key isolation

Layer 3: External Trust
- SOC2-ready design
- Privacy policy
- No key leakage guarantee
```

---

## 7.2 Key 生命周期

```
Create → Validate → Use → Audit → Rotate → Delete
```

---

# 8. 数据层设计

## 8.1 PostgreSQL Core Tables

```
users
workspaces
credentials
snapshots
reports
goals
builds
orders
licenses
usage_logs
```

---

## 8.2 Redis Layer

```
- price cache
- session cache
- rate limit
- temporary analysis results
```

---

# 9. Agent & Intelligence Layer

## 9.1 Progression Agent

```
Inputs:
- Account snapshot
- Goals
- Builds
- Market signals

Outputs:
- next actions
- weekly plan
- warnings
- opportunities
```

---

## 9.2 Agent Pipeline

```
Data → Context Builder → Reasoning Engine → Action Planner → Report Output
```

---

# 10. 前端系统（SaaS UI）

## 页面结构

```
/dashboard
/value
/items
/crafting
/goals
/builds
/reports
/advisor
/settings/credentials
/settings/billing
```

---

## 核心组件

```
ValueDashboard
GoalTracker
CraftingPlanner
BuildRecommender
ReportViewer
CredentialCenter
SubscriptionPanel
```

---

# 11. 商业闭环（最关键）

## 11.1 完整闭环

```
Traffic
  ↓
Landing Page
  ↓
Report Product Page
  ↓
Payment
  ↓
API Key Input
  ↓
Analysis Engine
  ↓
Report Generation
  ↓
Delivery (PDF + Dashboard)
  ↓
Weekly Subscription
  ↓
Retention Loop
```

---

## 11.2 收入模型

```
One-time Report: $5–$49
Subscription: $5–$20/month
Guild Plan: $49–$199/month
Enterprise (AegisRadar): $99–$999/month
```

---

# 12. 技术栈建议

```
Frontend:
- Next.js / React
- Tailwind

Backend:
- FastAPI
- Async worker

DB:
- PostgreSQL
- Redis

Storage:
- S3 / Object storage

Worker:
- Celery / RQ

Auth:
- JWT + Workspace model
```

---

# 13. MVP上线路径（关键）

## Phase 1（2–3周）

```
- GW2 API Key input
- Value report
- PDF export
- Session-only BYOK
```

---

## Phase 2（3–6周）

```
- Credential Center
- Encrypted key storage
- Report templates
- Share links
```

---

## Phase 3（6–10周）

```
- Subscription
- Weekly reports
- Goal tracking
- Build recommendation
```

---

## Phase 4（扩展）

```
- AegisRadar 接入
- Team workspace
- Marketplace
- Affiliate system
```

---

# 14. 最终架构定位

系统最终会演化为：

> **BYOK + 证据化分析 + 报告交付 + 订阅留存 + 智能 Agent 的垂直 SaaS 平台**

而不是单纯：

> GW2 工具 / API Viewer

---

# 15. 一句话总结

> 从“工具系统” → “报告系统” → “订阅系统” → “智能决策系统”
