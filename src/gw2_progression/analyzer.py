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


def _safe(fn, api_key: str):
    """Call fn(api_key) and return (result, None) or (None, error_string)."""
    try:
        return fn(api_key), None
    except Gw2ApiError as e:
        return None, e.message
    except Exception as e:
        return None, str(e)


class AccountContents(BaseModel):
    # identity
    token_name: str | None = None
    account_name: str | None = None
    account_world: int | None = None
    account_created: str | None = None
    account_age_hours: float | None = None
    fractal_level: int | None = None
    daily_ap: int | None = None
    monthly_ap: int | None = None
    wvw_rank: int | None = None

    # per-permission sections (None = not fetched / no permission)
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
    unlocked_dyes_count: int | None = None
    unlocked_minis_count: int | None = None
    unlocked_finishers: list | None = None
    wvw: dict | None = None

    errors: dict[str, str] = {}


def fetch_all(api_key: str) -> AccountContents:
    # Validate key first
    tokeninfo, err = _safe(fetch_tokeninfo, api_key)
    if err:
        raise Gw2ApiError(401, err)

    granted = set(tokeninfo.get("permissions", []))
    contents = AccountContents(token_name=tokeninfo.get("name"))
    errors: dict[str, str] = {}

    # account (base info)
    if "account" in granted:
        account, err = _safe(fetch_account, api_key)
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

    # characters
    if "characters" in granted:
        data, err = _safe(fetch_characters, api_key)
        if err:
            errors["characters"] = err
        else:
            contents.characters = data

    # wallet
    if "wallet" in granted:
        data, err = _safe(fetch_wallet, api_key)
        if err:
            errors["wallet"] = err
        else:
            contents.wallet = data

    # inventories
    if "inventories" in granted:
        for key, fn, field in [
            ("bank", fetch_bank, "bank"),
            ("materials", fetch_materials, "materials"),
            ("shared_inventory", fetch_inventory, "shared_inventory"),
        ]:
            data, err = _safe(fn, api_key)
            if err:
                errors[key] = err
            else:
                setattr(contents, field, data)

    # progression
    if "progression" in granted:
        for key, fn, field in [
            ("achievements", fetch_achievements, "achievements"),
            ("masteries", fetch_masteries, "masteries"),
            ("mastery_points", fetch_mastery_points, "mastery_points"),
        ]:
            data, err = _safe(fn, api_key)
            if err:
                errors[key] = err
            else:
                setattr(contents, field, data)

    # builds
    if "builds" in granted:
        data, err = _safe(fetch_builds, api_key)
        if err:
            errors["builds"] = err
        else:
            contents.builds = data if isinstance(data, list) else [data]

    # guilds
    if "guilds" in granted:
        data, err = _safe(fetch_guilds, api_key)
        if err:
            errors["guilds"] = err
        else:
            contents.guilds = data

    # pvp
    if "pvp" in granted:
        for key, fn, field in [
            ("pvp_stats", fetch_pvp_stats, "pvp_stats"),
            ("pvp_games", fetch_pvp_games, "pvp_games"),
            ("pvp_standings", fetch_pvp_standings, "pvp_standings"),
        ]:
            data, err = _safe(fn, api_key)
            if err:
                errors[key] = err
            else:
                setattr(contents, field, data)

    # tradingpost
    if "tradingpost" in granted:
        for key, fn, field in [
            ("tradingpost_buys", fetch_tradingpost_current_buys, "tradingpost_buys"),
            ("tradingpost_sells", fetch_tradingpost_current_sells, "tradingpost_sells"),
        ]:
            data, err = _safe(fn, api_key)
            if err:
                errors[key] = err
            else:
                setattr(contents, field, data)

    # unlocks
    if "unlocks" in granted:
        for key, fn, count_field in [
            ("dyes", fetch_unlocked_dyes, "unlocked_dyes_count"),
            ("minis", fetch_unlocked_minis, "unlocked_minis_count"),
        ]:
            data, err = _safe(fn, api_key)
            if err:
                errors[key] = err
            else:
                setattr(contents, count_field, len(data))

        skins_data, err = _safe(fetch_unlocked_skins, api_key)
        if err:
            errors["skins"] = err
        else:
            contents.unlocked_skins_count = len(skins_data)
            contents.unlocked_skins = skins_data
        data, err = _safe(fetch_unlocked_finishers, api_key)
        if err:
            errors["finishers"] = err
        else:
            contents.unlocked_finishers = data

    # wvw
    if "wvw" in granted:
        data, err = _safe(fetch_wvw_stats, api_key)
        if err:
            errors["wvw"] = err
        else:
            contents.wvw = data

    contents.errors = errors
    return contents
