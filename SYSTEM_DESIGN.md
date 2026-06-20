# GW2 Progression — 系统设计说明书

> Guild Wars 2 账号进度分析仪表盘
> 基于语义图谱 (`semantic_graph.json`) 与代码图谱分析

---

## 1. 系统架构设计

### 1.1 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser (User)                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              index.html (Vanilla JS SPA)                 │    │
│  │  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐  │    │
│  │  │ Overview│  │Char page │  │Wardrobe │  │  Other   │  │    │
│  │  │  Tab    │  │  Paper   │  │  Skins  │  │  Tabs    │  │    │
│  │  │         │  │  Doll    │  │  Grid   │  │(Wallet,  │  │    │
│  │  │         │  │  Layout  │  │  (Lazy) │  │ PvP...)  │  │    │
│  │  └────┬────┘  └────┬─────┘  └────┬────┘  └────┬─────┘  │    │
│  │       └────────────┴─────────────┴────────────┘         │    │
│  │                          │                                │    │
│  │                    fetch /analyze                         │    │
│  └──────────────────────────┬──────────────────────────────┘    │
└─────────────────────────────┼──────────────────────────────────┘
                              │ POST /analyze { api_key }
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (uvicorn)                      │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              api/routes/analyze.py                       │    │
│  │         POST /analyze → 401/200 + AccountContents       │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │                                     │
│  ┌────────────────────────▼────────────────────────────────┐    │
│  │                   analyzer.py                            │    │
│  │  fetch_all(api_key)                                      │    │
│  │  1. fetch_tokeninfo → validate key                       │    │
│  │  2. fetch_account → extract guild_ids + wvw data         │    │
│  │  3. asyncio.gather(                                      │    │
│  │       fetch_characters, fetch_wallet,                    │    │
│  │       fetch_bank, fetch_materials, ...                   │    │
│  │     )   ← 并行, 权限门控, 错误隔离                        │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │                                     │
│  ┌────────────────────────▼────────────────────────────────┐    │
│  │                   gw2_client.py                          │    │
│  │  _get() → httpx.AsyncClient → api.guildwars2.com         │    │
│  │  + 重试退避: 5xx retry 3x (1s/2s/4s)                    │    │
│  │  + 23 个 fetch_* 函数, 每个映射一个 GW2 API v2 端点       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   cache.py                               │    │
│  │  TTLCache (dict + TTL + maxsize eviction)               │    │
│  │  @cached(ttl=3600) 装饰器, 单例 get_cache()              │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    api.guildwars2.com
                    (GW2 Official API v2)
```

### 1.2 架构决策记录

| 决策 | 选择 | 理由 |
|---|---|---|
| Web 框架 | FastAPI | 原生 async 支持，Pydantic 集成，自动 OpenAPI |
| HTTP 客户端 | httpx.AsyncClient | 异步非阻塞，适配 FastAPI 事件循环 |
| 数据验证 | Pydantic v2 | FastAPI 默认，类型安全，`@field_validator` |
| 前端 | Vanilla JS (0 框架) | 零构建步骤，单 HTML 文件，本地工具无需打包 |
| 部署 | Docker + uvicorn | 单进程，无外部依赖，portable |
| 缓存 | 进程内 TTL dict | 零外部依赖，适合单用户工具场景 |

### 1.3 数据流

```
User Input          Backend                GW2 API              Frontend
─────────          ────────              ────────              ────────
API key ──POST────▶ fetch_tokeninfo ────▶ /v2/tokeninfo
                    │                                           
                    fetch_account  ──────▶ /v2/account
                    │  ├ guild_ids ──────▶ /v2/guild
                    │  └ wvw_team ─────── (derived)
                    │                                           
                    asyncio.gather                               
                    ├ fetch_characters ──▶ /v2/characters       
                    ├ fetch_wallet ──────▶ /v2/account/wallet   
                    ├ fetch_bank ────────▶ /v2/account/bank     
                    ├ ... (18 more)                             
                    │                                           
                    ◀── AccountContents ──┐                     
                                         │                     
                    resolveItems()  ◀────▶ /v2/items            
                    resolveSkins()  ◀────▶ /v2/skins            
                    ...                                         
                                         │                     
                    renderAll() ◀────────┘                     
                    ├ tab-overview                             
                    ├ tab-characters (paper-doll)              
                    ├ tab-wardrobe (lazy 200/batch)            
                    ├ tab-wallet                               
                    ├ tab-inventory                            
                    ├ tab-progression                          
                    ├ tab-pvp                                  
                    ├ tab-unlocks                              
                    └ tab-wvw                                  
