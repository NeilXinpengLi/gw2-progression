"""Mapper: GW2 API AccountContents → AccountObjectGraph (full object graph)."""

import logging
from datetime import datetime, timezone
from typing import Any

from ..analyzer import AccountContents
from .models import (
    AccountObjectGraph,
    AchievementCategory,
    CharacterNode,
    CurrencyGraph,
    CurrencyNode,
    EquipmentSlot,
    GuildNode,
    ItemNode,
    MarketGraph,
    MarketOrder,
    ProgressionGraph,
    UnlockGraph,
    UnlockNode,
)

logger = logging.getLogger("gw2.object_graph")

CURRENCY_IDS = {
    1: "Gold", 2: "Karma", 3: "Laurels", 4: "Spirit Shards",
    5: "Fractal Relics", 6: "PvP Tournament Tickets", 7: "WvW Skirmish Tickets",
    8: "Ascended Currency", 9: "Magnetite Shards", 10: "Gaeting Crystals",
    11: "Provisioning Tokens", 12: "Testimony of Heroics", 13: "Gems",
    14: "Volatile Magic", 15: "Unbound Magic", 16: "Research Notes",
}


def map_to_graph(contents: AccountContents) -> AccountObjectGraph:
    """Transform AccountContents (from fetch_all) into a full object graph."""
    graph = AccountObjectGraph(
        account_name=contents.account_name or "unknown",
        world=contents.account_world or 0,
        created=contents.account_created or "",
        age_hours=contents.account_age_hours or 0.0,
    )

    _map_currencies(contents, graph)
    _map_materials(contents, graph)
    _map_bank(contents, graph)
    _map_characters(contents, graph)
    _map_shared_inventory(contents, graph)
    _map_tradingpost(contents, graph)
    _map_unlocks(contents, graph)
    _map_progression(contents, graph)
    _map_guilds(contents, graph)

    return graph


