"""Three-layer data models: Raw → Normalized → Derived.

LAYER 1: Raw — mirrors GW2 API structure (no transformation)
LAYER 2: Normalized — gw2efficiency-aligned domain models
LAYER 3: Derived — AI/Decision intelligence computed from snapshot
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ── Layer 1: Raw (GW2 API mirror) ──────────────────────────────────


@dataclass
class RawAccount:
    id: str = ""
    name: str = ""
    world: int = 0
    created: str = ""
    age: int = 0
    access: str = ""
    guilds: list[str] = field(default_factory=list)
    guild_leader: list[str] = field(default_factory=list)
    fractal_level: int = 0
    daily_ap: int = 0
    monthly_ap: int = 0
    wvw_rank: int = 0
    last_modified: str = ""


@dataclass
class RawCharacter:
    name: str = ""
    race: str = ""
    profession: str = ""
    elite_specialization: str = ""
    level: int = 0
    age: int = 0
    created: str = ""
    deaths: int = 0
    equipment: list[dict] = field(default_factory=list)
    bags: list[dict] = field(default_factory=list)
    skills: dict = field(default_factory=dict)
    traits: dict = field(default_factory=dict)
    crafting: list[dict] = field(default_factory=list)
    backstory: list[str] = field(default_factory=list)
    wvw_abilities: list[dict] = field(default_factory=list)
    build_tabs: list[dict] = field(default_factory=list)
    equipment_tabs: list[dict] = field(default_factory=list)
    recipes: list[int] = field(default_factory=list)


@dataclass
class RawWallet:
    coins: int = 0
    currencies: list[dict] = field(default_factory=list)


@dataclass
class RawInventory:
    bank: list[dict | None] = field(default_factory=list)
    materials: list[dict] = field(default_factory=list)
    shared_inventory: list[dict | None] = field(default_factory=list)


@dataclass
class RawTradingPost:
    buys: list[dict] = field(default_factory=list)
    sells: list[dict] = field(default_factory=list)


@dataclass
class RawUnlocks:
    skins: list[int] = field(default_factory=list)
    dyes: list[int] = field(default_factory=list)
    minis: list[int] = field(default_factory=list)
    finishers: list[dict] = field(default_factory=list)
    titles: list[int] = field(default_factory=list)
    masteries: list[dict] = field(default_factory=list)
    mastery_points: dict = field(default_factory=dict)
    achievements: list[dict] = field(default_factory=list)
    recipes: list[int] = field(default_factory=list)


@dataclass
class RawAccountData:
    account: RawAccount = field(default_factory=RawAccount)
    characters: list[RawCharacter] = field(default_factory=list)
    wallet: RawWallet = field(default_factory=RawWallet)
    inventory: RawInventory = field(default_factory=RawInventory)
    tradingpost: RawTradingPost = field(default_factory=RawTradingPost)
    unlocks: RawUnlocks = field(default_factory=RawUnlocks)
    pvp: dict = field(default_factory=dict)
    wvw: dict = field(default_factory=dict)
    fetched_at: str = ""


# ── Layer 2: Normalized (gw2efficiency-aligned) ──────────────────


@dataclass
class AccountSnapshot:
    """Immutable point-in-time account snapshot. All AI reads from here."""
    snapshot_id: str = ""
    account_name: str = ""
    world: int = 0
    created_at: str = ""
    age_hours: float = 0.0
    character_count: int = 0
    total_levels: int = 0
    max_level_count: int = 0


@dataclass
class CharacterEntity:
    id: str = ""
    name: str = ""
    profession: str = ""
    elite_specialization: str = ""
    level: int = 0
    playtime_hours: float = 0.0
    created: str = ""
    deaths: int = 0
    gear_score: int = 0
    last_login_days: int = 0
    build_tabs: int = 0


@dataclass
class AssetEntity:
    item_id: int = 0
    count: int = 0
    location: str = ""       # wallet / bank / material / character / shared / tp_buy / tp_sell
    location_ref: str = ""
    binding: str = ""
    tradable: bool = True
    price_buy: int = 0
    price_sell: int = 0
    value_buy: int = 0
    value_sell: int = 0
    value_after_fee: int = 0
    liquidity: str = "unknown"
    confidence: float = 0.0
    data_source: str = "gw2_api"


@dataclass
class CurrencyEntity:
    gold: int = 0
    silver: int = 0
    copper: int = 0
    karma: int = 0
    laurels: int = 0
    spirit_shards: int = 0
    fractal_relics: int = 0
    pvp_tickets: int = 0
    wvw_skirmish_tickets: int = 0
    magnetite_shards: int = 0
    gaeting_crystals: int = 0
    provisioning_tokens: int = 0
    testimony_of_heroics: int = 0


@dataclass
class NormalizedAccountData:
    snapshot: AccountSnapshot = field(default_factory=AccountSnapshot)
    characters: list[CharacterEntity] = field(default_factory=list)
    assets: list[AssetEntity] = field(default_factory=list)
    currencies: CurrencyEntity = field(default_factory=CurrencyEntity)
    snapshot_id: str = ""


# ── Layer 3: Derived (AI/Decision intelligence) ──────────────────


@dataclass
class AccountValue:
    snapshot_id: str = ""
    total_value: int = 0
    liquid_value: int = 0          # sell value after TP fee
    liquid_value_buy: int = 0      # buy value
    hidden_value: int = 0          # value of unpriced items
    wallet_gold: int = 0
    material_value: int = 0
    bank_value: int = 0
    character_value: int = 0
    shared_inventory_value: int = 0
    tp_buy_value: int = 0
    tp_sell_value: int = 0
    confidence: float = 0.0
    data_freshness_hours: float = 0.0


@dataclass
class AssetBreakdown:
    category: str = ""
    total_value: int = 0
    liquid_value: int = 0
    percentage: float = 0.0
    risk: str = "low"
    item_count: int = 0


@dataclass
class DerivedAccountData:
    value: AccountValue = field(default_factory=AccountValue)
    breakdown: list[AssetBreakdown] = field(default_factory=list)
    snapshot_id: str = ""