```

---

## 2. 系统设计说明

### 2.1 模块职责

| 模块 | 职责 | 关键类/函数 |
|---|---|---|
| `gw2_client.py` | GW2 API HTTP 层 | `Gw2ApiError`, `_get()`, 23× `fetch_*` |
| `analyzer.py` | 编排 + 数据模型 | `AccountContents` (Pydantic), `fetch_all()`, `_safe()` |
| `api/main.py` | FastAPI 入口 | `app`, `GET /health`, `GET /` |
| `api/routes/analyze.py` | API 路由 | `AnalyzeRequest`, `POST /analyze` |
| `cache.py` | 缓存层 | `TTLCache`, `@cached`, `get_cache()` |
| `static/index.html` | 前端 SPA | 9 个 tab 面板, resolve* 函数, render* 函数 |

### 2.2 核心数据模型 — `AccountContents`

```
AccountContents (BaseModel)
├── identity (来自 /v2/account)
│   ├── token_name: str | None
│   ├── account_name: str | None
│   ├── account_world: int | None
│   ├── account_created: str | None
│   ├── account_age_hours: float | None
│   ├── fractal_level: int | None
│   ├── daily_ap: int | None
│   ├── monthly_ap: int | None
│   └── wvw_rank: int | None
│
├── per-section (None = permission not granted / fetch failed)
│   ├── characters: list | None        ← Permission: characters
│   ├── wallet: list | None            ← Permission: wallet
│   ├── bank: list | None              ← Permission: inventories
│   ├── materials: list | None         ← Permission: inventories
│   ├── shared_inventory: list | None  ← Permission: inventories
│   ├── achievements: list | None      ← Permission: progression
│   ├── masteries: list | None         ← Permission: progression
│   ├── mastery_points: dict | None    ← Permission: progression
│   ├── builds: list | None            ← Permission: builds
│   ├── guilds: list | None            ← Permission: guilds
│   ├── pvp_stats: dict | None         ← Permission: pvp
│   ├── pvp_games: list | None         ← Permission: pvp
│   ├── pvp_standings: list | None     ← Permission: pvp
│   ├── tradingpost_buys: list | None  ← Permission: tradingpost
│   ├── tradingpost_sells: list | None ← Permission: tradingpost
│   ├── unlocked_skins: list[int]|None ← Permission: unlocks
│   ├── unlocked_skins_count: int|None
│   ├── unlocked_dyes_count: int|None
│   ├── unlocked_minis_count: int|None
│   ├── unlocked_finishers: list|None
│   └── wvw: dict | None              ← Permission: wvw
│
└── errors: dict[str, str]  ← 每个端点独立错误捕获
```

### 2.3 权限门控 (Permission Guard)

```
fetch_all(api_key)
├── fetch_tokeninfo → 获取 granted permissions set
├── if "account" in granted: fetch_account
├── if "characters" in granted: fetch_characters
├── if "wallet" in granted: fetch_wallet
├── if "inventories" in granted: [bank, materials, inventory]
├── if "progression" in granted: [achievements, masteries, points]
├── if "builds" in granted: fetch_builds
├── if "guilds" in granted: fetch_guilds(guild_ids)
├── if "pvp" in granted: [stats, games, standings]
├── if "tradingpost" in granted: [buys, sells]
├── if "unlocks" in granted: [skins, dyes, minis, finishers]
└── if "wvw" in granted: fetch_wvw_stats(wvw_team, rank)
```

### 2.4 错误隔离策略

```python
async def _safe(fn, *args, **kwargs):
    try:
        result = await fn(*args, **kwargs)
        return result, None
    except Gw2ApiError as e:
        return None, e.message       # 预期 API 错误 → errors dict
    except Exception as e:
        return None, str(e)          # 未预期错误 → errors dict
