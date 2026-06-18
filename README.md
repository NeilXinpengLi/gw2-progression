# GW2 Progression

A Guild Wars 2 account intelligence tool inspired by [gw2efficiency](https://gw2efficiency.com) and [HoYoLab](https://www.hoyolab.com). Connect your GW2 API key and get a full visual breakdown of your account — characters, equipment, wardrobe, wallet, inventory, achievements, PvP stats, and more.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Features

### Account Overview
- Account name, world, total playtime, fractal level, daily AP, WvW rank
- Full permission breakdown showing which GW2 API scopes are granted

### Character Viewer
- Switch between all characters on your account
- **Paper doll** equipment layout — every gear slot shown with the skin's icon
- Dye colors displayed as color dots on each slot (top-right corner)
- Hover any slot for the skin name tooltip
- Weapon swap sets (set 1 and set 2)
- Trinkets: Back, Amulet, Accessory 1 & 2, Ring 1 & 2
- Guild badge per character showing `[TAG] Guild Name` (fetched from the public GW2 API)
- Full equipment list with icon, slot name, item name, and dye swatches

### Wardrobe
- All unlocked account skins displayed as an icon grid
- Filter by type: **Armor**, **Weapon**, **Back Item**
- Filter by subtype (auto-populated: Head, Coat, Greatsword, etc.)
- Live search by skin name
- Lazy-loads on first visit — fetches 1,000+ skin icons in batches

### Wallet
- All 50+ currencies with names and descriptions resolved from the GW2 API
- Gold displayed as `Xg Xs Xc`
- Sorted by quantity

### Inventory
- Top 40 materials by quantity with item icons and resolved category names
- Bank slot usage summary

### Progression
- All unlocked masteries with region (Heart of Thorns, Path of Fire, etc.) and level
- Mastery point totals (spent vs earned) per region
- Total achievement count

### PvP
- PvP rank, wins, losses, win rate, desertions, byes
- 10 most recent games with map name, result, score, and profession

### Unlocks
- Count of unlocked skins, dyes, minis, and finishers
- Finisher list with permanent/quantity status

### WvW
- WvW rank and current team

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, httpx, Pydantic |
| Frontend | Vanilla HTML/CSS/JavaScript (no framework) |
| Data | Guild Wars 2 Official API v2 |
| Package | setuptools, pip editable install |
| Tests | pytest |

---

## Project Structure

```
gw2-progression/
├── src/
│   └── gw2_progression/
│       ├── gw2_client.py       # All GW2 API calls (characters, wallet, skins, etc.)
│       ├── analyzer.py         # Orchestrates all fetches into AccountContents model
│       ├── static/
│       │   └── index.html      # Full single-page UI (paper doll, wardrobe, tabs)
│       └── api/
│           ├── main.py         # FastAPI app, static file serving
│           └── routes/
│               └── analyze.py  # POST /analyze endpoint
├── tests/
│   └── test_analyzer.py        # Unit tests for the analyzer
├── pyproject.toml
└── README.md
```

---

## Getting Started

### Requirements
- Python 3.12+
- A Guild Wars 2 account with an API key

### Installation

```powershell
cd C:\Users\35403\projects\gw2-progression
pip install -e ".[dev]"
```

### Running the app

```powershell
python -m uvicorn gw2_progression.api.main:app --reload
```

Open **http://127.0.0.1:8000** in your browser.

### Running tests

```powershell
python -m pytest tests/ -v
```

---

## Getting a GW2 API Key

1. Log in at [account.arena.net](https://account.arena.net)
2. Go to **Applications** → **New Key**
3. Enable all permissions for full access:
   - `account`, `characters`, `inventories`, `wallet`, `progression`
   - `builds`, `unlocks`, `pvp`, `wvw`, `tradingpost`, `guilds`
4. Copy the key and paste it into GW2 Progression

### Permission Notes

| Permission | What it unlocks |
|---|---|
| `account` | Account name, world, playtime, fractal level, AP, WvW rank |
| `characters` | All characters with equipment, dyes, crafting, guild |
| `inventories` | Bank slots, materials storage, shared inventory |
| `wallet` | All currency balances |
| `progression` | Achievements, masteries, mastery points |
| `builds` | Saved build templates |
| `unlocks` | Skins, dyes, minis, finishers |
| `pvp` | PvP rank, stats, recent games |
| `wvw` | WvW rank and team |
| `tradingpost` | Active buy/sell orders |
| `guilds` | Guild tag and name per character (basic info only — full guild data requires guild leader key) |

---

## How It Works

1. You paste your API key and click **Analyze**
2. The backend calls `/v2/tokeninfo` to validate the key and read granted permissions
3. All permitted endpoints are fetched in parallel (characters, wallet, bank, materials, achievements, masteries, PvP, unlocks, etc.)
4. The frontend then resolves display names from the **public** GW2 API (no key needed):
   - Item names + icons via `/v2/items`
   - Currency names + descriptions via `/v2/currencies`
   - Material category names via `/v2/materials`
   - Skin icons + types via `/v2/skins`
   - Dye colors (exact RGB) via `/v2/colors`
   - Mastery names + regions via `/v2/masteries`
   - Map names via `/v2/maps`
   - Guild name + tag via `/v2/guild/{id}`
5. Everything renders client-side — your API key is only ever sent to your own local server

---

## Privacy

- Your API key is sent only to `http://127.0.0.1:8000` (your own machine)
- No data is stored, logged, or sent to any third party
- The app runs entirely locally

---

## Inspired By

- [gw2efficiency](https://gw2efficiency.com) — the gold standard for GW2 account tools
- [HoYoLab](https://www.hoyolab.com) — the benchmark for game progression dashboards
