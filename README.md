# GW2 Progression

> **GW2 账号资产智能系统** — 对标 gw2efficiency 的账号价值计算、制作成本联动、Build 推荐、成长规划工具。

[![CI](https://github.com/NeilXinpengLi/gw2-progression/actions/workflows/ci.yml/badge.svg)](https://github.com/NeilXinpengLi/gw2-progression/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green)
![Tests](https://img.shields.io/badge/tests-159-brightgreen)
![Maturity](https://img.shields.io/badge/maturity-A--level-orange)

---

## 功能速览

| 模块 | 功能 | 状态 |
|------|------|------|
| **账号估值** | 6 种持仓归一化, 三口径估值 (Instant/Listing/Net Sell), 价格质量评分 | ✅ |
| **数据可视化** | 资产构成饼图, 位置柱图, 趋势折线图, 历史对比 | ✅ |
| **物品搜索** | 按名称/ID 搜索, 位置钻取, 市场深度, 套利检测 | ✅ |
| **制作计算** | 配方树展开, 已有材料抵扣, 5 种优化策略, 防循环 | ✅ |
| **目标追踪** | 创建/刷新/删除目标, 完成百分比, 剩余成本 | ✅ |
| **传奇规划** | 8 个模板 (Bolt/Twilight/Nevermore/Astralaria/Ad Infinitum/Vision), 需求映射 | ✅ |
| **Build 推荐** | 20 个 curated Build (SnowCrows + MetaBattle), readiness 评分 | ✅ |
| **市场策略** | Sell/Buy 信号, 流动性警告, 受保护资产 | ✅ |
| **成长 Agent** | 聚合分析, 行动建议, 7 天周计划 | ✅ |
| **TP 订单簿** | /v2/commerce/listings, 市场深度, 套利分析 | ✅ |

---

## 快速开始

### 前置条件

- Python 3.12+
- GW2 API Key ([获取](https://account.arena.net/applications))

### 本地运行

```bash
# 安装依赖
pip install -e ".[dev]"

# 启动服务
uvicorn gw2_progression.api.main:app

# 打开浏览器 http://localhost:8000
```

### Docker 运行

```bash
docker compose up -d

# 查看健康状态
docker compose ps

# 自定义端口
PORT=8080 docker compose up -d
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | `8000` | HTTP 端口 |
| `RATE_LIMIT_REQUESTS` | `30` | 每分钟每 IP 请求上限 |
| `RATE_LIMIT_WINDOW` | `60` | 速率窗口 (秒) |
| `GW2_API_BASE` | `https://api.guildwars2.com` | GW2 API 地址 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

---

## 项目结构

```
src/gw2_progression/
├── api/                    # FastAPI 路由层 (11 路由模块)
│   ├── main.py             # 入口 + 中间件 (logging, rate-limit, session)
│   └── routes/
│       ├── analyze.py      # POST /analyze
│       ├── resolve.py      # POST /resolve (GW2 静态数据代理)
│       ├── valuation.py    # /value/* (21 端点)
│       ├── crafting.py     # /crafting/* (10 端点)
│       ├── goals.py        # /goals/* (5 端点)
│       ├── progression.py  # /progression/* (3 端点)
│       ├── builds.py       # /builds/* (4 端点)
│       ├── tp_strategy.py  # /tp/* (6 端点)
│       └── agent.py        # /agent/* (2 端点)
├── services/               # 业务逻辑层 (22 服务)
│   ├── gw2_client.py       # GW2 HTTP 客户端 (22 fetch_*)
│   ├── analyzer.py         # 分析编排 + AccountContents
│   ├── price_service.py    # 市场价格 + 价格质量
│   ├── valuation_service.py# 估值引擎
│   ├── holdings_service.py # 持仓归一化
│   ├── recipe_service.py   # 配方引擎
│   ├── recipe_optimizer.py # 多策略配方优化
│   ├── delta_service.py    # 快照差分
│   ├── listing_service.py  # TP 订单簿
│   ├── build_service.py    # Build 推荐
│   ├── agent_service.py    # 成长 Agent
│   └── ...
├── models.py               # 40+ Pydantic 数据模型
├── database.py             # SQLite + 连接池 + 归档
└── static/                 # 前端 SPA (7 JS 模块)
    ├── index.html          # 18 Tab 面板
    ├── app.js              # 核心 (caches, resolve, analyze)
    ├── app-value.js        # 价值 Dashboard
    ├── app-characters.js   # 角色/衣柜/背包/专精/Builds
    ├── app-items.js        # 物品搜索
    ├── app-crafting.js     # 制作计算
    ├── app-goals.js        # 目标追踪
    ├── app-planner.js      # Planner/Builds/Market/Advisor
    └── style.css           # 响应式样式
```

---

## API 概览 (40+ 端点)

| 分组 | 端点数 | 主要功能 |
|------|--------|----------|
| `/analyze` | 1 | 账号全量数据拉取 |
| `/resolve` | 1 | GW2 静态数据代理 |
| `/value/*` | 17 | 估值, 搜索, 差分, 订单簿 |
| `/crafting/*` | 10 | 制作计算, 优化, 静态数据刷新 |
| `/goals/*` | 5 | 目标 CRUD + 进度刷新 |
| `/progression/*` | 3 | 传奇/升华规划 |
| `/builds/*` | 4 | Build 推荐 |
| `/tp/*` | 6 | 市场策略 |
| `/agent/*` | 2 | 成长建议 |

完整 API 文档请参考 [`ARCHITECTURE.md`](ARCHITECTURE.md)

---

## 测试

```bash
pytest tests/ -v          # 运行全部 159 测试
pytest tests/ -q          # 简洁输出
pytest tests/ --cov=src   # 覆盖率报告
```

---

## 技术栈

- **后端**: Python 3.12+, FastAPI, httpx, aiosqlite
- **前端**: Vanilla JS, Chart.js, 单页应用 (SPA)
- **数据**: SQLite (WAL), 内存 TTL 缓存
- **部署**: Docker, Docker Compose
- **CI**: GitHub Actions (lint + test + docker)
- **质量**: ruff, pytest, pre-commit

---

## 成熟度

| 维度 | 评分 | 状态 |
|------|------|------|
| 测试覆盖 | 7/10 | 159 tests, 18 文件 |
| 代码组织 | 8/10 | 22 services, 路由清晰, 内聚度 0.7-0.9 |
| 错误处理 | 7/10 | 中间件隔离, DB 连接池 |
| 性能 | 7/10 | TTL 缓存, 连接池, WAL |
| 安全 | 6/10 | 速率限制, Session 管理 |
| 前端 | 7/10 | 7 模块, Chart.js, 响应式 |
| **综合** | **A-** | 功能完整, 架构清晰 |

---

## 许可证

MIT