```

- 每个端点独立 try/except
- 失败不影响其他端点
- 前端按 `ERR_TAB_MAP` 将错误路由到对应 tab

### 2.5 缓存设计

```python
class TTLCache:
    """OrderedDict + time.monotonic() expiry + maxsize eviction."""
    def __init__(self, ttl=3600, maxsize=512): ...
    def get(self, key) -> Any | None: ...
    def set(self, key, value): ...
    def clear(self): ...

# 装饰器用法:
@cached(ttl=3600)
async def fetch_some_static_data(key: str): ...
```

---

## 3. 已实现功能列表

### 3.1 核心功能

| # | 功能 | 输入 | 输出 | 涉及 API |
|---|---|---|---|---|
| 1 | API Key 验证 | API key | token_name + permissions | `/v2/tokeninfo` |
| 2 | 账号总览 | — | name, world, age, fractal, AP, WvW rank | `/v2/account` |
| 3 | 权限徽章网格 | — | 11 个 scope 的 granted/missing 状态 | (derived) |
| 4 | 角色纸娃娃 | — | 装备 slots + 皮肤图标 + 染色圆点 | `/v2/characters` |
| 5 | 角色装备列表 | — | 全部装备名称/图标 tab 式列表 | `/v2/characters` |
| 6 | 武器切换可视化 | — | Set 1 / Set 2 武器槽位分离显示 | `/v2/characters` |
| 7 | 公会徽章 | — | 角色所属公会 tag + 名称 | `/v2/guild` |
| 8 | 衣柜皮肤网格 | — | 200 个/批懒加载, 名称/类型/子类型过滤 | `/v2/account/skins` |
| 9 | 衣柜搜索 | 关键词 | 按皮肤名称实时过滤 | (client-side) |
| 10 | 衣柜分页 | — | "Show more" 按钮, 每次追加 200 个 | (client-side) |
| 11 | 钱包货币 | — | 50+ 货币按数量排序, 金/银/铜格式 | `/v2/account/wallet` |
| 12 | 材料 Top 40 | — | 按数量排序, 带分类名称和图标 | `/v2/account/materials` |
| 13 | 银行槽位概览 | — | 已用/总槽位数 + 物品预览 | `/v2/account/bank` |
| 14 | 共享背包 | — | 共享槽位物品列表 | `/v2/account/inventory` |
| 15 | 已解锁成就数 | — | 已追踪成就计数 | `/v2/account/achievements` |
| 16 | 精通列表 | — | 按区域分组, 显示当前等级 | `/v2/account/masteries` |
| 17 | 精通点数统计 | — | 已花费 / 已获取点数 | `/v2/account/mastery/points` |
| 18 | PvP 统计 | — | rank, wins/losses, win rate, desertions, byes | `/v2/pvp/stats` |
| 19 | PvP 最近游戏 | — | 10 场最近比赛: map, result, score, profession | `/v2/pvp/games` |
| 20 | PvP 天梯 | — | 各分段 standings 数据 | `/v2/pvp/standings` |
| 21 | 交易所当前单 | — | 当前买入/卖出订单 | `/v2/commerce/transactions/current` |
| 22 | 解锁统计 | — | skins/dyes/minis/finishers 数量 | `/v2/account/skins|dyes|minis|finishers` |
| 23 | WvW 信息 | — | WvW 等级 + 当前队伍 | `/v2/account` (derived) |

### 3.2 基础设施功能

| # | 功能 | 实现 |
|---|---|---|
| 24 | API key 格式校验 | `@field_validator`, < 8 chars → 422 |
| 25 | 请求重试 + 退避 | `_get()` 中 5xx 重试 3 次, 1s/2s/4s |
| 26 | 超时保护 | `httpx.AsyncClient(timeout=30)` |
| 27 | 逐 tab 错误展示 | `.tab-error` 按 `ERR_TAB_MAP` 路由 |
| 28 | 逐 tab 加载态 | `.tab-loading` spinner, renderAll 时清除 |
| 29 | 请求去重 | `btn.disabled = true/false` |
| 30 | 进程内 TTL 缓存 | `TTLCache` + `@cached` 装饰器 |
| 31 | 异步并发 | `asyncio.gather` 并行所有可用端点 |
| 32 | 权限门控 | 每个端点仅在对应 permission 存在时调用 |
| 33 | CI 流水线 | `.github/workflows/ci.yml`: lint + test (3.12/3.13) |
| 34 | Docker 部署 | `Dockerfile` + `docker-compose.yml` |
| 35 | 测试覆盖 | 13 个测试: 核心流程 + 边界 + 错误隔离 + 缓存 |

---

## 4. 功能详细设计

### 4.1 API Key 验证与权限门控 (`routes/analyze.py` + `analyzer.py`)

```
请求: POST /analyze { api_key: str }
验证: api_key.strip() length ≥ 8

