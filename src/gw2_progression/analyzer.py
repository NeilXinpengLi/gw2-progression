from asyncio import gather

from pydantic import BaseModel

from .gw2_client import (
    Gw2ApiError,
    fetch_account,
    fetch_achievements,
    fetch_bank,
    fetch_builds,
    fetch_characters,
    fetch_guilds,
    fetch_inventory,
    fetch_masteries,
    fetch_mastery_points,
    fetch_materials,
    fetch_pvp_games,
    fetch_pvp_standings,
    fetch_pvp_stats,
    fetch_tokeninfo,
    fetch_tradingpost_current_buys,
    fetch_tradingpost_current_sells,
    fetch_unlocked_dyes,
    fetch_unlocked_finishers,
    fetch_unlocked_minis,
    fetch_unlocked_skins,
    fetch_wallet,
    fetch_wvw_stats,
)


async def _safe(fn, *args, **kwargs):
    try:
        if callable(fn):
            result = await fn(*args, **kwargs)
        else:
            result = await fn
        return result, None
    except Gw2ApiError as e:
        return None, e.message
    except Exception as e:
        return None, str(e)


class AccountContents(BaseModel):
    token_name: str | None = None
    account_name: str | None = None
    account_world: int | None = None
    account_created: str | None = None
    account_age_hours: float | None = None
    fractal_level: int | None = None
    daily_ap: int | None = None
    monthly_ap: int | None = None
    wvw_rank: int | None = None

    characters: list | None = None
    wallet: list | None = None
    bank: list | None = None
    materials: list | None = None
    shared_inventory: list | None = None
    achievements: list | None = None
    masteries: list | None = None
    mastery_points: dict | None = None
    builds: list | None = None
    guilds: list | None = None
    pvp_stats: dict | None = None
    pvp_games: list | None = None
    pvp_standings: list | None = None
    tradingpost_buys: list | None = None
    tradingpost_sells: list | None = None
    unlocked_skins_count: int | None = None
    unlocked_skins: list[int] | None = None
    unlocked_dyes: list[int] | None = None
    unlocked_minis: list[int] | None = None
    unlocked_dyes_count: int | None = None
    unlocked_minis_count: int | None = None
    unlocked_finishers: list | None = None
    wvw: dict | None = None

    errors: dict[str, str] = {}


async def fetch_all(api_key: str) -> AccountContents:
    tokeninfo, err = await _safe(fetch_tokeninfo, api_key)
    if err:
        raise Gw2ApiError(401, err)

    granted = set(tokeninfo.get("permissions", []))
    contents = AccountContents(token_name=tokeninfo.get("name"))
    errors: dict[str, str] = {}

    async def section(name, coro, field=None):
        data, err = await _safe(coro)
        if err:
            errors[name] = err
        elif field:
            setattr(contents, field, data)
        return data

    if "account" in granted:
        account, err = await _safe(fetch_account, api_key)
        if err:
            errors["account"] = err
        else:
            contents.account_name = account.get("name")
            contents.account_world = account.get("world")
            contents.account_created = account.get("created")
            contents.fractal_level = account.get("fractal_level")
            contents.daily_ap = account.get("daily_ap")
            contents.monthly_ap = account.get("monthly_ap")
            contents.wvw_rank = account.get("wvw_rank")
            age_seconds = account.get("age", 0)
            contents.account_age_hours = round(age_seconds / 3600, 1)

            guild_ids = account.get("guilds", [])
            wvw_team = account.get("wvw_team")

            pending = []

            if "characters" in granted:
                pending.append(section("characters", fetch_characters(api_key), "characters"))

            if "wallet" in granted:
                pending.append(section("wallet", fetch_wallet(api_key), "wallet"))

            if "inventories" in granted:
                pending.append(section("bank", fetch_bank(api_key), "bank"))
                pending.append(section("materials", fetch_materials(api_key), "materials"))
                pending.append(section("shared_inventory", fetch_inventory(api_key), "shared_inventory"))

            if "progression" in granted:
                pending.append(section("achievements", fetch_achievements(api_key), "achievements"))
                pending.append(section("masteries", fetch_masteries(api_key), "masteries"))
                pending.append(section("mastery_points", fetch_mastery_points(api_key), "mastery_points"))

            if "builds" in granted:
                pending.append(section("builds", fetch_builds(api_key), "builds"))

            if "guilds" in granted:
                pending.append(section("guilds", fetch_guilds(api_key, guild_ids), "guilds"))

            if "pvp" in granted:
                pending.append(section("pvp_stats", fetch_pvp_stats(api_key), "pvp_stats"))
                pending.append(section("pvp_games", fetch_pvp_games(api_key), "pvp_games"))
                pending.append(section("pvp_standings", fetch_pvp_standings(api_key), "pvp_standings"))

            if "tradingpost" in granted:
                pending.append(section("tradingpost_buys", fetch_tradingpost_current_buys(api_key), "tradingpost_buys"))
                fn_sells = section("tradingpost_sells", fetch_tradingpost_current_sells(api_key), "tradingpost_sells")
                pending.append(fn_sells)

            if "unlocks" in granted:
                pending.append(section("skins", fetch_unlocked_skins(api_key), "unlocked_skins"))
                pending.append(section("dyes", fetch_unlocked_dyes(api_key), "unlocked_dyes"))
                pending.append(section("minis", fetch_unlocked_minis(api_key), "unlocked_minis"))
                pending.append(section("finishers", fetch_unlocked_finishers(api_key), "unlocked_finishers"))

            if "wvw" in granted:
                pending.append(section("wvw", fetch_wvw_stats(wvw_team, contents.wvw_rank), "wvw"))

            if pending:
                await gather(*pending)

                if contents.unlocked_skins is not None:
                    contents.unlocked_skins_count = len(contents.unlocked_skins)
                if contents.unlocked_dyes is not None:
                    contents.unlocked_dyes_count = len(contents.unlocked_dyes)
                if contents.unlocked_minis is not None:
                    contents.unlocked_minis_count = len(contents.unlocked_minis)

    contents.errors = errors

    try:
        from .ontology.account_mapper import sync_account_to_ontology
        await sync_account_to_ontology(api_key, contents.account_name or "unknown")
    except Exception as e:
        contents.errors["ontology"] = str(e)

    return contents