def _map_currencies(contents: AccountContents, graph: AccountObjectGraph) -> None:
    """Map all wallet currencies into the currency graph."""
    cg = graph.currencies
    wallet = contents.wallet or []

    # Set gold/silver/copper from id=1
    for entry in wallet:
        cid = entry.get("id")
        val = entry.get("value", 0)
        name = CURRENCY_IDS.get(cid, f"Currency #{cid}")

        if cid == 1:
            cg.gold = CurrencyNode(currency_id=1, name="Gold", value=val, gold=val // 10000, silver=(val // 100) % 100, copper=val % 100)
        elif cid == 2:
            cg.karma = CurrencyNode(currency_id=2, name="Karma", value=val)
        elif cid == 3:
            cg.laurels = CurrencyNode(currency_id=3, name="Laurels", value=val)
        elif cid == 4:
            cg.spirit_shards = CurrencyNode(currency_id=4, name="Spirit Shards", value=val)
        elif cid == 5:
            cg.fractal_relics = CurrencyNode(currency_id=5, name="Fractal Relics", value=val)
        elif cid == 6:
            cg.pvp_tickets = CurrencyNode(currency_id=6, name="PvP Tournament Tickets", value=val)
        elif cid == 7:
            cg.wvw_skirmish = CurrencyNode(currency_id=7, name="WvW Skirmish Tickets", value=val)
        elif cid == 9:
            cg.magnetite = CurrencyNode(currency_id=9, name="Magnetite Shards", value=val)
        elif cid == 10:
            cg.gaeting = CurrencyNode(currency_id=10, name="Gaeting Crystals", value=val)
        elif cid == 11:
            cg.provisioning = CurrencyNode(currency_id=11, name="Provisioning Tokens", value=val)
        elif cid == 12:
            cg.testimony = CurrencyNode(currency_id=12, name="Testimony of Heroics", value=val)
        elif cid == 13:
            cg.gems = CurrencyNode(currency_id=13, name="Gems", value=val)
        elif cid == 14:
            cg.volatile_magic = CurrencyNode(currency_id=14, name="Volatile Magic", value=val)
        elif cid == 15:
            cg.unbound_magic = CurrencyNode(currency_id=15, name="Unbound Magic", value=val)
        elif cid == 16:
            cg.research_notes = CurrencyNode(currency_id=16, name="Research Notes", value=val)


def _map_materials(contents: AccountContents, graph: AccountObjectGraph) -> None:
    for entry in contents.materials or []:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id")
        count = entry.get("count", 0)
        if item_id and count > 0:
            graph.items.append(ItemNode(item_id=item_id, count=count, location="materials", binding="", tradable=True))


def _map_bank(contents: AccountContents, graph: AccountObjectGraph) -> None:
    for entry in contents.bank or []:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id")
        count = entry.get("count", 0)
        if item_id:
            graph.items.append(ItemNode(
                item_id=item_id, count=count or 1, location="bank",
                binding=entry.get("binding") or "", tradable=entry.get("binding") is None,
            ))


def _map_characters(contents: AccountContents, graph: AccountObjectGraph) -> None:
    for ch in contents.characters or []:
        if not isinstance(ch, dict):
            continue
        char_name = ch.get("name", "?")
        equipment_slots = []
        equip_value = 0
        for eq in ch.get("equipment") or []:
            if not isinstance(eq, dict):
                continue
            eq_item_id = eq.get("id")
            slot = eq.get("slot", "")
            equipment_slots.append(EquipmentSlot(
                slot=slot, item_id=eq_item_id or 0,
                binding=eq.get("binding") or "",
                skin_id=eq.get("skin") or 0,
                dyes=eq.get("dyes") or [],
            ))
            graph.items.append(ItemNode(item_id=eq_item_id or 0, count=1, location="character_equip", location_ref=f"{char_name}/{slot}", binding="AccountBound", tradable=False))

        bag_items = []
        for bag in ch.get("bags") or []:
            if not isinstance(bag, dict):
                continue
            for slot_idx, slot in enumerate(bag.get("inventory") or []):
                if slot is None or not isinstance(slot, dict):
                    continue
                slot_id = slot.get("id")
                slot_count = slot.get("count", 1)
                if slot_id:
                    node = ItemNode(item_id=slot_id, count=slot_count, location="character_inv", location_ref=f"{char_name}/bag{slot_idx}", binding=slot.get("binding") or "", tradable=slot.get("binding") is None)
                    graph.items.append(node)
                    bag_items.append(node)

        created_str = ch.get("created", "")
        login_days = 0
        if created_str:
            try:
                login_days = (datetime.now(timezone.utc) - datetime.fromisoformat(created_str.replace("Z", "+00:00"))).days
            except (ValueError, TypeError):
                pass

        graph.characters.append(CharacterNode(
            name=char_name,
            profession=ch.get("profession", ""),
            level=ch.get("level", 0),
            race=ch.get("race", ""),
            age=ch.get("age", 0),
            playtime_hours=round(ch.get("age", 0) / 3600, 1),
            created=created_str,
            last_login_days=login_days,
            deaths=ch.get("deaths", 0),
            equipment=equipment_slots,
            bag_count=len(ch.get("bags") or []),
            bag_items=bag_items,
            build_tabs=len(ch.get("build_tabs") or ch.get("equipment_tabs") or []),
        ))


def _map_shared_inventory(contents: AccountContents, graph: AccountObjectGraph) -> None:
    shared = contents.shared_inventory
    if isinstance(shared, dict):
        shared = shared.get("slots") or []
    for entry in shared or []:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id")
        count = entry.get("count", 1)
        if item_id:
            graph.items.append(ItemNode(item_id=item_id, count=count, location="shared", binding=entry.get("binding") or "", tradable=entry.get("binding") is None))


def _map_tradingpost(contents: AccountContents, graph: AccountObjectGraph) -> None:
    for entry in contents.tradingpost_buys or []:
        if not isinstance(entry, dict):
            continue
        iid = entry.get("item_id") or entry.get("id")
        qty = entry.get("quantity", 0)
        price = entry.get("price", 0)
        if iid and qty > 0:
            graph.items.append(ItemNode(item_id=iid, count=qty, location="tp_buy", tradable=True, price_buy=price, value_buy=qty * price))
            graph.market.buy_orders.append(MarketOrder(item_id=iid, price=price, quantity=qty, order_type="buy"))
            graph.market.total_buy_value += qty * price

    for entry in contents.tradingpost_sells or []:
        if not isinstance(entry, dict):
            continue
        iid = entry.get("item_id") or entry.get("id")
        qty = entry.get("quantity", 0)
        price = entry.get("price", 0)
        if iid and qty > 0:
            graph.items.append(ItemNode(item_id=iid, count=qty, location="tp_sell", tradable=True, price_sell=price, value_sell=qty * price))
            graph.market.sell_orders.append(MarketOrder(item_id=iid, price=price, quantity=qty, order_type="sell"))
            graph.market.total_sell_value += qty * price


def _map_unlocks(contents: AccountContents, graph: AccountObjectGraph) -> None:
    ug = graph.unlocks
    ug.skin_count = len(contents.unlocked_skins or [])
    ug.dye_count = len(contents.unlocked_dyes or [])
    ug.mini_count = len(contents.unlocked_minis or [])
    ug.finisher_count = len(contents.unlocked_finishers or [])

    for sid in (contents.unlocked_skins or [])[:20]:
        ug.skins.append(UnlockNode(unlock_type="skin", unlock_id=sid))
    for did in (contents.unlocked_dyes or [])[:20]:
        ug.dyes.append(UnlockNode(unlock_type="dye", unlock_id=did))
    for mid in (contents.unlocked_minis or [])[:20]:
        ug.minis.append(UnlockNode(unlock_type="mini", unlock_id=mid))


def _map_progression(contents: AccountContents, graph: AccountObjectGraph) -> None:
    pg = graph.progression
    pg.daily_ap = contents.daily_ap or 0
    pg.monthly_ap = contents.monthly_ap or 0
    pg.wvw_rank = contents.wvw_rank or 0
    pg.fractal_level = contents.fractal_level or 0
    pg.build_count = len(contents.builds or [])
    pg.mastery_count = len(contents.masteries or [])


def _map_guilds(contents: AccountContents, graph: AccountObjectGraph) -> None:
    guild_ids = contents.account.get("guilds") if hasattr(contents, "account") else []
    if not guild_ids and contents.account_name:
        pass  # guilds are fetched via fetch_guilds separately