流程:
┌─ fetch_tokeninfo(api_key) ──────────────────────────────┐
│  成功: { name, id, permissions: [...] }                  │
│  401:  raise Gw2ApiError(401) → HTTP 401                │
└─────────────────────────────────────────────────────────┘
         │
         ▼
granted = set(tokeninfo.permissions)
contents = AccountContents(token_name=tokeninfo.name)

         ▼
┌─ if "account" in granted ───────────────────────────────┐
│  fetch_account(api_key)                                  │
│  ├→ account_name, world, created, fractal_level, ...    │
│  ├→ guild_ids (传给 fetch_guilds)                       │
│  ├→ wvw_team (传给 fetch_wvw_stats)                    │
│  │                                                       │
│  └─ asyncio.gather(所有其他权限门控的端点) ────────────│
│      characters │ wallet │ bank │ materials │ ...        │
└─────────────────────────────────────────────────────────┘
```

### 4.2 角色纸娃娃 (`index.html`)

```
数据: data.characters[] → 每个 character 对象

渲染:
┌─ char-selector (按钮列表, 点击切换) ─────────────────┐
│  ch.name ─click──▶ char-detail 区域                   │
└───────────────────────────────────────────────────────┘

┌─ char-detail ────────────────────────────────────────┐
│  ├─ 纸娃娃网格 (6×2 CSS grid)                        │
│  │   Helm │ Shoulders │ Coat │ Gloves │ Legs │ Boots │
│  │   Wep1 │ Wep2      │ Off  │ ────── │ ──── │ ───── │
│  │                                                    │
│  │   每个 slot: 皮肤图标 + 染色圆点 + tooltip          │
│  │                                                    │
│  ├─ 武器切换: Set 1 / Set 2 并列显示                  │
│  │                                                    │
│  ├─ 饰品行: Back │ Accessory1 │ Accessory2 │ Ring1/2  │
│  │          Amulet │ Aquatic │ Scythe                  │
│  │                                                    │
│  ├─ 公会徽章 (如有)                                    │
│  │                                                    │
│  └─ 全部装备列表 (名称 + 图标 + 类型)                  │
└───────────────────────────────────────────────────────┘
```

### 4.3 Wardrobe 分片 + 搜索 (`index.html`)

```
数据: data.unlocked_skins: list[int]

状态:
  _allSkinIds: list[int]          ← 全部皮肤 ID
  _wardrobeFiltered: list[int]    ← 当前过滤后的子集
  _wardrobeVisible: number        ← 当前已显示的个数 (200 递增)
  _skinCache: { id → {name, icon, type, subtype} }

流程:
setupWardrobe(skinIds)
  ├─ 绑定 wardrobe tab 的 click 事件 → loadWardrobeOnce
  ├─ 绑定搜索输入 → resetWardrobePagination
  ├─ 绑定类型/子类型下拉 → resetWardrobePagination
  │
loadWardrobeOnce()
  ├─ resolveSkins(_allSkinIds)    ← 从 GW2 API 按 200/批拉取元数据
  ├─ populateSubtypes()           ← 从 _skinCache 提取所有子类型
  └─ filterWardrobe() → renderWardrobePage()

filterWardrobe()
  ├─ 按名称 (search input) 过滤
  ├─ 按类型 (type select) 过滤
  ├─ 按子类型 (subtype select) 过滤
  └─ _wardrobeFiltered = 过滤结果

renderWardrobePage()
  ├─ 取 _wardrobeFiltered[0.._wardrobeVisible)
  ├─ 渲染为 .skin-grid (CSS grid, 每项 56px 图标 + 名称 + 类型)
  ├─ 更新计数 "Showing X of Y skins"
  └─ if more: 追加 "Show N more" 按钮
      └─ click → _wardrobeVisible += 200 → renderWardrobePage()
