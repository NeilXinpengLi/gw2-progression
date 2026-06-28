"""Object Graph Data Models — full gw2efficiency-level account graph."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ── Currency System (10+ types) ─────────────────────


@dataclass
class CurrencyNode:
    currency_id: int = 0
    name: str = ""
    value: int = 0  # raw value from API
    gold: int = 0
    silver: int = 0
    copper: int = 0
    icon: str = ""


@dataclass
class CurrencyGraph:
    gold: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=1, name="Gold"))
    silver: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=1))
    copper: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=1))
    karma: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=2, name="Karma"))
    laurels: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=3, name="Laurels"))
    spirit_shards: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=4, name="Spirit Shards"))
    fractal_relics: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=5, name="Fractal Relics"))
    pvp_tickets: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=6, name="PvP Tournament Tickets"))
    wvw_skirmish: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=7, name="WvW Skirmish Tickets"))
    ascended_currency: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=8, name="Ascended Currency"))
    magnetite: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=9, name="Magnetite Shards"))
    gaeting: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=10, name="Gaeting Crystals"))
    provisioning: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=11, name="Provisioning Tokens"))
    testimony: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=12, name="Testimony of Heroics"))
    gems: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=13, name="Gems"))
    volatile_magic: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=14, name="Volatile Magic"))
    unbound_magic: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=15, name="Unbound Magic"))
    research_notes: CurrencyNode = field(default_factory=lambda: CurrencyNode(currency_id=16, name="Research Notes"))


# ── Item Node (atomic unit) ──────────────────────────


@dataclass
class ItemNode:
    """A single item stack at a specific location."""
    item_id: int = 0
    count: int = 0
    location: str = ""       # bank / materials / character_equip / character_inv / shared / tp_buy / tp_sell
    location_ref: str = ""   # e.g. "CharName/WeaponA1" or "bag0/slot3"
    binding: str = ""        # AccountBound / Soulbound / ""
    tradable: bool = True
    rarity: str = ""         # Basic / Fine / Masterwork / Rare / Exotic / Ascended / Legendary
    level: int = 0
    price_buy: int = 0
    price_sell: int = 0
    value_buy: int = 0
    value_sell: int = 0
    value_after_fee: int = 0
    icon: str = ""


# ── Character Node ────────────────────────────────────


@dataclass
class EquipmentSlot:
    slot: str = ""           # Helm / Shoulders / WeaponA1 / etc.
    item_id: int = 0
    binding: str = ""
    skin_id: int = 0
    dyes: list[int] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


@dataclass
class CharacterNode:
    name: str = ""
    profession: str = ""
    elite_specialization: str = ""
    level: int = 0
    race: str = ""
    age: int = 0
    playtime_hours: float = 0.0
    created: str = ""
    last_login_days: int = 0
    deaths: int = 0
    equipment: list[EquipmentSlot] = field(default_factory=list)
    equipment_value: int = 0
    bag_count: int = 0
    bag_items: list[ItemNode] = field(default_factory=list)
    build_tabs: int = 0
    specializations: list[dict] = field(default_factory=list)


# ── Unlock Nodes ──────────────────────────────────────


@dataclass
class UnlockNode:
    unlock_type: str = ""  # skin / dye / mini / finisher / mount / glider / emote
    unlock_id: int = 0
    name: str = ""


@dataclass
class UnlockGraph:
    skins: list[UnlockNode] = field(default_factory=list)
    dyes: list[UnlockNode] = field(default_factory=list)
    minis: list[UnlockNode] = field(default_factory=list)
    finishers: list[UnlockNode] = field(default_factory=list)
    skin_count: int = 0
    dye_count: int = 0
    mini_count: int = 0
    finisher_count: int = 0


# ── Market Node ───────────────────────────────────────


@dataclass
class MarketOrder:
    item_id: int = 0
    price: int = 0
    quantity: int = 0
    order_type: str = ""  # buy / sell


@dataclass
class MarketGraph:
    buy_orders: list[MarketOrder] = field(default_factory=list)
    sell_orders: list[MarketOrder] = field(default_factory=list)
    total_buy_value: int = 0
    total_sell_value: int = 0


# ── Guild Node ────────────────────────────────────────


@dataclass
class GuildNode:
    guild_id: str = ""
    name: str = ""
    tag: str = ""
    role: str = ""


# ── Progression Node ──────────────────────────────────


@dataclass
class AchievementCategory:
    category_id: int = 0
    name: str = ""
    completed: int = 0
    total: int = 0
    progress_pct: float = 0.0


@dataclass
class ProgressionGraph:
    daily_ap: int = 0
    monthly_ap: int = 0
    wvw_rank: int = 0
    fractal_level: int = 0
    achievement_categories: list[AchievementCategory] = field(default_factory=list)
    mastery_count: int = 0
    build_count: int = 0


# ── Account Master Graph ──────────────────────────────


@dataclass
class AccountObjectGraph:
    """Complete gw2efficiency-level object graph for an account."""
    account_name: str = ""
    world: int = 0
    created: str = ""
    age_hours: float = 0.0

    currencies: CurrencyGraph = field(default_factory=CurrencyGraph)
    items: list[ItemNode] = field(default_factory=list)
    characters: list[CharacterNode] = field(default_factory=list)
    unlocks: UnlockGraph = field(default_factory=UnlockGraph)
    market: MarketGraph = field(default_factory=MarketGraph)
    guilds: list[GuildNode] = field(default_factory=list)
    progression: ProgressionGraph = field(default_factory=ProgressionGraph)
