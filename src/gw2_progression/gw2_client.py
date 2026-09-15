import asyncio
from typing import Any

import httpx

GW2_BASE = "https://api.guildwars2.com"
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]

_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30)
    return _client


async def _close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class Gw2ApiError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


async def _get(path: str, api_key: str) -> Any:
    headers = {"Authorization": f"Bearer {api_key}"}
    client = await _get_client()
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.get(f"{GW2_BASE}{path}", headers=headers)
            if response.status_code == 401:
                raise Gw2ApiError(401, "Invalid or expired API key.")
            if not response.is_success:
                if response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                raise Gw2ApiError(response.status_code, response.text)
            return response.json()
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAYS[attempt])
                continue
            raise Gw2ApiError(0, str(e))


async def fetch_tokeninfo(api_key: str) -> dict:
    return await _get("/v2/tokeninfo", api_key)


async def fetch_account(api_key: str) -> dict:
    return await _get("/v2/account", api_key)


async def fetch_characters(api_key: str) -> list:
    return await _get("/v2/characters?ids=all", api_key)


async def fetch_wallet(api_key: str) -> list:
    return await _get("/v2/account/wallet", api_key)


async def fetch_bank(api_key: str) -> list:
    return await _get("/v2/account/bank", api_key)


async def fetch_materials(api_key: str) -> list:
    return await _get("/v2/account/materials", api_key)


async def fetch_inventory(api_key: str) -> dict:
    return await _get("/v2/account/inventory", api_key)


async def fetch_achievements(api_key: str) -> list:
    return await _get("/v2/account/achievements", api_key)


async def fetch_masteries(api_key: str) -> list:
    return await _get("/v2/account/masteries", api_key)


async def fetch_mastery_points(api_key: str) -> dict:
    return await _get("/v2/account/mastery/points", api_key)


async def fetch_builds(api_key: str) -> dict:
    return await _get("/v2/account/buildstorage", api_key)


async def fetch_guild(api_key: str, guild_id: str) -> dict:
    """Resolve a single guild GUID to core details (id, name, tag, emblem).

    Public endpoint (Scope: none) — name/tag come back without any special
    permission. Used to resolve the guild a character is representing.
    """
    return await _get(f"/v2/guild/{guild_id}", api_key)


async def fetch_guilds(api_key: str, guild_ids: list[str] | None = None) -> list:
    # GW2 has no bulk /v2/guild?ids= endpoint (it returns "not found"); each
    # guild must be resolved individually via /v2/guild/{id}.
    if not guild_ids:
        return []
    results = await asyncio.gather(
        *(fetch_guild(api_key, gid) for gid in guild_ids),
        return_exceptions=True,
    )
    return [g for g in results if isinstance(g, dict)]


async def fetch_pvp_stats(api_key: str) -> dict:
    return await _get("/v2/pvp/stats", api_key)


async def fetch_pvp_games(api_key: str) -> list:
    return await _get("/v2/pvp/games", api_key)


async def fetch_pvp_standings(api_key: str) -> list:
    return await _get("/v2/pvp/standings", api_key)


async def fetch_tradingpost_current_buys(api_key: str) -> list:
    return await _get("/v2/commerce/transactions/current/buys", api_key)


async def fetch_tradingpost_current_sells(api_key: str) -> list:
    return await _get("/v2/commerce/transactions/current/sells", api_key)


async def fetch_unlocked_skins(api_key: str) -> list:
    return await _get("/v2/account/skins", api_key)


async def fetch_unlocked_dyes(api_key: str) -> list:
    return await _get("/v2/account/dyes", api_key)


async def fetch_unlocked_minis(api_key: str) -> list:
    return await _get("/v2/account/minis", api_key)


async def fetch_unlocked_finishers(api_key: str) -> list:
    return await _get("/v2/account/finishers", api_key)


async def fetch_wvw_stats(wvw_team: str | None = None, wvw_rank: int | None = None) -> dict:
    return {"wvw_team": wvw_team, "account_wvw_rank": wvw_rank}