```

### 4.4 钱包渲染 (`index.html`)

```
数据: data.wallet: [{id, value}, ...]

流程:
  ├─ 按 value 降序排序
  ├─ 对 id=1 (coin): fmtCoin() → "12g 34s 56c"
  ├─ 对其他 id: toLocaleString()
  ├─ 从 _currencyCache 获取 name + description
  └─ HTML: .currency-row (name, desc, qty)
```

### 4.5 错误隔离与逐 tab 展示 (`analyzer.py` + `index.html`)

```
后端:
  _safe(fetch_characters, api_key)
    ├─ success → return (data, None)
    └─ fail    → return (None, "error message")
                  → errors["characters"] = "error message"

前端:
  ERR_TAB_MAP = {
    characters:        'err-characters',
    wallet:            'err-wallet',
    bank:              'err-inventory',
    achievements:      'err-progression',
    pvp_stats:         'err-pvp',
    skins:             'err-skins',
    ...
  }
  Object.entries(d.errors).forEach(([k, v]) => {
    const tabId = ERR_TAB_MAP[k] || 'err-overview';
    document.getElementById(tabId).innerHTML +=
      `<div class="error-box"><strong>${k}</strong>: ${v}</div>`;
  });
```

### 4.6 请求重试 (`gw2_client.py`)

```
_get(path, api_key):
  for attempt in 0..2:
    try:
      response = await client.get(url, headers)
      if 401 → raise Gw2ApiError(401)       ← 不重试
      if 5xx → sleep(RETRY_DELAYS[attempt]) ← 仅 5xx 重试
               continue
      if other error → raise Gw2ApiError    ← 不重试
      return response.json()
    except (TimeoutException, ConnectError):
      if attempt < 2 → sleep + retry        ← 网络错误重试
      raise

RETRY_DELAYS = [1, 2, 4]  # seconds
```

---

## 5. 代码图谱分析

### 5.1 调用关系图

```
index.html (JS)
  ├─ runAnalyze()
  │   └─ POST /analyze
  │       └─ routes/analyze.py:post_analyze()
  │           └─ analyzer.py:fetch_all()
  │               ├─ _safe(fetch_tokeninfo)
  │               │   └─ gw2_client.py:_get("/v2/tokeninfo")
  │               ├─ _safe(fetch_account)
  │               │   └─ gw2_client.py:_get("/v2/account")
  │               ├─ asyncio.gather(*[
  │               │     _safe(fetch_characters)    → _get("/v2/characters")
  │               │     _safe(fetch_wallet)        → _get("/v2/account/wallet")
  │               │     _safe(fetch_bank)          → _get("/v2/account/bank")
  │               │     _safe(fetch_materials)     → _get("/v2/account/materials")
  │               │     _safe(fetch_inventory)     → _get("/v2/account/inventory")
  │               │     _safe(fetch_achievements)  → _get("/v2/account/achievements")
  │               │     _safe(fetch_masteries)     → _get("/v2/account/masteries")
  │               │     _safe(fetch_mastery_points)→ _get("/v2/account/mastery/points")
  │               │     _safe(fetch_builds)        → _get("/v2/account/buildstorage")
  │               │     _safe(fetch_guilds)        → _get("/v2/guild")
  │               │     _safe(fetch_pvp_stats)     → _get("/v2/pvp/stats")
  │               │     _safe(fetch_pvp_games)     → _get("/v2/pvp/games")
  │               │     _safe(fetch_pvp_standings) → _get("/v2/pvp/standings")
  │               │     _safe(fetch_tradingpost_* ) → _get("/v2/commerce/...")
  │               │     _safe(fetch_unlocked_skins)→ _get("/v2/account/skins")
  │               │     _safe(fetch_unlocked_dyes) → _get("/v2/account/dyes")
  │               │     _safe(fetch_unlocked_minis)→ _get("/v2/account/minis")
  │               │     _safe(fetch_unlocked_finishers)→ _get("/v2/account/finishers")
  │               │     _safe(fetch_wvw_stats)     → (derived from account)
  │               │   ])
  │               └─ return AccountContents
  │
  ├─ renderAll(data)
  │   ├─ renderOverview()     → #tab-overview
  │   ├─ renderCharacters()   → #tab-characters
  │   ├─ renderWallet()       → #tab-wallet
  │   ├─ renderInventory()    → #tab-inventory
  │   ├─ renderProgression()  → #tab-progression
  │   ├─ renderPvp()          → #tab-pvp
  │   ├─ renderUnlocks()      → #tab-unlocks
  │   ├─ renderWvw()          → #tab-wvw
  │   └─ setupWardrobe()      → #tab-wardrobe (lazy)
  │
  └─ resolve 函数 (从 public GW2 API 拉取元数据)
      ├─ resolveItems()       → /v2/items?ids=...
      ├─ resolveCurrencies()  → /v2/currencies?ids=...
      ├─ resolveMatCategories()→ /v2/materials
      ├─ resolveMasteries()   → /v2/masteries?ids=...
      ├─ resolveMaps()        → /v2/maps?ids=...
      ├─ resolveSkins()       → /v2/skins?ids=...
      ├─ resolveColors()      → /v2/colors?ids=...
      └─ resolveGuilds()      → /v2/guild/{id}
