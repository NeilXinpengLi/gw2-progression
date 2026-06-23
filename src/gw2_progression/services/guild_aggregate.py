"""Guild aggregation — fetch and combine stats across all guild members."""

import logging

from gw2_progression.analyzer import fetch_all
from gw2_progression.services.guild_service import get_member_accounts

logger = logging.getLogger("gw2.guild.aggregate")


async def aggregate_guild(guild_id: int) -> dict:
    members = await get_member_accounts(guild_id)
    combined = {
        "guild_id": guild_id,
        "member_count": len(members),
        "members": [],
        "total_value_buy": 0,
        "total_wallet_gold": 0,
        "total_characters": 0,
        "total_skins": 0,
        "professions": {},
    }

    for account_name in members:
        try:
            data = await fetch_all(account_name)
            wallet_gold = sum(w.get("value", 0) for w in (data.wallet or []) if w.get("id") == 1)
            chars = data.characters or []
            profs = {}
            for c in chars:
                p = c.get("profession", "Unknown")
                profs[p] = profs.get(p, 0) + 1

            combined["members"].append(
                {
                    "account_name": data.account_name or account_name,
                    "wallet_gold": wallet_gold,
                    "character_count": len(chars),
                    "skin_count": data.unlocked_skins_count or 0,
                    "professions": profs,
                }
            )
            combined["total_wallet_gold"] += wallet_gold
            combined["total_characters"] += len(chars)
            combined["total_skins"] += data.unlocked_skins_count or 0

            for p, c in profs.items():
                combined["professions"][p] = combined["professions"].get(p, 0) + c
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", account_name, e)
            combined["members"].append({"account_name": account_name, "error": str(e)})

    return combined
