"""Normalize raw GW2 API data into ItemHolding models."""

from ..models import ItemHolding


def extract_wallet_holdings(wallet: list | None) -> list[ItemHolding]:
    """Wallet entries (currency id, value). Gold = id=1 is handled specially."""
    result = []
    if not wallet:
        return result
    for entry in wallet:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("id")
        value = entry.get("value", 0)
        if cid != 1:
            continue
        if value > 0:
            result.append(
                ItemHolding(
                    item_id=1,
                    count=value,
                    location_type="wallet",
                    location_ref=None,
                    tradable=True,
                    vendor_value=value,
                    price_buy=1,
                    price_sell=1,
                    value_buy=value,
                    value_sell=value,
                    valuation_status="priced",
                )
            )
    return result


def extract_material_holdings(materials: list | None) -> list[ItemHolding]:
    result = []
    if not materials:
        return result
    for entry in materials:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id")
        count = entry.get("count", 0)
        category = entry.get("category")
        if item_id and count > 0:
            result.append(
                ItemHolding(
                    item_id=item_id,
                    count=count,
                    location_type="material_storage",
                    location_ref=str(category) if category is not None else None,
                    valuation_status="pending",
                )
            )
    return result


def extract_bank_holdings(bank: list | None) -> list[ItemHolding]:
    result = []
    if not bank:
        return result
    for slot_idx, slot in enumerate(bank):
        if slot is None or not isinstance(slot, dict):
            continue
        item_id = slot.get("id")
        count = slot.get("count", 1)
        binding = slot.get("binding")
        if item_id:
            result.append(
                ItemHolding(
                    item_id=item_id,
                    count=count,
                    location_type="bank",
                    location_ref=str(slot_idx),
                    binding_status=binding,
                    tradable=binding is None,
                    valuation_status="pending",
                )
            )
    return result


def extract_character_holdings(characters: list | None) -> list[ItemHolding]:
    """Extract bag inventory items from characters (location_type='character')."""
    result = []
    if not characters:
        return result
    for char in characters:
        if not isinstance(char, dict):
            continue
        char_name = char.get("name", "unknown")
        bags = char.get("bags", [])
        for bag_idx, bag in enumerate(bags):
            if bag is None or not isinstance(bag, dict):
                continue
            inv = bag.get("inventory", [])
            for slot_idx, slot in enumerate(inv):
                if slot is None or not isinstance(slot, dict):
                    continue
                item_id = slot.get("id")
                count = slot.get("count", 1)
                binding = slot.get("binding")
                if item_id:
                    result.append(
                        ItemHolding(
                            item_id=item_id,
                            count=count,
                            location_type="character",
                            location_ref=f"{char_name}/bag{bag_idx}/slot{slot_idx}",
                            binding_status=binding,
                            tradable=binding is None,
                            valuation_status="pending",
                        )
                    )
    return result


def extract_character_equipment(characters: list | None) -> list[ItemHolding]:
    """Extract equipped gear items from characters (location_type='character_equipment')."""
    result = []
    if not characters:
        return result
    for char in characters:
        if not isinstance(char, dict):
            continue
        char_name = char.get("name", "unknown")
        for eq in (char.get("equipment") or []):
            if not isinstance(eq, dict):
                continue
            item_id = eq.get("id")
            slot = eq.get("slot", "")
            if item_id:
                result.append(
                    ItemHolding(
                        item_id=item_id,
                        count=1,
                        location_type="character_equipment",
                        location_ref=f"{char_name}/{slot}",
                        binding_status="AccountBound",
                        tradable=False,
                        valuation_status="pending",
                    )
                )
    return result


def extract_shared_inventory_holdings(shared: list | None) -> list[ItemHolding]:
    result = []
    if not shared:
        return result
    for slot_idx, slot in enumerate(shared):
        if slot is None or not isinstance(slot, dict):
            continue
        item_id = slot.get("id")
        count = slot.get("count", 1)
        binding = slot.get("binding")
        if item_id:
            result.append(
                ItemHolding(
                    item_id=item_id,
                    count=count,
                    location_type="shared_inventory",
                    location_ref=str(slot_idx),
                    binding_status=binding,
                    tradable=binding is None,
                    valuation_status="pending",
                )
            )
    return result


def extract_tradingpost_holdings(buys: list | None, sells: list | None) -> list[ItemHolding]:
    result = []
    if buys:
        for order in buys:
            if not isinstance(order, dict):
                continue
            item_id = order.get("item_id")
            count = order.get("quantity", 0)
            price = order.get("price", 0)
            if item_id and count > 0:
                result.append(
                    ItemHolding(
                        item_id=item_id,
                        count=count,
                        location_type="tradingpost",
                        location_ref="buy_order",
                        tradable=True,
                        price_buy=price,
                        price_sell=0,
                        value_buy=count * price,
                        value_sell=0,
                        valuation_status="priced",
                    )
                )
    if sells:
        for order in sells:
            if not isinstance(order, dict):
                continue
            item_id = order.get("item_id")
            count = order.get("quantity", 0)
            price = order.get("price", 0)
            if item_id and count > 0:
                result.append(
                    ItemHolding(
                        item_id=item_id,
                        count=count,
                        location_type="tradingpost",
                        location_ref="sell_order",
                        tradable=True,
                        price_buy=0,
                        price_sell=price,
                        value_buy=0,
                        value_sell=count * price,
                        valuation_status="priced",
                    )
                )
    return result