```

### 5.2 模块依赖图

```
static/index.html
  (前端 SPA, 无构建依赖)

src/gw2_progression/
├── api/
│   ├── main.py          ──depends_on──▶ routes/analyze.py
│   │                                     (fastapi, pydantic)
│   └── routes/
│       └── analyze.py   ──depends_on──▶ analyzer.py
│                                        gw2_client.py
│                                        (fastapi, pydantic)
│
├── analyzer.py          ──depends_on──▶ gw2_client.py
│                                        (pydantic, asyncio)
│
├── gw2_client.py        ──depends_on──▶ httpx
│                                        (asyncio)
│
└── cache.py             (zero external deps)
```

### 5.3 数据依赖链

```
/api/v2/tokeninfo
  └── permissions (决定后续所有 fetch 的门控)

/api/v2/account
  ├── guilds ─────────────▶ /api/v2/guild?ids=...
  ├── wvw_team ───────────▶ fetch_wvw_stats (派生)
  └── wvw_rank ───────────▶ fetch_wvw_stats (派生)

/api/v2/characters
  ├── equipment.skin ─────▶ /api/v2/skins
  ├── equipment.id ───────▶ /api/v2/items
  ├── equipment.dyes ─────▶ /api/v2/colors
  └── guild ──────────────▶ /api/v2/guild/{id}
