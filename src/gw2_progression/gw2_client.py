import httpx

GW2_BASE = "https://api.guildwars2.com"


class Gw2ApiError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _get(path: str, api_key: str) -> dict | list:
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=30) as client:
        response = client.get(f"{GW2_BASE}{path}", headers=headers)
    if response.status_code == 401:
        raise Gw2ApiError(401, "Invalid or expired API key.")
    if not response.is_success:
        raise Gw2ApiError(response.status_code, response.text)
    return response.json()


def fetch_tokeninfo(api_key: str) -> dict:
    return _get("/v2/tokeninfo", api_key)


def fetch_account(api_key: str) -> dict:
    return _get("/v2/account", api_key)


def fetch_characters(api_key: str) -> list:
    return _get("/v2/characters?ids=all", api_key)


def fetch_wallet(api_key: str) -> list:
    return _get("/v2/account/wallet", api_key)


def fetch_bank(api_key: str) -> list:
    return _get("/v2/account/bank", api_key)


def fetch_materials(api_key: str) -> list:
    return _get("/v2/account/materials", api_key)


def fetch_inventory(api_key: str) -> dict:
    return _get("/v2/account/inventory", api_key)


def fetch_achievements(api_key: str) -> list:
    return _get("/v2/account/achievements", api_key)


def fetch_masteries(api_key: str) -> list:
    return _get("/v2/account/masteries", api_key)


def fetch_mastery_points(api_key: str) -> dict:
    return _get("/v2/account/mastery/points", api_key)


def fetch_builds(api_key: str) -> dict:
    return _get("/v2/account/buildstorage", api_key)


def fetch_guilds(api_key: str) -> list:
    # account endpoint already returns guild IDs; fetch each guild
    account = fetch_account(api_key)
    guild_ids = account.get("guilds", [])
    if not guild_ids:
        return []
    ids_param = ",".join(guild_ids)
    return _get(f"/v2/guild?ids={ids_param}", api_key)


def fetch_pvp_stats(api_key: str) -> dict:
    return _get("/v2/pvp/stats", api_key)


def fetch_pvp_games(api_key: str) -> list:
    return _get("/v2/pvp/games", api_key)


def fetch_pvp_standings(api_key: str) -> list:
    return _get("/v2/pvp/standings", api_key)


def fetch_tradingpost_current_buys(api_key: str) -> list:
    return _get("/v2/commerce/transactions/current/buys", api_key)


def fetch_tradingpost_current_sells(api_key: str) -> list:
    return _get("/v2/commerce/transactions/current/sells", api_key)


def fetch_unlocked_skins(api_key: str) -> list:
    return _get("/v2/account/skins", api_key)


def fetch_unlocked_dyes(api_key: str) -> list:
    return _get("/v2/account/dyes", api_key)


def fetch_unlocked_minis(api_key: str) -> list:
    return _get("/v2/account/minis", api_key)


def fetch_unlocked_finishers(api_key: str) -> list:
    return _get("/v2/account/finishers", api_key)


def fetch_wvw_stats(api_key: str) -> dict:
    account = fetch_account(api_key)
    wvw_guild = account.get("wvw_team")
    return {"wvw_team": wvw_guild, "account_wvw_rank": account.get("wvw_rank")}