```

---

## 6. 语义图谱分析

### 6.1 三轴抽象

| 轴线 | 类型 | 实体 | 数量 |
|---|---|---|---|
| **State** | 权限状态枚举 | `PermissionAccount`, `PermissionCharacters`, ... (11) | 11 |
| **Entity** | 核心数据模型 | `AccountContents`, `AnalyzeRequest` | 2 |
| **Entity** | API 端点函数 | `fetch_*` (22 个) | 22 |
| **Constraint** | 异常约束 | `Gw2ApiError` | 1 |

### 6.2 核心实体 — `AccountContents`

```
AccountContents (Entity)
├── hasToken_name: str | None
├── hasAccount_name: str | None
├── hasAccount_world: int | None
├── hasAccount_created: str | None
├── hasAccount_age_hours: float | None
├── hasFractal_level: int | None
├── hasDaily_ap: int | None
├── hasMonthly_ap: int | None
├── hasWvw_rank: int | None
├── hasCharacters: list | None
├── hasWallet: list | None
├── hasBank: list | None
├── hasMaterials: list | None
├── hasShared_inventory: list | None
├── hasAchievements: list | None
├── hasMasteries: list | None
├── hasMastery_points: dict | None
├── hasBuilds: list | None
├── hasGuilds: list | None
├── hasPvp_stats: dict | None
├── hasPvp_games: list | None
├── hasPvp_standings: list | None
├── hasTradingpost_buys: list | None
├── hasTradingpost_sells: list | None
├── hasUnlocked_skins_count: int | None
├── hasUnlocked_skins: list[int] | None
├── hasUnlocked_dyes_count: int | None
├── hasUnlocked_minis_count: int | None
├── hasUnlocked_finishers: list | None
├── hasWvw: dict | None
└── hasErrors: dict[str, str]
```

### 6.3 SHACL 约束规则

| 规则 ID | 目标 | 严重度 | 逻辑 | 代码锚点 |
|---|---|---|---|---|
| `AuthValidation` | AccountContents | Critical | tokeninfo 必须在任何 fetch 前验证 | `analyzer.py:80-82` |
| `PermissionGuard` | AccountContents | Critical | 每个数据段按 API scope 门控 | `analyzer.py:84-217` |
| `SafeCallWrapper` | fetch_all | Warning | `_safe()` 隔离异常到 errors dict | `analyzer.py:30-37` |
| `GoldFormat` | Wallet | Info | coin(id=1) 渲染为 Xg Xs Xc | `index.html:wallet` |
| `WardrobeLazyLoad` | Wardrobe | Info | 皮肤按 200/批懒加载 | `index.html:wardrobe` |
| `AccountAgeConversion` | AccountContents | Info | 秒→小时 (/3600, round 1) | `analyzer.py:101-102` |
| `GuildFetchChain` | fetch_guilds | Warning | guilds 依赖 account 获取 guild_ids | `gw2_client.py:68-75` |
| `WvwStatsDerivation` | fetch_wvw_stats | Warning | WvW 数据从 account 派生 | `gw2_client.py:114-117` |
| `TimeoutGuard` | gw2_client | Warning | 30s timeout 所有 HTTP 请求 | `gw2_client.py:15` |
| `ApiKeyValidation` | AnalyzeRequest | Warning | key 长度 ≥ 8, 空/过短返回 422 | `routes/analyze.py:14-19` |
| `RetryPolicy` | _get | Info | 5xx 重试 3 次 (1s/2s/4s) | `gw2_client.py:14-41` |
| `CacheTTL` | cache.py | Info | TTL 3600s, maxsize 512 | `cache.py:8` |

### 6.4 语义关系边

```
fetch_all ──composes──▶ AccountContents
fetch_all ──calls──────▶ fetch_tokeninfo (gate)
fetch_all ──calls──────▶ fetch_account (gate)
fetch_all ──gather─────▶ fetch_characters, fetch_wallet, ... (22)
fetch_all ──guards─────▶ Permission{*} (11 scopes)

AccountContents ──renders──▶ index.html (9 tabs)
index.html ──resolves──────▶ /v2/items, /v2/skins, ... (8 public APIs)

_safe ──catches──────────▶ Gw2ApiError
_safe ──populates────────▶ AccountContents.errors

TTLCache ──used_by───────▶ fetch_* (via @cached decorator)
Gw2ApiError ──raised_by──▶ _get (401, 5xx, timeout)
```

---

## 7. 测试覆盖分析

| 测试文件 | 测试函数 | 覆盖范围 |
|---|---|---|
| `test_analyzer.py` (7) | `test_valid_key_returns_account_name` | 全权限 happy path |
| | `test_invalid_key_raises` | 401 异常传播 |
| | `test_all_permissions_no_errors` | 所有端点正常返回 |
| | `test_account_only_permission` | 子集权限 → 其余字段 None |
| | `test_endpoint_error_isolated` | 单端点失败 → errors dict |
| | `test_fetch_guilds_receives_guild_ids` | guild_ids 显式传入 |
| | `test_invalid_key_format_empty` | 空 key → 401 |
| `test_cache.py` (6) | `test_set_and_get` | 基础 set/get |
| | `test_expiry` | TTL 过期 |
| | `test_maxsize` | maxsize 淘汰 |
| | `test_clear` | 清空缓存 |
| | `test_singleton` | 单例模式 |
| | `test_cached_decorator` | 装饰器缓存命中 |

---

## 8. 部署架构

```
开发模式:
  uvicorn gw2_progression.api.main:app --reload --port 8000
  → http://127.0.0.1:8000

生产模式 (Docker):
  docker compose up -d
  → http://0.0.0.0:8000

负载: 单用户本地工具, 无多用户并发需求
存储: 无持久化存储, 全部数据来自 GW2 API
外部依赖: GW2 Official API v2 (api.guildwars2.com)
```
